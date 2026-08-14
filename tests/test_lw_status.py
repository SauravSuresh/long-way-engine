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


def test_build_status_lists_due_today_on_a_tuesday():
    """2026-08-18 is a Tuesday: marketplace-builder's build-session-tuesday
    template (weekly, day_of_week=tuesday) fires — its resolved title should
    show up in the due-today section."""
    from src.lw.status_logic import build_status

    lines = "\n".join(build_status(REPO, date(2026, 8, 18)))
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


def test_status_includes_global_xp_line_when_present(tmp_path):  # use the same tmp data.json trick
    from src.lw.status_logic import xp_line

    # no data.json -> None
    assert xp_line(tmp_path) is None


def test_build_status_does_not_crash_without_xp_block():
    """Real data.json (pre-Task-2-cron) lacks an xp block — build_status
    must still run cleanly."""
    from src.lw.status_logic import build_status

    build_status(REPO, date(2026, 8, 6))
