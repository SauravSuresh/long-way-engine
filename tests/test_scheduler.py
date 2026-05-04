from datetime import date

import pytest

from src.scheduler import (
    _is_first_of_quarter,
    _is_jan_1,
    _is_last_day_of_month,
    _is_last_saturday_of_month,
    should_create_today,
)
from src.templates import Template
from tests.test_templates import make_config, make_state


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


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


def weekly_template(day: str) -> Template:
    return Template(
        id=f"weekly-{day}",
        title=f"Weekly {day}",
        description="",
        due="today",
        labels=[],
        cadence="weekly",
        day_of_week=day,
    )


def monthly_template(rule: int | str) -> Template:
    return Template(
        id=f"monthly-{rule}",
        title=f"Monthly {rule}",
        description="",
        due="today",
        labels=[],
        cadence="monthly",
        day_of_month=rule,
    )


def quarterly_template() -> Template:
    return Template(
        id="quarterly-synthesis",
        title="Quarterly synthesis",
        description="",
        due="today",
        labels=[],
        cadence="quarterly",
    )


def annual_template() -> Template:
    return Template(
        id="annual-review",
        title="Annual review",
        description="",
        due="today",
        labels=[],
        cadence="annual",
    )


# ---------------------------------------------------------------------------
# paused short-circuit (highest precedence)
# ---------------------------------------------------------------------------


def test_paused_blocks_daily():
    state = make_state()
    state.paused = True
    assert should_create_today(daily_template(), date(2026, 5, 4), state, make_config()) is False


def test_paused_blocks_weekly():
    state = make_state()
    state.paused = True
    assert should_create_today(weekly_template("friday"), date(2026, 5, 8), state, make_config()) is False


def test_paused_blocks_monthly():
    state = make_state()
    state.paused = True
    assert should_create_today(monthly_template(1), date(2026, 5, 1), state, make_config()) is False


def test_paused_blocks_quarterly():
    state = make_state()
    state.paused = True
    assert should_create_today(quarterly_template(), date(2026, 4, 1), state, make_config()) is False


def test_paused_blocks_annual():
    state = make_state()
    state.paused = True
    assert should_create_today(annual_template(), date(2026, 1, 1), state, make_config()) is False


def test_paused_blocks_unknown_cadence_without_raising():
    """paused short-circuits BEFORE the unknown-cadence raise. Important for forward-compat."""
    state = make_state()
    state.paused = True
    tpl = Template(
        id="module-onboarding",
        title="x",
        description="",
        due="",
        labels=[],
        cadence="once-per-module",
    )
    assert should_create_today(tpl, date(2026, 5, 4), state, make_config()) is False


# ---------------------------------------------------------------------------
# Daily — Phase A behavior preserved
# ---------------------------------------------------------------------------


def test_daily_on_sunday_with_skip_returns_false():
    sunday = date(2026, 5, 3)
    assert sunday.weekday() == 6
    assert should_create_today(daily_template(), sunday, make_state(), make_config()) is False


def test_daily_on_monday_returns_true():
    monday = date(2026, 5, 4)
    assert should_create_today(daily_template(), monday, make_state(), make_config()) is True


def test_daily_without_skip_runs_on_sunday():
    sunday = date(2026, 5, 3)
    assert should_create_today(daily_template(skip=None), sunday, make_state(), make_config()) is True


def test_sunday_off_false_runs_daily_on_sunday():
    sunday = date(2026, 5, 3)
    cfg = make_config()
    cfg.sunday_off = False
    assert should_create_today(daily_template(), sunday, make_state(), cfg) is True


# ---------------------------------------------------------------------------
# Weekly
# ---------------------------------------------------------------------------


def test_weekly_friday_fires_on_friday():
    friday = date(2026, 5, 8)  # 2026-05-08 is a Friday
    assert friday.weekday() == 4
    assert should_create_today(weekly_template("friday"), friday, make_state(), make_config()) is True


def test_weekly_friday_does_not_fire_on_thursday():
    thursday = date(2026, 5, 7)
    assert should_create_today(weekly_template("friday"), thursday, make_state(), make_config()) is False


