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


# --- best-streak walkers ------------------------------------------------------
#
# "Best" means longest consecutive run from state.start_date up to (but not
# including) today. A current streak ≤ best by construction; the dashboard
# uses best as a frame of reference so 0 doesn't read as "engine never
# worked."


def best_daily_streak(
    today: date,
    state: State,
    cache: dict[str, Any],
    completion_set: set[str],
) -> int:
    best = 0
    cur = 0
    d = state.start_date
    while d < today:
        if _is_skipped_on(d, state):
            d += timedelta(days=1)
            continue
        if _all_required_done(d, cache, completion_set):
            cur += 1
            if cur > best:
                best = cur
        else:
            cur = 0
        d += timedelta(days=1)
    return best


def best_weekly_review_streak(
    today: date,
    state: State,
    cache: dict[str, Any],
    completion_set: set[str],
    reflections_root: Path,
) -> int:
    best = 0
    cur = 0
    yesterday = today - timedelta(days=1)
    end_friday = _most_recent_friday_le(yesterday)
    # First Friday on or after start_date.
    first_friday_delta = (FRIDAY - state.start_date.weekday()) % 7
    d = state.start_date + timedelta(days=first_friday_delta)
    while d <= end_friday:
        if _is_in_pause_window(d, state):
            d += timedelta(days=7)
            continue
        tid = _task_id_for(WEEKLY_REVIEW_TEMPLATE, d, cache)
        iso_year, iso_week, _ = d.isocalendar()
        ref_path = reflections_root / "weekly" / f"{iso_year}-W{iso_week:02d}.md"
        if (
            tid is not None
            and tid in completion_set
            and _reflection_status_filled(ref_path)
        ):
            cur += 1
            if cur > best:
                best = cur
        else:
            cur = 0
        d += timedelta(days=7)
    return best


def best_monthly_post_streak(
    today: date,
    state: State,
    cache: dict[str, Any],
    completion_set: set[str],
) -> int:
    best = 0
    cur = 0
    yesterday = today - timedelta(days=1)
    end_first = yesterday.replace(day=1)
    d = state.start_date.replace(day=1)
    while d <= end_first:
        if _is_in_pause_window(d, state):
            d = _next_month_first_day(d)
            continue
        tid = _task_id_for(MONTHLY_POST_TEMPLATE, d, cache)
        if tid is not None and tid in completion_set:
            cur += 1
            if cur > best:
                best = cur
        else:
            cur = 0
        d = _next_month_first_day(d)
    return best


def _next_month_first_day(d: date) -> date:
    if d.month == 12:
        return date(d.year + 1, 1, 1)
    return date(d.year, d.month + 1, 1)


# --- one-line hints -----------------------------------------------------------
#
# Sub-label rendered under each streak count. Tells the owner *why* the
# number is what it is and what would change it. Deterministic strings;
# no randomness or LLM.


def _is_currently_paused(state: State, today: date) -> bool:
    if state.paused:
        return True
    return _is_in_pause_window(today, state)


def _plural(n: int, unit: str) -> str:
    return f"{n} {unit}{'s' if n != 1 else ''}"


def adherence_since_start(
    today: date,
    state: State,
    cache: dict[str, Any],
    completion_set: set[str],
) -> tuple[int, int]:
    """Returns (done, expected) counted from state.start_date through yesterday.

    Expected = non-Sunday, non-paused days since start. Today itself is
    excluded because the cron renders at 05:30 and today's tasks aren't
    done yet.
    """
    done = 0
    expected = 0
    d = state.start_date
    while d < today:
        if _is_skipped_on(d, state):
            d += timedelta(days=1)
            continue
        expected += 1
        if _all_required_done(d, cache, completion_set):
            done += 1
        d += timedelta(days=1)
    return done, expected


def daily_hint(today: date, state: State, current: int) -> str:
    if today < state.start_date:
        return f"starts {state.start_date.isoformat()}"
    if _is_currently_paused(state, today):
        return "paused"
    if today.weekday() == SUNDAY:
        return "Sunday — rest day"
    if current == 0:
        return "complete morning reading + Anki today to start"
    return "morning reading + Anki by 23:59 to keep it"


def weekly_hint(today: date, state: State, current: int) -> str:
    if today < state.start_date:
        return f"starts {state.start_date.isoformat()}"
    if _is_currently_paused(state, today):
        return "paused"
    if today.weekday() == FRIDAY:
        return "Friday review + filled reflection due today"
    days_to_friday = (FRIDAY - today.weekday()) % 7
    if days_to_friday == 0:
        days_to_friday = 7
    return f"next Friday in {_plural(days_to_friday, 'day')}"


def monthly_hint(today: date, state: State, current: int) -> str:
    if today < state.start_date:
        return f"starts {state.start_date.isoformat()}"
    if _is_currently_paused(state, today):
        return "paused"
    if today.day == 1:
        return "monthly post due today"
    next_first = _next_month_first_day(today)
    days = (next_first - today).days
    return f"next post in {_plural(days, 'day')}"
