from datetime import date
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]


def test_build_status_lists_enabled_curricula():
    from src.lw.status_logic import build_status

    lines = "\n".join(build_status(REPO, date(2026, 8, 5)))
    assert "marketplace-builder" in lines


def test_build_status_shows_current_module_and_deadline_fields():
    from src.lw.status_logic import build_status

    lines = "\n".join(build_status(REPO, date(2026, 8, 5)))
    assert "Rung" in lines or "module" in lines.lower()


def test_build_status_lists_due_today_on_a_monday():
    """2026-08-10 is a Monday: marketplace-builder's build-session-monday
    template (weekly, day_of_week=monday) fires — its resolved title should
    show up in the due-today section."""
    from src.lw.status_logic import build_status

    lines = "\n".join(build_status(REPO, date(2026, 8, 10)))
    assert "due today" in lines
    assert "Ladder session" in lines


def test_deadline_line_handles_missing_deadline_without_crashing():
    """A rung with an empty/missing deadline and no extensions must not
    crash formatting the countdown (regression: {days:+d} on days=None)."""
    from src.lw.status_logic import _deadline_line

    meta = {"rung": 1, "option": "a", "deadline": "", "extensions": []}
    line = _deadline_line(meta, date(2026, 8, 5))
    assert "deadline" in line
    assert "d)" not in line
