import shutil
from dataclasses import replace
from datetime import date, timedelta
from pathlib import Path

import pytest
import yaml

from src.lw.status_logic import CurriculumCtx, EngineCtx, load_engine
from src.state import SyllabusState, load_shared_state, load_syllabus_state
from src.state_review import load_state_log

REPO = Path(__file__).resolve().parents[1]


def _mk_cur(module: int = 1) -> CurriculumCtx:
    state = SyllabusState(
        start_date=date(2026, 8, 5), phase=1, month=1,
        current_module=module, current_book="Book A",
    )
    return CurriculumCtx(entry=None, state=state, syllabus=None, templates=[])


def test_build_questions_filters_show_if_and_resolves_titles():
    from src.lw.review_logic import build_questions

    ctx = load_engine(REPO)
    cur = ctx.per_key["marketplace-builder"]
    assert cur.state.current_module == 1  # not the last of 16 rungs

    questions = build_questions(cur, date(2026, 8, 9))
    assert len(questions) == 7  # no book question: mb books are pull-only

    advance_q = next(q for q in questions if q.sub.action["type"] == "advance_module")
    assert "Rung" in advance_q.sub.title
    assert "2: Crash-safe persistence" in advance_q.sub.title


def test_counter_questions_flagged():
    from src.lw.review_logic import build_questions

    ctx = load_engine(REPO)
    cur = ctx.per_key["marketplace-builder"]
    questions = build_questions(cur, date(2026, 8, 9))

    anki_q = next(q for q in questions if "How many Anki cards" in q.sub.title)
    assert anki_q.wants_count is True

    advance_q = next(q for q in questions if q.sub.action["type"] == "advance_module")
    assert advance_q.wants_count is False

    # input: yesno renders an increment_counter as Yes/No
    cluster_q = next(q for q in questions if "learn cluster" in q.sub.title)
    assert cluster_q.sub.action["type"] == "increment_counter"
    assert cluster_q.wants_count is False


def test_apply_answers_advances_module_and_writes_log(tmp_path: Path):
    from src.lw.review_logic import apply_answers, build_questions

    real_ctx = load_engine(REPO)
    real_cur = real_ctx.per_key["marketplace-builder"]

    (tmp_path / "state").mkdir()
    shutil.copy(REPO / "state" / "marketplace-builder.yaml", tmp_path / "state" / "marketplace-builder.yaml")
    shutil.copy(REPO / "state" / "shared.yaml", tmp_path / "state" / "shared.yaml")

    entry = replace(real_cur.entry, state_file=Path("state/marketplace-builder.yaml"))
    state = load_syllabus_state(tmp_path / "state" / "marketplace-builder.yaml")
    shared = load_shared_state(tmp_path / "state" / "shared.yaml")
    cur = CurriculumCtx(entry, state, real_cur.syllabus, real_cur.templates)
    ctx = EngineCtx(real_ctx.cfg, shared, {"marketplace-builder": cur}, tmp_path)

    today = date(2026, 8, 9)
    questions = build_questions(cur, today)
    advance_q = next(q for q in questions if q.sub.action["type"] == "advance_module")

    messages = apply_answers(ctx, "marketplace-builder", [(advance_q, True)], today)

    assert cur.state.current_module == 2
    reloaded = load_syllabus_state(tmp_path / "state" / "marketplace-builder.yaml")
    assert reloaded.current_module == 2

    log_entries = load_state_log(tmp_path / "state" / "marketplace-builder_state_log.yaml")
    assert len(log_entries) == 1
    assert log_entries[0]["todoist_task_id"].startswith("lw-review-")
    assert messages


def _write_meta(meta_path: Path, deadline: str, outcome=None, extensions=None):
    meta_path.write_text(
        yaml.safe_dump({
            "rung": 1,
            "option": "a",
            "slug": "rung-01a-expression-calculator",
            "picked_at": "2026-08-01",
            "code_path": "/tmp/rung-01a",
            "deadline": deadline,
            "extensions": extensions or [],
            "outcome": outcome,
        }, sort_keys=False),
        encoding="utf-8",
    )


