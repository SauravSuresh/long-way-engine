"""Pure logic for lw review: yaml-driven questionnaire, dispatch, deadline gate.

No Todoist, no network — reads state.yaml/shared.yaml/meta.yaml and the
curriculum's own state_review template, writes state + log + meta.yaml.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import date, timedelta
from pathlib import Path
from typing import Any

import yaml

from src.config import Config, DashboardConfig, TodoistConfig
from src.lw.status_logic import (
    CurriculumCtx,
    EngineCtx,
    current_rung_meta,
    effective_deadline,
)
from src.state import SharedState, save_shared_state, save_syllabus_state, update_derived_fields
from src.state_review import _dispatch, evaluate_show_if, load_state_log, save_state_log
from src.templates import MissingVariable, SubtaskSpec, resolve_string

logger = logging.getLogger(__name__)

# state_review sub_task titles only ever reference state/syllabus fields
# (current_book, current_module, next_module, ...), never ritual_times, so
# an empty Config is enough for resolve_string here.
_EMPTY_CONFIG = Config(
    todoist=TodoistConfig(project_id="", labels={}),
    ritual_times={},
    sunday_off=True,
    dashboard=DashboardConfig(github_username="", repo_name=""),
    todoist_token="",
)


@dataclass
class Question:
    sub: SubtaskSpec
    wants_count: bool


def review_day(cur: CurriculumCtx) -> str | None:
    """The state_review template's scheduled day_of_week (lowercase), or
    None when the curriculum has no state_review template or no fixed day."""
    tpl = next((t for t in cur.templates if t.state_review), None)
    if tpl is None or not tpl.day_of_week:
        return None
    return str(tpl.day_of_week).lower()


def is_review_time(cur: CurriculumCtx, today: date) -> bool:
    """True when today is the curriculum's state-review day. No fixed day
    (or no state_review template) means any day is fine."""
    day = review_day(cur)
    return day is None or day == today.strftime("%A").lower()


def build_questions(cur: CurriculumCtx, today: date) -> list[Question]:
    """The state_review template's sub_tasks, show_if-filtered, titles resolved."""
    tpl = next((t for t in cur.templates if t.state_review), None)
    if tpl is None:
        return []
    questions: list[Question] = []
    for sub in tpl.sub_tasks:
        if not evaluate_show_if(sub.show_if, cur.state, cur.syllabus):
            continue
        try:
            title = resolve_string(sub.title, cur.state, _EMPTY_CONFIG, today, syllabus=cur.syllabus)
        except MissingVariable as e:
            logger.warning("state_review sub_task %r: %s; skipping", sub.title, e)
            continue
        questions.append(
            Question(
                sub=SubtaskSpec(title=title, action=sub.action, show_if=sub.show_if),
                wants_count=sub.action.get("type") == "increment_counter",
            )
        )
    return questions


def apply_answers(
    ctx: EngineCtx,
    key: str,
    answers: list[tuple[Question, "bool | int"]],
    today: date,
) -> list[str]:
    """Dispatch checked answers, save state + shared + log. Returns user_messages."""
    cur = ctx.per_key[key]
    state_path = ctx.repo_root / cur.entry.state_file
    shared_path = ctx.repo_root / "state" / "shared.yaml"
    log_path = ctx.repo_root / "state" / f"{key}_state_log.yaml"
    log_entries = load_state_log(log_path)

    new_state = cur.state
    new_shared = ctx.shared
    messages: list[str] = []
    n = 0
    for question, answer in answers:
        checked = answer if isinstance(answer, bool) else answer > 0
        if not checked:
            continue
        comment = str(answer) if question.wants_count else None
        result = _dispatch(
            question.sub.action, new_state, new_shared, cur.syllabus,
            log_entries, f"lw-review-{today.isoformat()}-{n}", today,
            comment_value=comment,
        )
        n += 1
        if result is None:
            continue
        if isinstance(result.new_state, SharedState):
            new_shared = result.new_state
        else:
            new_state = result.new_state
        log_entries.append(result.log_entry)
        messages.append(result.user_message)

    cur.state = update_derived_fields(new_state, cur.syllabus, today)
    ctx.shared = new_shared
    save_syllabus_state(state_path, cur.state)
    save_shared_state(shared_path, ctx.shared)
    save_state_log(log_path, log_entries)
    return messages


@dataclass
class DeadlineGate:
    meta_path: Path
    meta: dict[str, Any]


