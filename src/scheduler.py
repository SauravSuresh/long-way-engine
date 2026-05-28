"""Decide whether a template should produce a task today.

Cadence dispatch:

  - paused short-circuit (highest precedence)
  - sunday_off short-circuit — if config.sunday_off and today is Sunday,
    NO template fires regardless of cadence. Hard rest day across the
    board (daily, weekly, monthly, quarterly, annual, once-per-module).
  - daily          — every day, with optional skip_if rules:
                       * skip_if=pair_day + today is config.pair_day -> skip
  - weekly         — today.weekday() matches template.day_of_week
  - monthly        — template.day_of_month is int 1..28, "last-day", or "last-saturday"
  - quarterly      — today is Jan 1 / Apr 1 / Jul 1 / Oct 1
  - annual         — today is Jan 1
  - once-per-module — template.module_number == state.current_module
  - anything else raises NotImplementedError naming the cadence and the
    offending template id.

Sunday-off applies GLOBALLY when config.sunday_off=true. A Sunday quarter
boundary (e.g. 2029-04-01) loses its task; the owner accepts that as the
price of a real rest day. Owner can opt out by setting sunday_off=false.
"""

from __future__ import annotations

import calendar
from datetime import date, timedelta

from src.config import Config
from src.state import State
from src.templates import Template

SUNDAY = 6  # date.weekday(): 0=Mon ... 6=Sun
SATURDAY = 5

_DAY_OF_WEEK: dict[str, int] = {
    "monday": 0,
    "tuesday": 1,
    "wednesday": 2,
    "thursday": 3,
    "friday": 4,
    "saturday": 5,
    "sunday": 6,
}

_QUARTER_START_MONTHS = (1, 4, 7, 10)


def should_create_today(
    template: Template,
    today: date,
    state: State,
    config: Config,
    syllabus_key: str = "",
) -> bool:
    if state.paused:
        return False

    # Global Sunday rest day: blocks every cadence when sunday_off is set.
    # Lives above cadence dispatch so weekly day_of_week=sunday templates,
    # monthly day_of_month=1 falling on Sunday, etc. all skip uniformly.
    # Exception: state_review templates fire on Sunday by design (the
    # weekly review IS the rest-day's planning ritual, not study work).
    if (
        config.sunday_off
        and today.weekday() == SUNDAY
        and not getattr(template, "state_review", False)
    ):
        return False

    # gated_by: AND-composed track / module gates. Evaluated AFTER
    # paused + sunday_off so existing tests on those branches keep
    # the same skip reason ordering.
    gates = getattr(template, "gated_by", None) or []
    if gates:
        from src.tracks import evaluate_gates
        passes, _reason = evaluate_gates(gates, state)
        if not passes:
            return False

    cadence = template.cadence
    if cadence == "daily":
        return _daily_fires(template, today, config)
    if cadence == "weekly":
        return _weekly_fires(template, today)
    if cadence == "monthly":
        return _monthly_fires(template, today)
    if cadence == "quarterly":
        return _is_first_of_quarter(today)
    if cadence == "annual":
        return _is_jan_1(today)
    if cadence == "once-per-module":
        return _once_per_module_fires(template, state)

    raise NotImplementedError(
        f"cadence {cadence!r} on template {template.id!r} not supported"
    )


# --- per-cadence predicates -----------------------------------------------------


def _daily_fires(template: Template, today: date, config: Config) -> bool:
    rules = template.skip_if  # list[str]; may have multiple rules
    if (
        "sunday" in rules
        and config.sunday_off
        and today.weekday() == SUNDAY
    ):
        return False
    if (
        "pair_day" in rules
        and config.pair_day
        and today.weekday() == _DAY_OF_WEEK.get(config.pair_day.lower(), -1)
    ):
        return False
    return True


def _once_per_module_fires(template: Template, state: State) -> bool:
    if template.module_number is None:
        raise NotImplementedError(
            f"once-per-module template {template.id!r} missing module_number"
        )
    return template.module_number == state.current_module


def _weekly_fires(template: Template, today: date) -> bool:
    if template.day_of_week is None:
        raise NotImplementedError(
            f"weekly template {template.id!r} missing day_of_week"
        )
    key = template.day_of_week.lower()
    if key not in _DAY_OF_WEEK:
        raise NotImplementedError(
            f"unsupported day_of_week {template.day_of_week!r} on template {template.id!r}"
        )
    if today.weekday() != _DAY_OF_WEEK[key]:
        return False
    # Phase F: weekly templates may opt out of last-Saturdays via the existing
    # skip_if list (e.g. weekly-saturday-deep-block on monthly-retrieval days).
    if (
        "last-saturday-of-month" in template.skip_if
        and _is_last_saturday_of_month(today)
    ):
        return False
    return True


def _monthly_fires(template: Template, today: date) -> bool:
    rule = template.day_of_month
    if rule is None:
        raise NotImplementedError(
            f"monthly template {template.id!r} missing day_of_month"
        )
    if isinstance(rule, int):
        if not (1 <= rule <= 28):
            raise NotImplementedError(
                f"unsupported day_of_month {rule!r} on template {template.id!r}; "
                "only 1..28 supported (avoid 29/30/31 month-length edge cases)"
            )
        return today.day == rule
    if rule == "last-day":
        return _is_last_day_of_month(today)
    if rule == "last-saturday":
        return _is_last_saturday_of_month(today)
    raise NotImplementedError(
        f"unsupported day_of_month {rule!r} on template {template.id!r}; "
        "supported: int 1..28, 'last-day', 'last-saturday'"
    )


# --- date helpers --------------------------------------------------------------


def _is_last_day_of_month(today: date) -> bool:
    last = calendar.monthrange(today.year, today.month)[1]
    return today.day == last


def _is_last_saturday_of_month(today: date) -> bool:
    if today.weekday() != SATURDAY:
        return False
    # If today is Saturday and adding 7 days lands in a different month,
    # today is the last Saturday.
    return (today + timedelta(days=7)).month != today.month


def _is_first_of_quarter(today: date) -> bool:
    return today.day == 1 and today.month in _QUARTER_START_MONTHS


def _is_jan_1(today: date) -> bool:
    return today.month == 1 and today.day == 1
