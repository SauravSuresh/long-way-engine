from datetime import date
from pathlib import Path

import pytest
from zoneinfo import ZoneInfo

from src.state import load_state

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
