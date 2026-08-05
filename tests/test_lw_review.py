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
    assert len(questions) == 7

    advance_q = next(q for q in questions if q.sub.action["type"] == "advance_module")
    assert "Rung" in advance_q.sub.title
    assert "2" in advance_q.sub.title


def test_counter_questions_flagged():
    from src.lw.review_logic import build_questions

    ctx = load_engine(REPO)
    cur = ctx.per_key["marketplace-builder"]
    questions = build_questions(cur, date(2026, 8, 9))

    anki_q = next(q for q in questions if "Anki cards added" in q.sub.title)
    assert anki_q.wants_count is True

    advance_q = next(q for q in questions if q.sub.action["type"] == "advance_module")
    assert advance_q.wants_count is False


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


def test_apply_gate_failed_is_fail_forward(tmp_path: Path):
    from src.lw.review_logic import DeadlineGate, apply_gate

    today = date(2026, 8, 20)
    rung_dir = tmp_path / "ladder" / "rung-01a-expression-calculator"
    rung_dir.mkdir(parents=True)
    meta_path = rung_dir / "meta.yaml"
    _write_meta(meta_path, (today - timedelta(days=1)).isoformat())
    meta = yaml.safe_load(meta_path.read_text(encoding="utf-8"))
    gate = DeadlineGate(meta_path, meta)

    outcome = apply_gate(gate, "failed", today=today)
    assert outcome.advance is True
    reloaded = yaml.safe_load(meta_path.read_text(encoding="utf-8"))
    assert reloaded["outcome"] == "failed"

    # shipped is fail-forward too — same advance=True contract.
    _write_meta(meta_path, (today - timedelta(days=1)).isoformat())
    meta2 = yaml.safe_load(meta_path.read_text(encoding="utf-8"))
    gate2 = DeadlineGate(meta_path, meta2)
    outcome2 = apply_gate(gate2, "shipped", today=today)
    assert outcome2.advance is True
    assert yaml.safe_load(meta_path.read_text(encoding="utf-8"))["outcome"] == "shipped"