def test_weekly_saturday_fires_on_saturday():
    sat = date(2026, 5, 9)
    assert sat.weekday() == 5
    assert should_create_today(weekly_template("saturday"), sat, make_state(), make_config()) is True


def test_weekly_iso_week_year_boundary_fires_on_calendar_friday():
    """2027-01-01 is Friday but ISO week 53 of 2026. Day-of-week dispatch is calendar-based."""
    fri_in_iso_2026 = date(2027, 1, 1)
    assert fri_in_iso_2026.weekday() == 4
    assert should_create_today(weekly_template("friday"), fri_in_iso_2026, make_state(), make_config()) is True

    fri_in_iso_2026_w52 = date(2026, 12, 25)
    assert fri_in_iso_2026_w52.weekday() == 4
    assert should_create_today(weekly_template("friday"), fri_in_iso_2026_w52, make_state(), make_config()) is True


def test_weekly_unknown_day_raises():
    with pytest.raises(NotImplementedError, match="day_of_week"):
        should_create_today(weekly_template("funday"), date(2026, 5, 4), make_state(), make_config())


def test_weekly_missing_day_raises():
    tpl = Template(
        id="weekly-bad",
        title="x",
        description="",
        due="",
        labels=[],
        cadence="weekly",
    )
    with pytest.raises(NotImplementedError, match="day_of_week"):
        should_create_today(tpl, date(2026, 5, 4), make_state(), make_config())


# ---------------------------------------------------------------------------
# Monthly — int day_of_month
# ---------------------------------------------------------------------------


def test_monthly_day_1_fires_on_first():
    assert should_create_today(monthly_template(1), date(2026, 5, 1), make_state(), make_config()) is True


def test_monthly_day_1_does_not_fire_on_second():
    assert should_create_today(monthly_template(1), date(2026, 5, 2), make_state(), make_config()) is False


def test_monthly_day_15_fires_on_fifteenth():
    assert should_create_today(monthly_template(15), date(2026, 5, 15), make_state(), make_config()) is True


def test_monthly_day_29_raises_for_safety():
    """Phase B refuses 29..31 to avoid month-length edge cases."""
    with pytest.raises(NotImplementedError, match="day_of_month"):
        should_create_today(monthly_template(29), date(2026, 5, 29), make_state(), make_config())


# ---------------------------------------------------------------------------
# Monthly — last-saturday and last-day
# ---------------------------------------------------------------------------


def test_monthly_last_saturday_fires_on_2026_05_30():
    """2026-05-30 is the last Saturday of May 2026 (May 31 is a Sunday)."""
    d = date(2026, 5, 30)
    assert d.weekday() == 5
    assert should_create_today(monthly_template("last-saturday"), d, make_state(), make_config()) is True


def test_monthly_last_saturday_does_not_fire_on_earlier_saturdays():
    earlier = date(2026, 5, 23)
    assert earlier.weekday() == 5
    assert should_create_today(monthly_template("last-saturday"), earlier, make_state(), make_config()) is False


def test_monthly_last_saturday_fires_on_feb_28_2026():
    """2026-02-28 is a Saturday and the last day of Feb 2026 (non-leap)."""
    d = date(2026, 2, 28)
    assert d.weekday() == 5
    assert should_create_today(monthly_template("last-saturday"), d, make_state(), make_config()) is True


def test_monthly_last_day_fires_on_apr_30():
    assert should_create_today(monthly_template("last-day"), date(2026, 4, 30), make_state(), make_config()) is True


def test_monthly_last_day_does_not_fire_on_apr_29():
    assert should_create_today(monthly_template("last-day"), date(2026, 4, 29), make_state(), make_config()) is False


def test_monthly_last_day_fires_on_feb_28_non_leap():
    assert should_create_today(monthly_template("last-day"), date(2026, 2, 28), make_state(), make_config()) is True


def test_monthly_last_day_fires_on_feb_29_leap():
    assert should_create_today(monthly_template("last-day"), date(2024, 2, 29), make_state(), make_config()) is True