def test_deadline_gate_none_before_deadline_and_present_after(tmp_path: Path):
    from src.lw.review_logic import build_deadline_gate

    today = date(2026, 8, 20)
    rung_dir = tmp_path / "ladder" / "rung-01a-expression-calculator"
    rung_dir.mkdir(parents=True)
    meta_path = rung_dir / "meta.yaml"
    cur = _mk_cur(module=1)

    _write_meta(meta_path, (today - timedelta(days=1)).isoformat())
    gate = build_deadline_gate(tmp_path, cur, today)
    assert gate is not None
    assert gate.meta["rung"] == 1

    _write_meta(meta_path, (today + timedelta(days=1)).isoformat())
    assert build_deadline_gate(tmp_path, cur, today) is None

    _write_meta(meta_path, (today - timedelta(days=1)).isoformat(), outcome="shipped")
    assert build_deadline_gate(tmp_path, cur, today) is None


def test_apply_gate_extend_requires_reason_and_appends(tmp_path: Path):
    from src.lw.review_logic import DeadlineGate, apply_gate

    today = date(2026, 8, 20)
    rung_dir = tmp_path / "ladder" / "rung-01a-expression-calculator"
    rung_dir.mkdir(parents=True)
    meta_path = rung_dir / "meta.yaml"
    _write_meta(meta_path, (today - timedelta(days=1)).isoformat())
    meta = yaml.safe_load(meta_path.read_text(encoding="utf-8"))
    gate = DeadlineGate(meta_path, meta)

    outcome = apply_gate(gate, "extend", reason="sick week", extra_days=7, today=today)
    assert outcome.advance is False

    reloaded = yaml.safe_load(meta_path.read_text(encoding="utf-8"))
    assert reloaded["extensions"][-1]["new_deadline"] == (today + timedelta(days=7)).isoformat()
    assert reloaded["extensions"][-1]["reason"] == "sick week"
    assert reloaded["outcome"] is None

    with pytest.raises(ValueError):
        apply_gate(gate, "extend", reason="", extra_days=7, today=today)


def test_preview_gate_outcome_does_not_touch_disk(tmp_path: Path):
    """lw review's TUI calls preview_gate_outcome the moment a gate choice is
    picked (to pre-check the advance question), before the user confirms.
    Quitting before confirm must leave meta.yaml untouched — preview_gate_outcome
    takes no gate/meta_path at all, so it structurally cannot write."""
    from src.lw.review_logic import preview_gate_outcome

    today = date(2026, 8, 20)
    rung_dir = tmp_path / "ladder" / "rung-01a-expression-calculator"
    rung_dir.mkdir(parents=True)
    meta_path = rung_dir / "meta.yaml"
    _write_meta(meta_path, (today - timedelta(days=1)).isoformat())
    before = meta_path.read_text(encoding="utf-8")

    outcome = preview_gate_outcome("shipped", today=today)
    assert outcome.advance is True
    outcome = preview_gate_outcome("extend", reason="sick week", extra_days=7, today=today)
    assert outcome.advance is False
    assert meta_path.read_text(encoding="utf-8") == before

    with pytest.raises(ValueError):
        preview_gate_outcome("extend", reason="", extra_days=7, today=today)
    assert meta_path.read_text(encoding="utf-8") == before


def test_forced_advance_answer_only_forces_advance_module_on_fail_forward():
    from src.lw.review_logic import Question, forced_advance_answer
    from src.templates import SubtaskSpec

    advance_q = Question(
        sub=SubtaskSpec(title="advance", action={"type": "advance_module"}, show_if=[]),
        wants_count=False,
    )
    other_q = Question(
        sub=SubtaskSpec(title="anki", action={"type": "increment_counter"}, show_if=[]),
        wants_count=True,
    )

    assert forced_advance_answer(advance_q, gate_advance=True) is True
    assert forced_advance_answer(advance_q, gate_advance=False) is None
    assert forced_advance_answer(other_q, gate_advance=True) is None


