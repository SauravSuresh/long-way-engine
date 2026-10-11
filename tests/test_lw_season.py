from datetime import date
from pathlib import Path

from src.lw.season_logic import log_minutes, mark_done, rest_end, status_lines
from src.seasons import SeasonsState, load_seasons

OWNER = """
todoist_project_id: p
rhythm:
  rest_week: true
  deep_blocks:
    monday: {start: "07:30", minutes: 60}
    tuesday: {start: "07:30", minutes: 60}
bucket:
  - {id: a, name: A, area: Work, hours: 2}
  - {id: b, name: B, area: Work, hours: 1}
"""
MON = date(2026, 10, 12)


def _seasons(tmp_path: Path):
    p = tmp_path / "seasons.yaml"
    p.write_text(OWNER)
    return load_seasons(p)


def test_done_defaults_to_main_and_starts_rest(tmp_path):
    state, msg = mark_done(_seasons(tmp_path), SeasonsState(), MON, None)
    assert state.milestones["a"].done == MON
    assert state.rest_until == date(2026, 10, 19) and "rest week" in msg
    assert state.rests == [(date(2026, 10, 13), date(2026, 10, 19))]


def test_done_last_milestone_has_no_rest(tmp_path):
    seasons = _seasons(tmp_path)
    state, _ = mark_done(seasons, SeasonsState(), MON, "b")
    state, msg = mark_done(seasons, state, MON, "a")
    assert state.rest_until is None and "rest" not in msg


def test_log_and_rest_end(tmp_path):
    seasons = _seasons(tmp_path)
    state, _ = log_minutes(seasons, SeasonsState(), MON, 45, date(2026, 10, 9), None)
    assert state.milestones["a"].logged == {date(2026, 10, 9): 45}
    state.rest_until = MON
    state, msg = rest_end(state)
    assert state.rest_until is None and msg


def test_status_lines_mention_current_and_forecast(tmp_path):
    lines = status_lines(_seasons(tmp_path), SeasonsState(), MON)
    assert lines[0] == "Main: a    Side: —"
    assert any(line.startswith("A ") and "2026-10-12 -> 2026-10-13" in line for line in lines)
    assert any("rest weeks: 2026-10-14..2026-10-20" in line for line in lines)