def test_monthly_unknown_string_rule_raises():
    with pytest.raises(NotImplementedError, match="day_of_month"):
        should_create_today(monthly_template("first-friday"), date(2026, 5, 1), make_state(), make_config())


# ---------------------------------------------------------------------------
# Quarterly
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("d", [
    date(2026, 1, 1),
    date(2026, 4, 1),
    date(2026, 7, 1),
    date(2026, 10, 1),
    date(2027, 1, 1),
])
def test_quarterly_fires_on_quarter_starts(d):
    assert should_create_today(quarterly_template(), d, make_state(), make_config()) is True


@pytest.mark.parametrize("d", [
    date(2026, 1, 2),
    date(2026, 3, 31),
    date(2026, 4, 2),
    date(2026, 5, 1),
    date(2026, 6, 30),
])
def test_quarterly_does_not_fire_off_quarter_starts(d):
    assert should_create_today(quarterly_template(), d, make_state(), make_config()) is False


# ---------------------------------------------------------------------------
# Annual
# ---------------------------------------------------------------------------


def test_annual_fires_on_jan_1():
    assert should_create_today(annual_template(), date(2026, 1, 1), make_state(), make_config()) is True


def test_annual_does_not_fire_on_dec_31():
    assert should_create_today(annual_template(), date(2026, 12, 31), make_state(), make_config()) is False


def test_annual_does_not_fire_on_jan_2():
    assert should_create_today(annual_template(), date(2026, 1, 2), make_state(), make_config()) is False


# ---------------------------------------------------------------------------
# THE EDGE CASE: 2029-04-01 is a Sunday AND a quarter boundary
# ---------------------------------------------------------------------------


def test_2029_04_01_quarterly_fires_despite_being_sunday():
    sunday_q2 = date(2029, 4, 1)
    assert sunday_q2.weekday() == 6  # Sunday
    assert should_create_today(quarterly_template(), sunday_q2, make_state(), make_config()) is True


def test_2029_04_01_daily_with_sunday_skip_does_not_fire():
    """Same date, daily template: Sunday-off still wins for daily cadence."""
    sunday_q2 = date(2029, 4, 1)
    assert should_create_today(daily_template(), sunday_q2, make_state(), make_config()) is False


# ---------------------------------------------------------------------------
# Unknown cadence
# ---------------------------------------------------------------------------


def test_unknown_cadence_raises_with_template_id():
    bogus = Template(
        id="bogus-cadence-template",
        title="x",
        description="",
        due="",
        labels=[],
        cadence="biweekly",  # not supported
    )
    with pytest.raises(NotImplementedError, match=r"biweekly.*bogus-cadence-template"):
        should_create_today(bogus, date(2026, 5, 4), make_state(), make_config())


# ---------------------------------------------------------------------------
# once-per-module cadence (Phase D)
# ---------------------------------------------------------------------------


def _module_template(module_number: int, suffix: str = "onboarding") -> Template:
    return Template(
        id=f"module-{module_number:02d}-{suffix}",
        title=f"Module {module_number} {suffix}",
        description="",
        due="today",
        labels=[],
        cadence="once-per-module",
        module_number=module_number,
    )


def test_once_per_module_fires_when_template_matches_current_module():
    state = make_state()
    state.current_module = 6
    assert (
        should_create_today(
            _module_template(6), date(2026, 5, 4), state, make_config()
        )
        is True
    )


def test_once_per_module_does_not_fire_for_past_module():
    state = make_state()
    state.current_module = 6
    assert (
        should_create_today(
            _module_template(1), date(2026, 5, 4), state, make_config()
        )
        is False
    )


def test_once_per_module_does_not_fire_for_future_module():
    state = make_state()
    state.current_module = 1
    assert (
        should_create_today(
            _module_template(2), date(2026, 5, 4), state, make_config()
        )
        is False
    )