def test_apply_gate_failed_move_on_advances_and_logs(tmp_path: Path):
    from src.lw.review_logic import DeadlineGate, apply_gate

    today = date(2026, 8, 20)
    rung_dir = tmp_path / "ladder" / "rung-01a-expression-calculator"
    rung_dir.mkdir(parents=True)
    meta_path = rung_dir / "meta.yaml"
    _write_meta(meta_path, (today - timedelta(days=1)).isoformat())
    meta = yaml.safe_load(meta_path.read_text(encoding="utf-8"))
    gate = DeadlineGate(meta_path, meta)

    outcome = apply_gate(gate, "failed_move_on", today=today)
    assert outcome.advance is True
    reloaded = yaml.safe_load(meta_path.read_text(encoding="utf-8"))
    assert reloaded["outcome"] == "failed"
    assert reloaded["failures"][-1] == {"date": today.isoformat(), "decision": "move_on"}

    # shipped resolves the same way — advance=True contract.
    _write_meta(meta_path, (today - timedelta(days=1)).isoformat())
    meta2 = yaml.safe_load(meta_path.read_text(encoding="utf-8"))
    gate2 = DeadlineGate(meta_path, meta2)
    outcome2 = apply_gate(gate2, "shipped", today=today)
    assert outcome2.advance is True
    assert yaml.safe_load(meta_path.read_text(encoding="utf-8"))["outcome"] == "shipped"


def test_apply_gate_failed_retry_keeps_rung_open_with_new_deadline(tmp_path: Path):
    from src.lw.review_logic import DeadlineGate, apply_gate, build_deadline_gate, preview_gate_outcome

    today = date(2026, 8, 20)
    rung_dir = tmp_path / "ladder" / "rung-01a-expression-calculator"
    rung_dir.mkdir(parents=True)
    meta_path = rung_dir / "meta.yaml"
    _write_meta(meta_path, (today - timedelta(days=1)).isoformat())
    meta = yaml.safe_load(meta_path.read_text(encoding="utf-8"))
    gate = DeadlineGate(meta_path, meta)

    outcome = apply_gate(gate, "failed_retry", extra_days=7, today=today)
    assert outcome.advance is False

    reloaded = yaml.safe_load(meta_path.read_text(encoding="utf-8"))
    assert reloaded["outcome"] is None
    assert reloaded["failures"][-1] == {"date": today.isoformat(), "decision": "retry"}
    assert reloaded["extensions"][-1]["new_deadline"] == (today + timedelta(days=7)).isoformat()
    assert reloaded["extensions"][-1]["reason"] == "failed — retrying"

    # Rung stays open: gate is quiet until the retry deadline, fires again after it.
    cur = _mk_cur(module=1)
    assert build_deadline_gate(tmp_path, cur, today) is None
    assert build_deadline_gate(tmp_path, cur, today + timedelta(days=8)) is not None

    # retry demands a positive day count, and validation is pure (no disk write).
    before = meta_path.read_text(encoding="utf-8")
    with pytest.raises(ValueError):
        preview_gate_outcome("failed_retry", extra_days=0, today=today)
    with pytest.raises(ValueError):
        apply_gate(DeadlineGate(meta_path, reloaded), "failed_retry", extra_days=0, today=today)
    assert meta_path.read_text(encoding="utf-8") == before


def test_is_review_time_only_on_the_state_review_day():
    from datetime import date as _date
    from pathlib import Path as _Path

    from src.lw.review_logic import is_review_time, review_day
    from src.lw.status_logic import load_engine

    ctx = load_engine(_Path(__file__).resolve().parents[1])
    cur = ctx.per_key["marketplace-builder"]
    assert review_day(cur) == "saturday"
    assert is_review_time(cur, _date(2026, 8, 6)) is False  # Thursday
    assert is_review_time(cur, _date(2026, 8, 8)) is True  # Saturday


def test_due_monthly_reflections_only_on_firing_day():
    from src.lw.review_logic import due_monthly_reflections

    ctx = load_engine(REPO)
    # 2026-09-26 is the last Saturday of September: the devops-ready
    # monthly retrospective (a reflection-stub template) fires.
    due = due_monthly_reflections(ctx, date(2026, 9, 26))
    assert any(t.key == "devops-ready" and t.cadence == "monthly" for t in due)
    # A non-last Saturday fires no monthly reflection.
    assert due_monthly_reflections(load_engine(REPO), date(2026, 9, 19)) == []
