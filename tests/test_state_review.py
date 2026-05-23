"""Orchestrator tests with a mocked TodoistReviewClient + completion client.

Exercises: idempotency (same task_id applied once), auto-unpause on
elapsed paused_until, persistent task consumption, increment_counter
comment parsing.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, timedelta
from pathlib import Path

import pytest
import yaml
from zoneinfo import ZoneInfo

from src.state import State, load_state, save_state
from src.state_review import (
    evaluate_show_if,
    load_state_log,
    persistent_pause_external_id,
    run_state_review_phase,
    save_state_log,
)
from src.syllabus import Module, Phase, Syllabus


@dataclass
class FakeSubtask:
    id: str
    content: str
    is_completed: bool
    comment_count: int = 0
    parent_id: str = "parent-1"


class FakeReviewClient:
    def __init__(self, subtasks=None, comment=None, **_kwargs):
        self._subtasks = subtasks or []
        self._comment = comment

    def get_subtasks(self, parent_task_id):
        return list(self._subtasks)

    def get_first_comment(self, task_id):
        return self._comment

    def find_task_by_external_id(self, external_id):
        return None


class FakeCompletionClient:
    def __init__(self, completed=None, **_kwargs):
        self._completed = set(completed or [])

    def get_completion_status(self, task_ids):
        return {tid: tid in self._completed for tid in task_ids}


def _state(**overrides):
    base = dict(
        start_date=date(2026, 5, 1),
        timezone=ZoneInfo("UTC"),
        phase=1,
        month=1,
        current_module=1,
        current_book="Book A",
    )
    base.update(overrides)
    return State(**base)


def _syllabus(tracks=None):
    return Syllabus(
        meta={},
        phases=[Phase(number=1, name="P1", months=(1, 12))],
        books=[],
        primary_book_by_month={},
        modules=[Module(number=i, name=f"M{i}", phase=1) for i in range(1, 5)],
        tracks=tracks or [],
    )


def _config():
    """Minimal Config with just the fields run_state_review_phase reads
    via attribute access in this test surface."""
    from src.config import Config, DashboardConfig, TodoistConfig

    return Config(
        todoist=TodoistConfig(project_id="p1"),
        ritual_times={},
        sunday_off=True,
        dashboard=DashboardConfig(github_username="x", repo_name="y"),
        todoist_token="tok",
    )


def test_advance_module_via_sub_task_dispatches(tmp_path: Path):
    cache = {
        "parent-ext": {
            "todoist_task_id": "parent-1",
            "created_at": "2026-06-07T00:00:00+00:00",
            "template_id": "weekly-state-review",
            "due_date": "2026-06-07",
            "state_review_parent": True,
        },
        "sub-ext-0": {
            "todoist_task_id": "sub-advance",
            "state_review_action": {"type": "advance_module"},
        },
    }
    state = _state()
    state_path = tmp_path / "state.yaml"
    save_state(state_path, state)
    log_path = tmp_path / "state_log.yaml"

    subtasks = [FakeSubtask(id="sub-advance", content="advance", is_completed=True)]
    new_state, summary = run_state_review_phase(
        config=_config(),
        state=state,
        syllabus=_syllabus(),
        today=date(2026, 6, 8),
        cache=cache,
        state_path=state_path,
        state_log_path=log_path,
        review_factory=lambda **kw: FakeReviewClient(subtasks=subtasks),
        completion_factory=lambda **kw: FakeCompletionClient(),
        todoist_token="tok",
        project_id="p1",
    )

    assert new_state.current_module == 2
    assert summary.mutations_applied == 1
    log_entries = load_state_log(log_path)
    assert len(log_entries) == 1
    assert log_entries[0]["action"] == "advance_module"
    assert log_entries[0]["todoist_task_id"] == "sub-advance"


def test_idempotency_same_task_applied_once(tmp_path: Path):
    cache = {
        "parent-ext": {
            "todoist_task_id": "parent-1",
            "state_review_parent": True,
            "created_at": "2026-06-07T00:00:00+00:00",
        },
        "sub-ext-0": {
            "todoist_task_id": "sub-advance",
            "state_review_action": {"type": "advance_module"},
        },
    }
    state = _state()
    state_path = tmp_path / "state.yaml"
    save_state(state_path, state)
    log_path = tmp_path / "state_log.yaml"

    subtasks = [FakeSubtask(id="sub-advance", content="advance", is_completed=True)]
    # First run: applies.
    state_v1, summary1 = run_state_review_phase(
        config=_config(),
        state=state,
        syllabus=_syllabus(),
        today=date(2026, 6, 8),
        cache=cache,
        state_path=state_path,
        state_log_path=log_path,
        review_factory=lambda **kw: FakeReviewClient(subtasks=subtasks),
        completion_factory=lambda **kw: FakeCompletionClient(),
        todoist_token="tok",
        project_id="p1",
    )
    assert summary1.mutations_applied == 1
    assert state_v1.current_module == 2

    # Second run: same sub-task still completed in Todoist, but already
    # in the log → MUST NOT re-apply.
    state_v2, summary2 = run_state_review_phase(
        config=_config(),
        state=state_v1,
        syllabus=_syllabus(),
        today=date(2026, 6, 9),
        cache=cache,
        state_path=state_path,
        state_log_path=log_path,
        review_factory=lambda **kw: FakeReviewClient(subtasks=subtasks),
        completion_factory=lambda **kw: FakeCompletionClient(),
        todoist_token="tok",
        project_id="p1",
    )
    assert summary2.mutations_applied == 0
    assert state_v2.current_module == 2


def test_auto_unpause_when_paused_until_elapses(tmp_path: Path):
    state = _state(
        paused=True,
        paused_since=date(2026, 6, 1),
        paused_until=date(2026, 6, 8),
    )
    state_path = tmp_path / "state.yaml"
    save_state(state_path, state)
    log_path = tmp_path / "state_log.yaml"

    new_state, summary = run_state_review_phase(
        config=_config(),
        state=state,
        syllabus=_syllabus(),
        today=date(2026, 6, 8),
        cache={},
        state_path=state_path,
        state_log_path=log_path,
        review_factory=lambda **kw: FakeReviewClient(),
        completion_factory=lambda **kw: FakeCompletionClient(),
        todoist_token="tok",
        project_id="p1",
    )
    assert summary.auto_unpaused is True
    assert new_state.paused is False
    assert len(new_state.pause_history) == 1


def test_auto_unpause_idempotent(tmp_path: Path):
    """Second cron after auto-unpause must NOT re-write a duplicate log entry."""
    state = _state(
        paused=True,
        paused_since=date(2026, 6, 1),
        paused_until=date(2026, 6, 8),
    )
    state_path = tmp_path / "state.yaml"
    save_state(state_path, state)
    log_path = tmp_path / "state_log.yaml"

    new_state, summary1 = run_state_review_phase(
        config=_config(), state=state, syllabus=_syllabus(),
        today=date(2026, 6, 8), cache={},
        state_path=state_path, state_log_path=log_path,
        review_factory=lambda **kw: FakeReviewClient(),
        completion_factory=lambda **kw: FakeCompletionClient(),
        todoist_token="tok", project_id="p1",
    )
    assert summary1.auto_unpaused is True
    log_v1 = load_state_log(log_path)

    # Second cron with unpaused state — should be inert on the auto-unpause path.
    _, summary2 = run_state_review_phase(
        config=_config(), state=new_state, syllabus=_syllabus(),
        today=date(2026, 6, 9), cache={},
        state_path=state_path, state_log_path=log_path,
        review_factory=lambda **kw: FakeReviewClient(),
        completion_factory=lambda **kw: FakeCompletionClient(),
        todoist_token="tok", project_id="p1",
    )
    assert summary2.auto_unpaused is False
    assert load_state_log(log_path) == log_v1


def test_increment_counter_parses_comment(tmp_path: Path):
    cache = {
        "parent-ext": {
            "todoist_task_id": "parent-1",
            "state_review_parent": True,
            "created_at": "2026-06-07T00:00:00+00:00",
        },
        "sub-ext-0": {
            "todoist_task_id": "sub-anki",
            "state_review_action": {"type": "increment_counter", "counter": "anki_card_count"},
        },
    }
    state = _state(manual_counters={"anki_card_count": 100})
    state_path = tmp_path / "state.yaml"
    save_state(state_path, state)
    log_path = tmp_path / "state_log.yaml"

    subtasks = [FakeSubtask(id="sub-anki", content="anki", is_completed=True)]
    new_state, summary = run_state_review_phase(
        config=_config(), state=state, syllabus=_syllabus(),
        today=date(2026, 6, 8), cache=cache,
        state_path=state_path, state_log_path=log_path,
        review_factory=lambda **kw: FakeReviewClient(subtasks=subtasks, comment="25"),
        completion_factory=lambda **kw: FakeCompletionClient(),
        todoist_token="tok", project_id="p1",
    )
    assert summary.mutations_applied == 1
    assert new_state.manual_counters["anki_card_count"] == 125


def test_increment_counter_skips_unparseable_comment(tmp_path: Path):
    cache = {
        "parent-ext": {
            "todoist_task_id": "parent-1",
            "state_review_parent": True,
            "created_at": "2026-06-07T00:00:00+00:00",
        },
        "sub-ext-0": {
            "todoist_task_id": "sub-anki",
            "state_review_action": {"type": "increment_counter", "counter": "anki_card_count"},
        },
    }
    state = _state(manual_counters={"anki_card_count": 100})
    state_path = tmp_path / "state.yaml"
    save_state(state_path, state)
    log_path = tmp_path / "state_log.yaml"

    subtasks = [FakeSubtask(id="sub-anki", content="anki", is_completed=True)]
    new_state, summary = run_state_review_phase(
        config=_config(), state=state, syllabus=_syllabus(),
        today=date(2026, 6, 8), cache=cache,
        state_path=state_path, state_log_path=log_path,
        review_factory=lambda **kw: FakeReviewClient(subtasks=subtasks, comment="around 25"),
        completion_factory=lambda **kw: FakeCompletionClient(),
        todoist_token="tok", project_id="p1",
    )
    assert summary.mutations_applied == 0
    assert new_state.manual_counters["anki_card_count"] == 100


def test_persistent_emergency_pause_consumed(tmp_path: Path):
    ep_ext = persistent_pause_external_id(date(2026, 6, 1))
    cache = {
        ep_ext: {
            "todoist_task_id": "pause-task",
            "persistent_category": "emergency-pause",
            "persistent_action": {"type": "set_pause", "days": 365, "reason": "emergency"},
            "persistent_consumed": False,
        }
    }
    state = _state(paused=False)
    state_path = tmp_path / "state.yaml"
    save_state(state_path, state)
    log_path = tmp_path / "state_log.yaml"

    new_state, summary = run_state_review_phase(
        config=_config(), state=state, syllabus=_syllabus(),
        today=date(2026, 6, 8), cache=cache,
        state_path=state_path, state_log_path=log_path,
        review_factory=lambda **kw: FakeReviewClient(),
        completion_factory=lambda **kw: FakeCompletionClient(completed={"pause-task"}),
        todoist_token="tok", project_id="p1",
    )
    assert summary.mutations_applied == 1
    assert new_state.paused is True
    assert cache[ep_ext]["persistent_consumed"] is True


def test_evaluate_show_if_predicates():
    syl = _syllabus()
    s = _state(current_module=1)
    assert evaluate_show_if("not_on_last_module", s, syl) is True
    s_last = _state(current_module=len(syl.modules))
    assert evaluate_show_if("not_on_last_module", s_last, syl) is False
    assert evaluate_show_if("paused", _state(paused=True), syl) is True
    assert evaluate_show_if("not_paused", _state(paused=False), syl) is True
    assert evaluate_show_if(None, s, syl) is True


def test_dry_run_makes_no_writes(tmp_path: Path):
    state = _state()
    state_path = tmp_path / "state.yaml"
    save_state(state_path, state)
    original = state_path.read_text()
    log_path = tmp_path / "state_log.yaml"

    new_state, summary = run_state_review_phase(
        config=_config(), state=state, syllabus=_syllabus(),
        today=date(2026, 6, 8), cache={},
        state_path=state_path, state_log_path=log_path,
        dry_run=True,
        review_factory=lambda **kw: FakeReviewClient(),
        completion_factory=lambda **kw: FakeCompletionClient(),
        todoist_token="tok", project_id="p1",
    )
    assert new_state is state
    assert summary.mutations_applied == 0
    assert state_path.read_text() == original
    assert not log_path.exists()


def test_state_log_round_trip(tmp_path: Path):
    log_path = tmp_path / "state_log.yaml"
    entries = [
        {"timestamp": "2026-06-08", "action": "advance_module", "todoist_task_id": "t1"},
        {"timestamp": "2026-06-15", "action": "mark_book_finished", "todoist_task_id": "t2"},
    ]
    save_state_log(log_path, entries)
    assert load_state_log(log_path) == entries


def test_state_log_missing_file_returns_empty(tmp_path: Path):
    assert load_state_log(tmp_path / "nope.yaml") == []


def test_track_auto_lifecycle_fires_at_month_boundary(tmp_path: Path):
    """Owner's not_started track flips to current when derived_month >= start."""
    from src.syllabus import TrackDeclaration
    state = _state(
        start_date=date(2026, 5, 1),
        learning_tracks={"Courses": {"X": "not_started"}},
    )
    state_path = tmp_path / "state.yaml"
    save_state(state_path, state)
    log_path = tmp_path / "state_log.yaml"

    syl = _syllabus(tracks=[
        TrackDeclaration(title="X", category="Courses", phase=1, months=(1, 3))
    ])

    new_state, summary = run_state_review_phase(
        config=_config(), state=state, syllabus=syl,
        today=date(2026, 5, 8),  # derived month 1, inside [1,3]
        cache={}, state_path=state_path, state_log_path=log_path,
        review_factory=lambda **kw: FakeReviewClient(),
        completion_factory=lambda **kw: FakeCompletionClient(),
        todoist_token="tok", project_id="p1",
    )
    assert summary.mutations_applied >= 1
    assert new_state.learning_tracks["Courses"]["X"] == "current"


