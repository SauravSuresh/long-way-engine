"""Decide whether a template should produce a task today.

Phase A handles only `cadence: daily` with optional `skip_if: sunday`.
Other cadences raise NotImplementedError so an accidental Phase B
template added to Phase A fails loudly rather than silently misfiring.
"""

from __future__ import annotations

from datetime import date

from src.config import Config
from src.state import State
from src.templates import Template

SUNDAY = 6  # date.weekday() returns 0=Mon ... 6=Sun


def should_create_today(
    template: Template,
    today: date,
    state: State,
    config: Config,
) -> bool:
    """Phase A scheduler: daily cadence + Sunday skip only."""
    if template.cadence == "daily":
        if (
            template.skip_if == "sunday"
            and config.sunday_off
            and today.weekday() == SUNDAY
        ):
            return False
        return True

    raise NotImplementedError(
        f"cadence {template.cadence!r} is not supported in Phase A"
    )