@dataclass
class GateOutcome:
    advance: bool
    message: str


def build_deadline_gate(repo_root: Path, cur: CurriculumCtx, today: date) -> DeadlineGate | None:
    """The picked rung's gate, or None if not picked / already resolved / not yet due."""
    meta = current_rung_meta(repo_root, cur.state.current_module)
    if meta is None or meta.get("outcome") is not None:
        return None
    dl = effective_deadline(meta)
    if not dl or date.fromisoformat(dl) > today:
        return None
    mod_no = cur.state.current_module
    meta_path = next(
        d / "meta.yaml"
        for d in sorted((repo_root / "ladder").glob(f"rung-{mod_no:02d}[abc]-*"))
        if (d / "meta.yaml").exists()
    )
    return DeadlineGate(meta_path, meta)


def forced_advance_answer(question: Question, gate_advance: bool) -> bool | None:
    """When the deadline gate resolved fail-forward (shipped/failed →
    advance=True), the advance_module question isn't optional — the spec's
    "failed (logged, advance anyway)" means answering No would silently
    leave the module unadvanced while the gate says otherwise. Returns True
    to force the answer; None when this question isn't gated by the rule."""
    if gate_advance and question.sub.action.get("type") == "advance_module":
        return True
    return None


def preview_gate_outcome(
    choice: str, *, reason: str = "", extra_days: int = 0, today: date
) -> GateOutcome:
    """Same choice/validation semantics as apply_gate below, but pure — no
    gate, no meta, no disk write. lw review's TUI calls this the moment the
    user picks Shipped/Extend/Failed (to decide the next screen's pre-check),
    then only calls the persisting apply_gate if the user reaches Confirm —
    quitting before Confirm must leave meta.yaml untouched."""
    if choice == "shipped":
        return GateOutcome(advance=True, message="shipped — advance the rung below")
    if choice == "failed_move_on":
        return GateOutcome(advance=True, message="failed — logged, moving on; advance the rung below")
    if choice == "failed_retry":
        if extra_days <= 0:
            raise ValueError("failed_retry requires extra_days > 0")
        new_deadline = today + timedelta(days=extra_days)
        return GateOutcome(
            advance=False, message=f"failed — retrying, new deadline {new_deadline.isoformat()}"
        )
    if choice == "extend":
        if not reason:
            raise ValueError("extend requires a reason")
        if extra_days <= 0:
            raise ValueError("extend requires extra_days > 0")
        new_deadline = today + timedelta(days=extra_days)
        return GateOutcome(advance=False, message=f"extended to {new_deadline.isoformat()}")
    raise ValueError(f"unknown gate choice {choice!r}")


def apply_gate(
    gate: DeadlineGate,
    choice: str,
    *,
    reason: str = "",
    extra_days: int = 0,
    today: date,
) -> GateOutcome:
    """choice in {shipped, extend, failed_move_on, failed_retry}. shipped and
    failed_move_on resolve the rung (advance=True); failed_retry logs the
    failure but keeps the rung open with a new deadline (outcome stays null,
    so the gate re-fires); extend requires a reason and extra_days > 0. Writes
    meta.yaml immediately — see preview_gate_outcome for the non-persisting
    twin used to preview the outcome before the user commits to it."""
    outcome = preview_gate_outcome(choice, reason=reason, extra_days=extra_days, today=today)
    meta = gate.meta
    if choice == "shipped":
        meta["outcome"] = "shipped"
    elif choice == "failed_move_on":
        meta["outcome"] = "failed"
        meta.setdefault("failures", []).append(
            {"date": today.isoformat(), "decision": "move_on"}
        )
    elif choice == "failed_retry":
        new_deadline = today + timedelta(days=extra_days)
        meta.setdefault("failures", []).append(
            {"date": today.isoformat(), "decision": "retry"}
        )
        meta.setdefault("extensions", []).append(
            {
                "date": today.isoformat(),
                "new_deadline": new_deadline.isoformat(),
                "reason": "failed — retrying",
            }
        )
    else:  # extend — already validated by preview_gate_outcome above
        new_deadline = today + timedelta(days=extra_days)
        meta.setdefault("extensions", []).append(
            {"date": today.isoformat(), "new_deadline": new_deadline.isoformat(), "reason": reason}
        )
    gate.meta_path.write_text(
        yaml.safe_dump(meta, sort_keys=False, default_flow_style=False), encoding="utf-8"
    )
    return outcome
