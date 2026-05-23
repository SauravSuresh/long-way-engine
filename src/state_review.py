"""State-mutation phase orchestrator.

Runs before the task-creation phase each cron. Responsibilities:

  1. Load state_log.yaml; build applied_task_ids set for idempotency.
  2. Auto-unpause if state.paused_until has elapsed.
  3. For the most recent weekly-state-review parent in cache: fetch its
     sub-tasks via TodoistReviewClient. For every completed sub-task
     whose todoist_task_id is NOT in state_log, dispatch its action via
     state_mutations.ACTION_HANDLERS.
  4. For each persistent task (emergency-pause, resume): poll completion
     via TodoistCompletionClient. If completed and not yet applied,
     dispatch + recreate a fresh instance with a new external_id suffix.
  5. Atomic-write state.yaml; append entries to state_log.yaml.

The orchestrator NEVER mutates state mid-flight. It builds the full
sequence of MutationResults, then commits the final new_state to disk
plus the log entries together. On any individual mutation raising, the
orchestrator logs and skips that one; remaining mutations apply.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any

import yaml

from src.config import Config
from src.ids import external_id
from src.state import State, save_state
from src.state_mutations import ACTION_HANDLERS, MutationResult
from src.syllabus import Syllabus, current_book

logger = logging.getLogger(__name__)


PERSISTENT_EMERGENCY_PAUSE_TITLE = "🛑 Emergency pause (stops tasks on next cron)"
PERSISTENT_EMERGENCY_PAUSE_DESC = (
    "Check this to pause immediately. Auto-recreates after consumption."
)
PERSISTENT_RESUME_TITLE = "▶️ Resume (only fires when paused)"
PERSISTENT_RESUME_DESC = "Check this when you're back."

EMERGENCY_PAUSE_DEFAULT_DAYS = 365


@dataclass
class StateReviewSummary:
    auto_unpaused: bool = False
    mutations_applied: int = 0
    mutations_skipped: int = 0
    persistent_recreated: list[str] = field(default_factory=list)
    messages: list[str] = field(default_factory=list)


def load_state_log(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    try:
        data = yaml.safe_load(path.read_text(encoding="utf-8")) or []
    except yaml.YAMLError as e:
        logger.warning("state_log.yaml unreadable (%s); treating as empty", e)
        return []
    if not isinstance(data, list):
        logger.warning("state_log.yaml is not a list; treating as empty")
        return []
    return data


def save_state_log(path: Path, entries: list[dict[str, Any]]) -> None:
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(
        yaml.safe_dump(entries, sort_keys=False, default_flow_style=False) if entries else "[]\n",
        encoding="utf-8",
    )
    tmp.replace(path)


# --- show_if predicates -----------------------------------------------------


def evaluate_show_if(name: str | None, state: State, syllabus: Syllabus) -> bool:
    if not name:
        return True
    if name == "not_on_last_module":
        return state.current_module < len(syllabus.modules)
    if name == "book_transition_this_month":
        if state.month <= 1:
            return False
        return current_book(state.month, syllabus) != current_book(state.month - 1, syllabus)
    if name == "not_paused":
        return not state.paused
    if name == "paused":
        return state.paused
    logger.warning("unknown show_if predicate %r; defaulting to true", name)
    return True


# --- dispatch ---------------------------------------------------------------


def _dispatch(
    action_spec: dict[str, Any],
    state: State,
    syllabus: Syllabus,
    log_entries: list[dict[str, Any]],
    todoist_task_id: str,
    today: date,
    *,
    comment_value: int | None = None,
) -> MutationResult | None:
    """Call the right handler for `action_spec`. Returns None if the
    action type is unknown (validator should have caught it earlier).
    """
    atype = action_spec.get("type")
    handler = ACTION_HANDLERS.get(str(atype))
    if handler is None:
        logger.error("unknown action type %r; skipping", atype)
        return None
    kwargs: dict[str, Any] = {"todoist_task_id": todoist_task_id, "today": today}
    if atype == "advance_module":
        return handler(state, syllabus, **kwargs)
    if atype in ("mark_book_finished", "mark_book_started"):
        kwargs["book"] = str(action_spec.get("book", state.current_book))
        return handler(state, **kwargs)
    if atype == "set_pause":
        kwargs["days"] = int(action_spec.get("days", EMERGENCY_PAUSE_DEFAULT_DAYS))
        kwargs["reason"] = str(action_spec.get("reason", ""))
        return handler(state, **kwargs)
    if atype == "unset_pause":
        return handler(state, **kwargs)
    if atype == "increment_counter":
        if comment_value is None:
            logger.warning(
                "increment_counter sub-task %s has no parseable comment; skipping",
                todoist_task_id,
            )
            return None
        kwargs["counter"] = str(action_spec.get("counter", "anki_card_count"))
        kwargs["delta"] = comment_value
        return handler(state, **kwargs)
    if atype == "revert_last":
        return handler(state, log_entries, **kwargs)
    logger.error("no dispatch path for action type %r", atype)
    return None


def _parse_counter_comment(comment: str | None) -> int | None:
    if comment is None:
        return None
    stripped = comment.strip()
    if not stripped:
        return None
    try:
        return int(stripped)
    except (ValueError, TypeError):
        return None


# --- main orchestrator ------------------------------------------------------


def run_state_review_phase(
    *,
    config: Config,
    state: State,
    syllabus: Syllabus,
    today: date,
    cache: dict[str, dict[str, Any]],
    state_path: Path,
    state_log_path: Path,
    review_factory=None,
    completion_factory=None,
    dry_run: bool = False,
    todoist_token: str | None = None,
    project_id: str | None = None,
) -> tuple[State, StateReviewSummary]:
    """Execute the state-mutation phase. Returns (new_state, summary).

    On dry-run: no Todoist reads, no disk writes, no mutations applied.
    `state` is returned unchanged and the summary reports zero activity.
    """
    summary = StateReviewSummary()
    if dry_run:
        return state, summary

    log_entries = load_state_log(state_log_path)
    applied_task_ids: set[str] = {
        str(e.get("todoist_task_id"))
        for e in log_entries
        if e.get("todoist_task_id")
    }
    new_state = state
    pending_entries: list[dict[str, Any]] = []

    # 1. Auto-unpause if timer elapsed
    if (
        new_state.paused
        and new_state.paused_until is not None
        and today >= new_state.paused_until
    ):
        auto_id = f"auto-unpause-{new_state.paused_since.isoformat() if new_state.paused_since else today.isoformat()}"
        if auto_id not in applied_task_ids:
            handler = ACTION_HANDLERS["unset_pause"]
            result = handler(new_state, todoist_task_id=auto_id, today=today)
            new_state = result.new_state
            pending_entries.append(result.log_entry)
            applied_task_ids.add(auto_id)
            summary.auto_unpaused = True
            summary.mutations_applied += 1
            summary.messages.append(f"auto-unpause: {result.user_message}")

    # 2. State-review parent: find newest in cache, fetch sub-tasks, dispatch.
    review_client = None
    if todoist_token and project_id and review_factory is not None:
        try:
            review_client = review_factory(token=todoist_token, project_id=project_id)
        except Exception as e:
            logger.warning("could not instantiate review client: %s", e)
            review_client = None

    newest_parent = _find_newest_state_review_parent(cache)
    if newest_parent and review_client is not None:
        parent_task_id = newest_parent.get("todoist_task_id", "")
        if parent_task_id and not str(parent_task_id).startswith("DRY-RUN"):
            try:
                subtasks = review_client.get_subtasks(parent_task_id)
            except Exception as e:
                logger.warning("review subtask fetch failed: %s", e)
                subtasks = []
            ext_id_by_task_id = _index_subtask_cache_entries(cache)
            for sub in subtasks:
                if not sub.is_completed:
                    continue
                if sub.id in applied_task_ids:
                    continue
                cache_entry_ext_id = ext_id_by_task_id.get(sub.id)
                if cache_entry_ext_id is None:
                    continue
                cache_entry = cache[cache_entry_ext_id]
                action_spec = cache_entry.get("state_review_action") or {}
                if not action_spec:
                    continue
                comment_value: int | None = None
                if action_spec.get("type") == "increment_counter":
                    try:
                        comment_value = _parse_counter_comment(
                            review_client.get_first_comment(sub.id)
                        )
                    except Exception as e:
                        logger.warning("comment fetch failed for %s: %s", sub.id, e)
                        comment_value = None
                try:
                    result = _dispatch(
                        action_spec,
                        new_state,
                        syllabus,
                        log_entries + pending_entries,
                        sub.id,
                        today,
                        comment_value=comment_value,
                    )
                except Exception as e:
                    logger.error("dispatch failed for sub-task %s: %s", sub.id, e)
                    summary.mutations_skipped += 1
                    continue
                if result is None:
                    summary.mutations_skipped += 1
                    continue
                new_state = result.new_state
                pending_entries.append(result.log_entry)
                applied_task_ids.add(sub.id)
                summary.mutations_applied += 1
                summary.messages.append(result.user_message)

    # 3. Persistent emergency-pause / resume tasks.
    completion_client = None
    if todoist_token and project_id and completion_factory is not None:
        try:
            completion_client = completion_factory(
                token=todoist_token,
                project_id=project_id,
            )
        except Exception as e:
            logger.warning("could not instantiate completion client for persistent: %s", e)
            completion_client = None

    persistent_entries = [
        (ext_id, entry)
        for ext_id, entry in cache.items()
        if entry.get("persistent_action") and not entry.get("persistent_consumed")
    ]
    persistent_task_ids = [
        str(entry["todoist_task_id"])
        for _, entry in persistent_entries
        if entry.get("todoist_task_id")
        and not str(entry["todoist_task_id"]).startswith("DRY-RUN")
    ]
    completion_status: dict[str, bool] = {}
    if completion_client is not None and persistent_task_ids:
        try:
            completion_status = completion_client.get_completion_status(persistent_task_ids)
        except Exception as e:
            logger.warning("persistent completion lookup failed: %s", e)
            completion_status = {}

    for ext_id_str, entry in persistent_entries:
        task_id = str(entry.get("todoist_task_id") or "")
        if not task_id or task_id.startswith("DRY-RUN"):
            continue
        if not completion_status.get(task_id):
            continue
        if task_id in applied_task_ids:
            entry["persistent_consumed"] = True
            continue
        action_spec = entry.get("persistent_action") or {}
        try:
            result = _dispatch(
                action_spec,
                new_state,
                syllabus,
                log_entries + pending_entries,
                task_id,
                today,
            )
        except Exception as e:
            logger.error("persistent dispatch failed for %s: %s", task_id, e)
            summary.mutations_skipped += 1
            continue
        if result is None:
            summary.mutations_skipped += 1
            continue
        new_state = result.new_state
        pending_entries.append(result.log_entry)
        applied_task_ids.add(task_id)
        summary.mutations_applied += 1
        summary.messages.append(result.user_message)
        entry["persistent_consumed"] = True
        summary.persistent_recreated.append(ext_id_str)

    # 4. Atomic write: state.yaml first, then state_log append.
    if pending_entries or new_state is not state:
        save_state(state_path, new_state)
        if pending_entries:
            save_state_log(state_log_path, log_entries + pending_entries)

    return new_state, summary


def _find_newest_state_review_parent(cache: dict[str, dict[str, Any]]) -> dict[str, Any] | None:
    candidates = [
        entry for entry in cache.values()
        if entry.get("state_review_parent")
        and entry.get("todoist_task_id")
    ]
    if not candidates:
        return None
    candidates.sort(key=lambda e: str(e.get("created_at", "")), reverse=True)
    return candidates[0]


def _index_subtask_cache_entries(
    cache: dict[str, dict[str, Any]],
) -> dict[str, str]:
    """Map sub-task todoist_task_id -> cache key (external_id)."""
    out: dict[str, str] = {}
    for ext_id_str, entry in cache.items():
        if entry.get("state_review_action") and entry.get("todoist_task_id"):
            out[str(entry["todoist_task_id"])] = ext_id_str
    return out


# --- persistent task creation ----------------------------------------------


def persistent_pause_external_id(today: date) -> str:
    """ext_id for emergency-pause; versioned by today so each consumption
    rolls over to a fresh cache key per spec."""
    return external_id("persistent-emergency-pause", today)


def persistent_resume_external_id(today: date) -> str:
    return external_id("persistent-resume", today)


def open_persistent_cache_entry(
    cache: dict[str, dict[str, Any]],
    category: str,
) -> dict[str, Any] | None:
    for entry in cache.values():
        if (
            entry.get("persistent_category") == category
            and not entry.get("persistent_consumed")
        ):
            return entry
    return None