def test_once_per_module_lineage_and_onboarding_both_fire_for_same_module():
    """Module 6 has both onboarding and lineage detour. Both have module_number=6."""
    state = make_state()
    state.current_module = 6
    onboarding = _module_template(6, "onboarding")
    lineage = _module_template(6, "lineage")
    assert should_create_today(onboarding, date(2026, 5, 4), state, make_config())
    assert should_create_today(lineage, date(2026, 5, 4), state, make_config())


def test_once_per_module_missing_module_number_raises():
    bad = Template(
        id="module-bad",
        title="x",
        description="",
        due="",
        labels=[],
        cadence="once-per-module",
    )
    with pytest.raises(NotImplementedError, match="module_number"):
        should_create_today(bad, date(2026, 5, 4), make_state(), make_config())


def test_paused_blocks_once_per_module_without_raising():
    """paused short-circuit beats every cadence including once-per-module."""
    state = make_state()
    state.paused = True
    state.current_module = 6
    assert (
        should_create_today(
            _module_template(6), date(2026, 5, 4), state, make_config()
        )
        is False
    )


# ---------------------------------------------------------------------------
# skip_if: pair_day  (Phase D)
# ---------------------------------------------------------------------------


def _pair_day_template() -> Template:
    return Template(
        id="daily-evening-hands-on",
        title="Evening hands-on",
        description="",
        due="today",
        labels=[],
        cadence="daily",
        skip_if="pair_day",
    )


def test_pair_day_skip_on_configured_day():
    cfg = make_config()
    cfg.pair_day = "thursday"
    thursday = date(2026, 5, 7)
    assert thursday.weekday() == 3
    assert should_create_today(_pair_day_template(), thursday, make_state(), cfg) is False


def test_pair_day_no_skip_on_other_days():
    cfg = make_config()
    cfg.pair_day = "thursday"
    monday = date(2026, 5, 4)
    assert should_create_today(_pair_day_template(), monday, make_state(), cfg) is True


def test_pair_day_unset_means_no_skip():
    cfg = make_config()
    cfg.pair_day = None
    thursday = date(2026, 5, 7)
    assert should_create_today(_pair_day_template(), thursday, make_state(), cfg) is True


def test_pair_day_unknown_value_means_no_skip():
    """Defensive: a typo in config should not crash; skip rule simply doesn't fire."""
    cfg = make_config()
    cfg.pair_day = "tursday"  # typo
    thursday = date(2026, 5, 7)
    assert should_create_today(_pair_day_template(), thursday, make_state(), cfg) is True


# ---------------------------------------------------------------------------
# Date helpers
# ---------------------------------------------------------------------------


def test_is_last_saturday_of_month():
    assert _is_last_saturday_of_month(date(2026, 5, 30)) is True
    assert _is_last_saturday_of_month(date(2026, 5, 23)) is False
    assert _is_last_saturday_of_month(date(2026, 2, 28)) is True
    assert _is_last_saturday_of_month(date(2026, 5, 31)) is False  # Sunday


def test_is_last_day_of_month():
    assert _is_last_day_of_month(date(2026, 4, 30)) is True
    assert _is_last_day_of_month(date(2026, 4, 29)) is False
    assert _is_last_day_of_month(date(2026, 2, 28)) is True   # non-leap
    assert _is_last_day_of_month(date(2024, 2, 29)) is True   # leap
    assert _is_last_day_of_month(date(2024, 2, 28)) is False  # leap, not last


def test_is_first_of_quarter():
    assert _is_first_of_quarter(date(2026, 1, 1)) is True
    assert _is_first_of_quarter(date(2026, 4, 1)) is True
    assert _is_first_of_quarter(date(2026, 7, 1)) is True
    assert _is_first_of_quarter(date(2026, 10, 1)) is True
    assert _is_first_of_quarter(date(2026, 2, 1)) is False
    assert _is_first_of_quarter(date(2026, 4, 2)) is False


def test_is_jan_1():
    assert _is_jan_1(date(2026, 1, 1)) is True
    assert _is_jan_1(date(2027, 1, 1)) is True
    assert _is_jan_1(date(2026, 1, 2)) is False
    assert _is_jan_1(date(2026, 12, 31)) is False
