from datetime import date
from pathlib import Path

import pytest
from zoneinfo import ZoneInfo

from src.state import PauseInterval, load_state

VALID_STATE = """
start_date: 2026-05-04
timezone: Asia/Kolkata
phase: 1
month: 1
current_module: 1
current_book: "Computer Systems: A Programmer's Perspective"
completed_modules: []
active_branches: []
paused: false
manual_counters:
  anki_card_count: 0
notes: "started"
"""


def test_load_state_happy_path(tmp_path: Path):
    p = tmp_path / "state.yaml"
    p.write_text(VALID_STATE)
    s = load_state(p)
    assert s.start_date == date(2026, 5, 4)
    assert s.timezone == ZoneInfo("Asia/Kolkata")
    assert s.current_book.startswith("Computer Systems")
    assert s.phase == 1
    assert s.paused is False


def test_load_state_missing_required_key_exits(tmp_path: Path):
    p = tmp_path / "state.yaml"
    p.write_text("phase: 1\n")
    with pytest.raises(SystemExit):
        load_state(p)


def test_load_state_bad_timezone_exits(tmp_path: Path):
    p = tmp_path / "state.yaml"
    p.write_text(VALID_STATE.replace("Asia/Kolkata", "Not/A_Zone"))
    with pytest.raises(SystemExit):
        load_state(p)


def test_load_state_start_date_must_be_date(tmp_path: Path):
    p = tmp_path / "state.yaml"
    p.write_text(VALID_STATE.replace("2026-05-04", '"not-a-date"'))
    with pytest.raises(SystemExit):
        load_state(p)


# --- Phase E additions --------------------------------------------------------


def test_phase_e_fields_default_when_absent(tmp_path: Path):
    """Phase A-D states (no Phase E keys) keep loading."""
    p = tmp_path / "state.yaml"
    p.write_text(VALID_STATE)
    s = load_state(p)
    assert s.paused_since is None
    assert s.pause_history == []
    assert s.books_state == {}


def test_paused_since_parses_date(tmp_path: Path):
    p = tmp_path / "state.yaml"
    p.write_text(VALID_STATE + "paused_since: 2026-05-04\n")
    s = load_state(p)
    assert s.paused_since == date(2026, 5, 4)


def test_paused_since_must_be_date(tmp_path: Path):
    p = tmp_path / "state.yaml"
    p.write_text(VALID_STATE + "paused_since: not-a-date\n")
    with pytest.raises(SystemExit):
        load_state(p)


def test_pause_history_parses_intervals(tmp_path: Path):
    p = tmp_path / "state.yaml"
    p.write_text(VALID_STATE + (
        "pause_history:\n"
        "  - start: 2026-04-15\n"
        "    end: 2026-04-30\n"
        "    reason: travel\n"
    ))
    s = load_state(p)
    assert len(s.pause_history) == 1
    pi = s.pause_history[0]
    assert isinstance(pi, PauseInterval)
    assert pi.start == date(2026, 4, 15)
    assert pi.end == date(2026, 4, 30)
    assert pi.reason == "travel"


def test_pause_history_rejects_inverted_interval(tmp_path: Path):
    p = tmp_path / "state.yaml"
    p.write_text(VALID_STATE + (
        "pause_history:\n"
        "  - start: 2026-04-30\n"
        "    end: 2026-04-15\n"
        "    reason: oops\n"
    ))
    with pytest.raises(SystemExit):
        load_state(p)


def test_pause_history_rejects_non_date(tmp_path: Path):
    p = tmp_path / "state.yaml"
    p.write_text(VALID_STATE + (
        "pause_history:\n"
        "  - start: \"x\"\n"
        "    end: 2026-04-15\n"
    ))
    with pytest.raises(SystemExit):
        load_state(p)


def test_books_state_parses(tmp_path: Path):
    p = tmp_path / "state.yaml"
    p.write_text(VALID_STATE + (
        "books_state:\n"
        "  CSAPP: current\n"
        "  Networking: not_started\n"
        "  Debugging: done\n"
    ))
    s = load_state(p)
    assert s.books_state == {
        "CSAPP": "current",
        "Networking": "not_started",
        "Debugging": "done",
    }


def test_books_state_rejects_invalid_value(tmp_path: Path):
    p = tmp_path / "state.yaml"
    p.write_text(VALID_STATE + (
        "books_state:\n"
        "  CSAPP: pending\n"
    ))
    with pytest.raises(SystemExit):
        load_state(p)


# --- learning_tracks ---------------------------------------------------------


def test_learning_tracks_default_when_absent(tmp_path: Path):
    p = tmp_path / "state.yaml"
    p.write_text(VALID_STATE)
    s = load_state(p)
    assert s.learning_tracks == {}


def test_learning_tracks_default_when_null(tmp_path: Path):
    p = tmp_path / "state.yaml"
    p.write_text(VALID_STATE + "learning_tracks: null\n")
    s = load_state(p)
    assert s.learning_tracks == {}


def test_learning_tracks_parses_nested(tmp_path: Path):
    p = tmp_path / "state.yaml"
    p.write_text(VALID_STATE + (
        "learning_tracks:\n"
        "  Courses:\n"
        '    "boot.dev backend path": current\n'
        '    "boot.dev DSA": not_started\n'
        "  Certifications:\n"
        "    LFCS: current\n"
    ))
    s = load_state(p)
    assert s.learning_tracks == {
        "Courses": {
            "boot.dev backend path": "current",
            "boot.dev DSA": "not_started",
        },
        "Certifications": {"LFCS": "current"},
    }


def test_learning_tracks_rejects_top_non_dict(tmp_path: Path):
    p = tmp_path / "state.yaml"
    p.write_text(VALID_STATE + 'learning_tracks: ["a", "b"]\n')
    with pytest.raises(SystemExit):
        load_state(p)


def test_learning_tracks_rejects_category_non_dict(tmp_path: Path):
    p = tmp_path / "state.yaml"
    p.write_text(VALID_STATE + (
        "learning_tracks:\n"
        "  Courses: \"not a dict\"\n"
    ))
    with pytest.raises(SystemExit):
        load_state(p)


def test_learning_tracks_rejects_invalid_state(tmp_path: Path):
    p = tmp_path / "state.yaml"
    p.write_text(VALID_STATE + (
        "learning_tracks:\n"
        "  Courses:\n"
        "    \"boot.dev\": in_progress\n"  # not a valid state
    ))
    with pytest.raises(SystemExit):
        load_state(p)


def test_learning_tracks_empty_category_permitted(tmp_path: Path):
    p = tmp_path / "state.yaml"
    p.write_text(VALID_STATE + (
        "learning_tracks:\n"
        "  Courses: {}\n"
    ))
    s = load_state(p)
    assert s.learning_tracks == {"Courses": {}}


def test_learning_tracks_preserves_yaml_order(tmp_path: Path):
    p = tmp_path / "state.yaml"
    p.write_text(VALID_STATE + (
        "learning_tracks:\n"
        "  Zeta:\n"
        "    z-item: current\n"
        "  Alpha:\n"
        "    a-item: current\n"
    ))
    s = load_state(p)
    # Insertion order preserved (Python 3.7+ dict).
    assert list(s.learning_tracks.keys()) == ["Zeta", "Alpha"]
