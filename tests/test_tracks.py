"""Tests for src/tracks.py: gate predicates + lifecycle transitions.

Both functions are pure; no fixtures load the engine.
"""

from __future__ import annotations

from datetime import date

import pytest
from zoneinfo import ZoneInfo

from src.state import State
from src.syllabus import TrackDeclaration
from src.tracks import (
    LifecycleTransition,
    compute_lifecycle_transitions,
    evaluate_gates,
    expected_position,
    slug_of,
)


def _state(**overrides):
    base = dict(
        start_date=date(2026, 5, 1),
        timezone=ZoneInfo("UTC"),
        phase=1,
        month=1,
        current_module=1,
        current_book="",
    )
    base.update(overrides)
    return State(**base)


# --- slug ---

def test_slug_of_basic():
    assert slug_of("Courses", "boot.dev backend path") == "courses-boot-dev-backend-path"


def test_slug_strips_leading_trailing_hyphens():
    assert slug_of("--Courses--", "--X--") == "courses-x"


# --- gates ---

def test_gates_empty_list_passes():
    s = _state()
    ok, reason = evaluate_gates([], s)
    assert ok is True
    assert reason is None


def test_track_gate_passes_when_state_current():
    s = _state(learning_tracks={"Courses": {"X": "current"}})
    gates = [{"type": "track", "category": "Courses", "item": "X"}]
    ok, _ = evaluate_gates(gates, s)
    assert ok is True


def test_track_gate_fails_when_state_done():
    s = _state(learning_tracks={"Courses": {"X": "done"}})
    gates = [{"type": "track", "category": "Courses", "item": "X"}]
    ok, reason = evaluate_gates(gates, s)
    assert ok is False
    assert "track" in reason


def test_track_gate_custom_states_set():
    s = _state(learning_tracks={"Courses": {"X": "done"}})
    gates = [{"type": "track", "category": "Courses", "item": "X", "states": ["done"]}]
    ok, _ = evaluate_gates(gates, s)
    assert ok is True


def test_track_gate_fails_when_missing():
    s = _state(learning_tracks={})
    gates = [{"type": "track", "category": "Courses", "item": "X"}]
    ok, _ = evaluate_gates(gates, s)
    assert ok is False


def test_module_eq_gate():
    s = _state(current_module=5)
    assert evaluate_gates([{"type": "module_eq", "value": 5}], s)[0] is True
    assert evaluate_gates([{"type": "module_eq", "value": 4}], s)[0] is False


def test_module_gte_gate():
    s = _state(current_module=5)
    assert evaluate_gates([{"type": "module_gte", "value": 3}], s)[0] is True
    assert evaluate_gates([{"type": "module_gte", "value": 5}], s)[0] is True
    assert evaluate_gates([{"type": "module_gte", "value": 6}], s)[0] is False


def test_module_lte_gate():
    s = _state(current_module=5)
    assert evaluate_gates([{"type": "module_lte", "value": 10}], s)[0] is True
    assert evaluate_gates([{"type": "module_lte", "value": 5}], s)[0] is True
    assert evaluate_gates([{"type": "module_lte", "value": 4}], s)[0] is False


def test_gates_anded():
    s = _state(current_module=5, learning_tracks={"Courses": {"X": "current"}})
    gates = [
        {"type": "track", "category": "Courses", "item": "X"},
        {"type": "module_gte", "value": 3},
    ]
    assert evaluate_gates(gates, s)[0] is True
    # Flip module_gte to fail
    gates[1] = {"type": "module_gte", "value": 10}
    assert evaluate_gates(gates, s)[0] is False


def test_unknown_gate_type_fails_closed():
    s = _state()
    ok, reason = evaluate_gates([{"type": "phase_eq", "value": 1}], s)
    assert ok is False
    assert "unknown gate type" in reason


# --- expected_position ---

def test_expected_position_no_months_returns_pre_start():
    decl = TrackDeclaration(title="X", category="C", phase=1, months=None)
    assert expected_position(decl, 1) == "pre_start"
    assert expected_position(decl, 99) == "pre_start"


def test_expected_position_within_range():
    decl = TrackDeclaration(title="X", category="C", phase=1, months=(5, 7))
    assert expected_position(decl, 4) == "pre_start"
    assert expected_position(decl, 5) == "current"
    assert expected_position(decl, 7) == "current"
    assert expected_position(decl, 8) == "past_end"


# --- compute_lifecycle_transitions ---

def _decl(title, category, months=None):
    return TrackDeclaration(title=title, category=category, phase=1, months=months)


def test_lifecycle_not_started_to_current():
    s = _state(learning_tracks={})
    decl = _decl("X", "C", months=(3, 5))
    transitions = compute_lifecycle_transitions(s, [decl], derived_month=3, applied_task_ids=set())
    assert len(transitions) == 1
    t = transitions[0]
    assert t.from_state == "not_started"
    assert t.to_state == "current"
    assert t.todoist_task_id == "auto-track-c-x-start-3"


def test_lifecycle_current_to_done():
    s = _state(learning_tracks={"C": {"X": "current"}})
    decl = _decl("X", "C", months=(3, 5))
    transitions = compute_lifecycle_transitions(s, [decl], derived_month=6, applied_task_ids=set())
    assert len(transitions) == 1
    t = transitions[0]
    assert t.from_state == "current"
    assert t.to_state == "done"
    assert t.todoist_task_id == "auto-track-c-x-end-5"


def test_lifecycle_not_started_past_end_noop():
    """Owner skipped the window entirely; engine does NOT auto-flip."""
    s = _state(learning_tracks={})
    decl = _decl("X", "C", months=(3, 5))
    transitions = compute_lifecycle_transitions(s, [decl], derived_month=10, applied_task_ids=set())
    assert transitions == []


def test_lifecycle_owner_current_early_no_transition():
    """Owner started early (before window). Engine respects, no-op."""
    s = _state(learning_tracks={"C": {"X": "current"}})
    decl = _decl("X", "C", months=(3, 5))
    transitions = compute_lifecycle_transitions(s, [decl], derived_month=1, applied_task_ids=set())
    assert transitions == []


def test_lifecycle_done_never_reopens():
    s = _state(learning_tracks={"C": {"X": "done"}})
    decl = _decl("X", "C", months=(3, 5))
    transitions = compute_lifecycle_transitions(s, [decl], derived_month=4, applied_task_ids=set())
    assert transitions == []


def test_lifecycle_no_months_never_auto():
    s = _state(learning_tracks={})
    decl = _decl("X", "C", months=None)
    transitions = compute_lifecycle_transitions(s, [decl], derived_month=5, applied_task_ids=set())
    assert transitions == []


def test_lifecycle_idempotency_skips_applied():
    s = _state(learning_tracks={})
    decl = _decl("X", "C", months=(3, 5))
    applied = {"auto-track-c-x-start-3"}
    transitions = compute_lifecycle_transitions(s, [decl], derived_month=3, applied_task_ids=applied)
    assert transitions == []


def test_lifecycle_multiple_declarations():
    s = _state(learning_tracks={"C": {"Y": "current"}})
    decls = [
        _decl("X", "C", months=(3, 5)),
        _decl("Y", "C", months=(3, 5)),
        _decl("Z", "C", months=(3, 5)),
    ]
    transitions = compute_lifecycle_transitions(s, decls, derived_month=6, applied_task_ids=set())
    titles = {t.title for t in transitions}
    # X stays not_started past end (no-op), Y goes done, Z stays not_started.
    assert titles == {"Y"}
    assert transitions[0].to_state == "done"
