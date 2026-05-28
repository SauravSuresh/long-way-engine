from datetime import date
from pathlib import Path

from src.state import SyllabusState, load_syllabus_state


YAML = """
start_date: 2026-05-05
phase: 1
month: 1
current_module: 1
current_book: "Computer Systems: A Programmer's Perspective"
completed_modules: []
books_state:
  "Computer Systems: A Programmer's Perspective": current
learning_tracks:
  Courses:
    "boot.dev": current
paused: false
paused_since: null
pause_history: []
"""


def test_load_syllabus_state_basic(tmp_path: Path):
    p = tmp_path / "long-way.yaml"
    p.write_text(YAML)
    s = load_syllabus_state(p)
    assert isinstance(s, SyllabusState)
    assert s.start_date == date(2026, 5, 5)
    assert s.phase == 1
    assert s.current_module == 1
    assert s.current_book.startswith("Computer Systems")
    assert s.paused is False
    assert s.learning_tracks["Courses"]["boot.dev"] == "current"
    assert s.books_state["Computer Systems: A Programmer's Perspective"] == "current"


def test_load_syllabus_state_missing_required(tmp_path: Path):
    import pytest

    p = tmp_path / "bad.yaml"
    p.write_text("phase: 1\n")  # missing start_date, current_module, current_book
    with pytest.raises(KeyError):
        load_syllabus_state(p)
