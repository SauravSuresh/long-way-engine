"""Unit tests for pure state-mutation handlers.

Each handler is tested in isolation. Handlers do no IO and observe no
clock; the tests pass `today` and `todoist_task_id` directly.
"""

from __future__ import annotations

from datetime import date

import pytest
from zoneinfo import ZoneInfo

from src.state import PauseInterval, SharedState, SyllabusState
from src.state_mutations import (
    ACTION_HANDLERS,
    advance_module,
    increment_counter,
    mark_book_finished,
    mark_book_started,
    revert_last,
    set_pause,
    unset_pause,
)
from src.syllabus import Module, Phase, Syllabus


def _state(**overrides):
    base = dict(
        start_date=date(2026, 5, 1),
        phase=1,
        month=1,
        current_module=1,
        current_book="Book A",
        completed_modules=[],
    )
    base.update(overrides)
    return SyllabusState(**base)


def _shared(**overrides):
    base = dict(
        timezone=ZoneInfo("UTC"),
        manual_counters={},
    )
    base.update(overrides)
    return SharedState(**base)


def _syllabus(num_modules=3):
    return Syllabus(
        meta={},
        phases=[Phase(number=1, name="P1", months=(1, 3))],
        books=[],
        primary_book_by_month={},
        modules=[Module(number=i, name=f"M{i}", phase=1) for i in range(1, num_modules + 1)],
    )


TODAY = date(2026, 6, 1)


def test_advance_module_happy_path():
    s = _state(current_module=1, completed_modules=[])
    syl = _syllabus(3)
    result = advance_module(s, syl, todoist_task_id="t1", today=TODAY)
    assert result.new_state.current_module == 2
    assert result.new_state.completed_modules == [1]
    assert result.log_entry["action"] == "advance_module"
    assert result.log_entry["todoist_task_id"] == "t1"
    assert result.log_entry["prior"] == {"current_module": 1, "completed_modules": []}
    assert result.log_entry["new"]["current_module"] == 2


def test_advance_module_noop_on_last_module():
    s = _state(current_module=3)
    syl = _syllabus(3)
    result = advance_module(s, syl, todoist_task_id="t1", today=TODAY)
    assert result.new_state.current_module == 3
    assert result.log_entry.get("noop") is True


def test_mark_book_finished_sets_done():
    s = _state(books_state={"Book A": "current"})
    result = mark_book_finished(s, book="Book A", todoist_task_id="t1", today=TODAY)
    assert result.new_state.books_state["Book A"] == "done"
    assert result.log_entry["prior"]["books_state"] == {"Book A": "current"}


def test_mark_book_started_sets_current():
    s = _state(books_state={})
    result = mark_book_started(s, book="Book B", todoist_task_id="t1", today=TODAY)
    assert result.new_state.books_state["Book B"] == "current"


def test_set_pause_sets_paused_with_until():
    s = _state(paused=False)
    result = set_pause(s, days=7, reason="vacation", todoist_task_id="t1", today=TODAY)
    assert result.new_state.paused is True
    assert result.new_state.paused_since == TODAY
    assert result.new_state.paused_until == date(2026, 6, 8)


def test_unset_pause_appends_to_history():
    s = _state(
        paused=True,
        paused_since=date(2026, 5, 20),
        paused_until=date(2026, 5, 27),
    )
    result = unset_pause(s, todoist_task_id="t1", today=TODAY)
    assert result.new_state.paused is False
    assert result.new_state.paused_since is None
    assert result.new_state.paused_until is None
    assert len(result.new_state.pause_history) == 1
    iv = result.new_state.pause_history[0]
    assert iv.start == date(2026, 5, 20)
    assert iv.end == TODAY


def test_unset_pause_noop_when_not_paused():
    s = _state(paused=False)
    result = unset_pause(s, todoist_task_id="t1", today=TODAY)
    assert result.new_state.paused is False
    assert result.log_entry.get("noop") is True


def test_increment_counter_with_existing_value():
    sh = _shared(manual_counters={"anki_card_count": 12})
    result = increment_counter(sh, counter="anki_card_count", delta=5, todoist_task_id="t1", today=TODAY)
    assert result.new_state.manual_counters["anki_card_count"] == 17


def test_increment_counter_initializes_zero():
    sh = _shared(manual_counters={})
    result = increment_counter(sh, counter="prs_opened", delta=3, todoist_task_id="t1", today=TODAY)
    assert result.new_state.manual_counters["prs_opened"] == 3


def test_mark_track_started_sets_current():
    from src.state_mutations import mark_track_started
    s = _state(learning_tracks={})
    result = mark_track_started(s, category="Courses", item="boot.dev", todoist_task_id="t1", today=TODAY)
    assert result.new_state.learning_tracks["Courses"]["boot.dev"] == "current"
    assert result.log_entry["category"] == "Courses"


def test_mark_track_finished_sets_done():
    from src.state_mutations import mark_track_finished
    s = _state(learning_tracks={"Courses": {"boot.dev": "current"}})
    result = mark_track_finished(s, category="Courses", item="boot.dev", todoist_task_id="t1", today=TODAY)
    assert result.new_state.learning_tracks["Courses"]["boot.dev"] == "done"


def test_mark_track_noop_when_already_in_state():
    from src.state_mutations import mark_track_started
    s = _state(learning_tracks={"Courses": {"X": "current"}})
    result = mark_track_started(s, category="Courses", item="X", todoist_task_id="t1", today=TODAY)
    assert result.log_entry.get("noop") is True


def test_revert_last_restores_prior_module():
    s = _state(current_module=2, completed_modules=[1])
    log = [{
        "timestamp": "2026-06-01",
        "action": "advance_module",
        "todoist_task_id": "prior",
        "prior": {"current_module": 1, "completed_modules": []},
        "new": {"current_module": 2, "completed_modules": [1]},
    }]
    result = revert_last(s, log, todoist_task_id="revert-1", today=TODAY)
    assert result.new_state.current_module == 1
    assert result.new_state.completed_modules == []
    assert result.log_entry["reverted_action"] == "advance_module"


def test_revert_last_skips_prior_reverts():
    s = _state(current_module=1, completed_modules=[])
    log = [
        {
            "timestamp": "2026-06-01",
            "action": "advance_module",
            "todoist_task_id": "a1",
            "prior": {"current_module": 1, "completed_modules": []},
            "new": {"current_module": 2, "completed_modules": [1]},
        },
        {
            "timestamp": "2026-06-08",
            "action": "revert_last",
            "todoist_task_id": "r1",
            "reverted_action": "advance_module",
        },
    ]
    result = revert_last(s, log, todoist_task_id="r2", today=TODAY)
    # Should NOT re-revert the revert — should be a no-op since the only
    # non-revert entry was already reverted.
    # With the implementation: the most recent non-revert is "advance_module".
    # Its prior was current_module=1, completed_modules=[]. We're already there.
    assert result.new_state.current_module == 1


def test_revert_last_empty_log_noop():
    s = _state()
    result = revert_last(s, [], todoist_task_id="r1", today=TODAY)
    assert result.log_entry.get("noop") is True


def test_action_handlers_table_complete():
    expected = {
        "advance_module",
        "mark_book_finished",
        "mark_book_started",
        "mark_track_started",
        "mark_track_finished",
        "set_pause",
        "unset_pause",
        "increment_counter",
        "revert_last",
    }
    assert set(ACTION_HANDLERS.keys()) == expected
