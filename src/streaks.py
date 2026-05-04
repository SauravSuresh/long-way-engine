"""Pure-function streak walkers for the Phase E dashboard.

Three streaks:
  - daily_streak — walks day-by-day; both daily-anki AND
    daily-morning-reading must be completed for the day to extend.
  - weekly_review_streak — walks Friday-by-Friday; weekly-friday-review
    must be completed AND the week's reflection must have status:filled.
  - monthly_post_streak — walks month-by-month; monthly-blog-post for
    the month's day 1 must be completed.

Skip rule (Phase E plan decision 6): Sundays AND any date inside
state.pause_history AND any date >= state.paused_since (when paused)
are "skipped" — they neither count toward the streak nor break it.

All walkers start at today - 1 (Phase E plan decision 5): today's
tasks may not be done yet by the 03:00 IST cron, so don't punish.

These functions are pure: no I/O beyond the reflection-file read in
weekly_review_streak (which is filesystem-only, no network).
"""

from __future__ import annotations

from datetime import date, timedelta
from pathlib import Path
from typing import Any

from src.ids import external_id
from src.reflections import split_frontmatter
from src.state import State

DAILY_TEMPLATES_REQUIRED = ("daily-anki", "daily-morning-reading")
WEEKLY_REVIEW_TEMPLATE = "weekly-friday-review"
MONTHLY_POST_TEMPLATE = "monthly-blog-post"

FRIDAY = 4
SUNDAY = 6


def _is_in_pause_window(d: date, state: State) -> bool:
    """Inside a closed pause_history interval, or in the open paused_since window."""
    for interval in state.pause_history:
        if interval.start <= d <= interval.end:
            return True
    if state.paused and state.paused_since is not None and d >= state.paused_since:
        return True
    return False


def _is_skipped_on(d: date, state: State) -> bool:
    """Daily-streak skip-day: Sunday OR inside a pause window.

    Sunday-skip applies only to daily streaks (anki + morning-reading both
    have skip_if=sunday, so absence on Sunday is not a break). Weekly and
    monthly walkers use _is_in_pause_window directly: Friday is never a
    Sunday, and the monthly-blog-post fires on day-1 even when that day-1
    lands on a Sunday.
    """
    return d.weekday() == SUNDAY or _is_in_pause_window(d, state)


def _external_id_for_daily(template_id: str, d: date) -> str:
    """Helper for callers that want the same id the engine wrote into the cache."""
    return external_id(template_id, d)


def _task_id_for(
    template_id: str, due_date: date, cache: dict[str, Any]
) -> str | None:
    ext_id = external_id(template_id, due_date)
    entry = cache.get(ext_id)
    if entry is None:
        return None
    tid = entry.get("todoist_task_id")
    return str(tid) if tid else None


def _all_required_done(
    d: date, cache: dict[str, Any], completion_set: set[str]
) -> bool:
    for tpl in DAILY_TEMPLATES_REQUIRED:
        tid = _task_id_for(tpl, d, cache)
        if tid is None or tid not in completion_set:
            return False
    return True


def daily_streak(
    today: date,
    state: State,
    cache: dict[str, Any],
    completion_set: set[str],
) -> int:
    """Count consecutive prior days where both required dailies completed."""
    streak = 0
    d = today - timedelta(days=1)
    while d >= state.start_date:
        if _is_skipped_on(d, state):
            d -= timedelta(days=1)
            continue
        if _all_required_done(d, cache, completion_set):
            streak += 1
            d -= timedelta(days=1)
        else:
            break
    return streak


def _most_recent_friday_le(d: date) -> date:
    """The Friday on or before d."""
    delta = (d.weekday() - FRIDAY) % 7
    return d - timedelta(days=delta)


def _previous_month_first_day(d: date) -> date:
    """The first day of the month immediately before d (which is itself a day-1)."""
    if d.month == 1:
        return date(d.year - 1, 12, 1)
    return date(d.year, d.month - 1, 1)


def _reflection_status_filled(path: Path) -> bool:
    if not path.exists():
        return False
    try:
        text = path.read_text(encoding="utf-8")
    except OSError:
        return False
    fm, _ = split_frontmatter(text)
    return fm.get("status") == "filled"


def weekly_review_streak(
    today: date,
    state: State,
    cache: dict[str, Any],
    completion_set: set[str],
    reflections_root: Path,
) -> int:
    """Walk Fridays back; require both Todoist completion + reflection filled."""
    streak = 0
    yesterday = today - timedelta(days=1)
    d = _most_recent_friday_le(yesterday)
    while d >= state.start_date:
        if _is_in_pause_window(d, state):
            d -= timedelta(days=7)
            continue
        tid = _task_id_for(WEEKLY_REVIEW_TEMPLATE, d, cache)
        if tid is None or tid not in completion_set:
            break
        iso_year, iso_week, _ = d.isocalendar()
        ref_path = reflections_root / "weekly" / f"{iso_year}-W{iso_week:02d}.md"
        if not _reflection_status_filled(ref_path):
            break
        streak += 1
        d -= timedelta(days=7)
    return streak


def monthly_post_streak(
    today: date,
    state: State,
    cache: dict[str, Any],
    completion_set: set[str],
) -> int:
    """Walk month-day-1s back; require Todoist completion of monthly-blog-post."""
    streak = 0
    yesterday = today - timedelta(days=1)
    d = yesterday.replace(day=1)
    start_month_first = state.start_date.replace(day=1)
    while d >= start_month_first:
        if _is_in_pause_window(d, state):
            d = _previous_month_first_day(d)
            continue
        tid = _task_id_for(MONTHLY_POST_TEMPLATE, d, cache)
        if tid is None or tid not in completion_set:
            break
        streak += 1
        d = _previous_month_first_day(d)
    return streak
