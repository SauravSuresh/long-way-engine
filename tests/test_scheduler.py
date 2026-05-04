from datetime import date

import pytest

from src.scheduler import should_create_today
from src.templates import Template
from tests.test_templates import make_config, make_state


def daily_template(skip: str | None = "sunday") -> Template:
    return Template(
        id="daily-anki",
        title="Anki",
        description="",
        due="today",
        labels=[],
        cadence="daily",
        skip_if=skip,
    )


def test_daily_on_sunday_with_skip_returns_false():
    sunday = date(2026, 5, 3)  # 2026-05-03 is a Sunday
    assert sunday.weekday() == 6
    assert (
        should_create_today(daily_template(), sunday, make_state(), make_config())
        is False
    )


def test_daily_on_monday_returns_true():
    monday = date(2026, 5, 4)
    assert monday.weekday() == 0
    assert (
        should_create_today(daily_template(), monday, make_state(), make_config())
        is True
    )


def test_daily_without_skip_runs_on_sunday():
    sunday = date(2026, 5, 3)
    assert (
        should_create_today(daily_template(skip=None), sunday, make_state(), make_config())
        is True
    )


def test_sunday_off_false_runs_daily_on_sunday():
    sunday = date(2026, 5, 3)
    cfg = make_config()
    cfg.sunday_off = False
    assert should_create_today(daily_template(), sunday, make_state(), cfg) is True


def test_unsupported_cadence_raises():
    weekly = Template(
        id="weekly-friday-review",
        title="t",
        description="",
        due="",
        labels=[],
        cadence="weekly",
    )
    with pytest.raises(NotImplementedError):
        should_create_today(weekly, date(2026, 5, 4), make_state(), make_config())