def test_track_auto_lifecycle_idempotent(tmp_path: Path):
    """Second cron after a transition must not duplicate the log entry."""
    from src.syllabus import TrackDeclaration
    state = _state(learning_tracks={})
    state_path = tmp_path / "state.yaml"
    save_state(state_path, state)
    log_path = tmp_path / "state_log.yaml"
    syl = _syllabus(tracks=[
        TrackDeclaration(title="X", category="Courses", phase=1, months=(1, 3))
    ])

    state_v1, _ = run_state_review_phase(
        config=_config(), state=state, syllabus=syl,
        today=date(2026, 5, 8), cache={},
        state_path=state_path, state_log_path=log_path,
        review_factory=lambda **kw: FakeReviewClient(),
        completion_factory=lambda **kw: FakeCompletionClient(),
        todoist_token="tok", project_id="p1",
    )
    log_v1 = load_state_log(log_path)

    _, summary2 = run_state_review_phase(
        config=_config(), state=state_v1, syllabus=syl,
        today=date(2026, 5, 9), cache={},
        state_path=state_path, state_log_path=log_path,
        review_factory=lambda **kw: FakeReviewClient(),
        completion_factory=lambda **kw: FakeCompletionClient(),
        todoist_token="tok", project_id="p1",
    )
    assert summary2.mutations_applied == 0
    assert load_state_log(log_path) == log_v1


def test_track_lifecycle_skipped_while_paused(tmp_path: Path):
    """Engine should not auto-transition tracks during a pause window."""
    from src.syllabus import TrackDeclaration
    state = _state(
        learning_tracks={},
        paused=True,
        paused_since=date(2026, 5, 1),
        paused_until=date(2026, 12, 1),  # far future; no auto-unpause
    )
    state_path = tmp_path / "state.yaml"
    save_state(state_path, state)
    log_path = tmp_path / "state_log.yaml"
    syl = _syllabus(tracks=[
        TrackDeclaration(title="X", category="Courses", phase=1, months=(1, 3))
    ])

    new_state, _ = run_state_review_phase(
        config=_config(), state=state, syllabus=syl,
        today=date(2026, 5, 8), cache={},
        state_path=state_path, state_log_path=log_path,
        review_factory=lambda **kw: FakeReviewClient(),
        completion_factory=lambda **kw: FakeCompletionClient(),
        todoist_token="tok", project_id="p1",
    )
    # No transition — track stays not_started.
    assert new_state.learning_tracks.get("Courses", {}).get("X") in (None, "not_started")
