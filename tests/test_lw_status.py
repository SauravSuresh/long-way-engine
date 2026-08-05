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
