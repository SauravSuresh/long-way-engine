from datetime import date
from pathlib import Path
from zoneinfo import ZoneInfo

from src.ids import external_id
from src.state import PauseInterval, State
from src.streaks import (
    _is_skipped_on,
    _most_recent_friday_le,
    daily_streak,
    monthly_post_streak,
    weekly_review_streak,
)

IST = ZoneInfo("Asia/Kolkata")


def make_state(
    start: date = date(2026, 1, 1),
    paused: bool = False,
    paused_since: date | None = None,
    pause_history: list[PauseInterval] | None = None,
) -> State:
    return State(
        start_date=start,
        timezone=IST,
        phase=1,
        month=1,
        current_module=1,
        current_book="x",
        paused=paused,
        paused_since=paused_since,
        pause_history=pause_history or [],
    )


def cache_entry(template_id: str, d: date, task_id: str) -> tuple[str, dict]:
    ext = external_id(template_id, d)
    return ext, {
        "todoist_task_id": task_id,
        "created_at": "2026-05-04T03:00:00+00:00",
        "template_id": template_id,
        "due_date": d.isoformat(),
    }


def add_daily_pair(cache: dict, d: date) -> tuple[str, str]:
    """Add anki + morning-reading entries for date d. Returns (anki_id, morning_id)."""
    anki_ext, anki_e = cache_entry("daily-anki", d, f"anki-{d.isoformat()}")
    morn_ext, morn_e = cache_entry("daily-morning-reading", d, f"morn-{d.isoformat()}")
    cache[anki_ext] = anki_e
    cache[morn_ext] = morn_e
    return anki_e["todoist_task_id"], morn_e["todoist_task_id"]


# --- _is_skipped_on -----------------------------------------------------------


def test_is_skipped_sunday():
    assert _is_skipped_on(date(2026, 5, 3), make_state()) is True  # Sunday


def test_is_skipped_monday_not():
    assert _is_skipped_on(date(2026, 5, 4), make_state()) is False  # Monday


def test_is_skipped_inside_pause_history():
    state = make_state(pause_history=[
        PauseInterval(date(2026, 4, 15), date(2026, 4, 30), "travel")
    ])
    assert _is_skipped_on(date(2026, 4, 20), state) is True
    assert _is_skipped_on(date(2026, 4, 15), state) is True  # boundary
    assert _is_skipped_on(date(2026, 4, 30), state) is True  # boundary
    assert _is_skipped_on(date(2026, 5, 1), state) is False


def test_is_skipped_currently_paused():
    state = make_state(paused=True, paused_since=date(2026, 5, 4))
    assert _is_skipped_on(date(2026, 5, 4), state) is True
    assert _is_skipped_on(date(2026, 5, 6), state) is True
    # May 2 is a Saturday strictly before paused_since.
    assert _is_skipped_on(date(2026, 5, 2), state) is False


# --- _most_recent_friday_le ---------------------------------------------------


def test_friday_le_friday_returns_self():
    assert _most_recent_friday_le(date(2026, 5, 8)) == date(2026, 5, 8)  # Friday


def test_friday_le_monday_walks_back():
    # 2026-05-04 is Monday -> previous Friday is 2026-05-01
    assert _most_recent_friday_le(date(2026, 5, 4)) == date(2026, 5, 1)


def test_friday_le_thursday_walks_back_six():
    # Thursday -> previous Friday is 6 days earlier
    assert _most_recent_friday_le(date(2026, 5, 7)) == date(2026, 5, 1)


# --- daily_streak -------------------------------------------------------------


def test_daily_streak_zero_when_no_data():
    state = make_state(start=date(2026, 5, 1))
    assert daily_streak(date(2026, 5, 4), state, {}, set()) == 0


def test_daily_streak_three_consecutive():
    """Mon-Tue-Wed before Thu: 3 days, all done. Today=Thu."""
    state = make_state(start=date(2026, 5, 1))
    cache: dict = {}
    done: set[str] = set()
    for d in (date(2026, 5, 4), date(2026, 5, 5), date(2026, 5, 6)):  # Mon, Tue, Wed
        a, m = add_daily_pair(cache, d)
        done.update([a, m])
    assert daily_streak(date(2026, 5, 7), state, cache, done) == 3


def test_daily_streak_breaks_on_partial_day():
    """If only anki done one day, streak breaks there."""
    state = make_state(start=date(2026, 5, 1))
    cache: dict = {}
    done: set[str] = set()
    # day -1 (yesterday Wed): both done
    a1, m1 = add_daily_pair(cache, date(2026, 5, 6))
    done.update([a1, m1])
    # day -2 (Tue): only anki done
    a2, m2 = add_daily_pair(cache, date(2026, 5, 5))
    done.add(a2)  # not m2
    # day -3 (Mon): both done — but unreachable
    a3, m3 = add_daily_pair(cache, date(2026, 5, 4))
    done.update([a3, m3])
    assert daily_streak(date(2026, 5, 7), state, cache, done) == 1


def test_daily_streak_skips_sunday_without_breaking():
    """Sun in middle of streak doesn't break. Today=Mon, streak walks Sun, Sat, Fri..."""
    state = make_state(start=date(2026, 4, 30))
    cache: dict = {}
    done: set[str] = set()
    # Yesterday=Sun (skipped), Sat, Fri all done.
    for d in (date(2026, 5, 2), date(2026, 5, 1), date(2026, 4, 30)):
        a, m = add_daily_pair(cache, d)
        done.update([a, m])
    # No anki/morning entries created on Sunday because skip_if=sunday — that's
    # the realistic state. Streak walks Sun (skip), Sat (done), Fri (done), Thu...
    streak = daily_streak(date(2026, 5, 4), state, cache, done)  # Mon
    assert streak == 3  # Sat + Fri + Thu (Thu=Apr 30 = start_date)


def test_daily_streak_skips_pause_history():
    """Days inside pause_history are skipped without breaking."""
    state = make_state(
        start=date(2026, 4, 1),
        pause_history=[PauseInterval(date(2026, 4, 15), date(2026, 4, 30), "x")],
    )
    cache: dict = {}
    done: set[str] = set()
    # Yesterday May 3 is Sunday (skipped).
    # May 1, May 2 are completed days. Then April 15-30 paused (skip).
    # April 14 not done -> break there.
    for d in (date(2026, 5, 2), date(2026, 5, 1)):
        a, m = add_daily_pair(cache, d)
        done.update([a, m])
    # Add April 14 + 13 with task_id but NOT in completion set (so they'd break)
    add_daily_pair(cache, date(2026, 4, 14))
    streak = daily_streak(date(2026, 5, 4), state, cache, done)  # Mon
    # May 3=Sun(skip), May 2=Sat(done), May 1=Fri(done), Apr 30 - Apr 15 (skipped
    # via pause), Apr 14 not done -> break. streak = 2.
    assert streak == 2


def test_daily_streak_skips_currently_paused_window():
    state = make_state(
        start=date(2026, 4, 1),
        paused=True,
        paused_since=date(2026, 5, 1),
    )
    cache: dict = {}
    done: set[str] = set()
    # Apr 30 done.
    for d in (date(2026, 4, 30),):
        a, m = add_daily_pair(cache, d)
        done.update([a, m])
    # Yesterday May 3 paused (skip), May 2 paused (skip), May 1 paused (skip),
    # Apr 30 done -> streak 1, Apr 29 not in cache -> break.
    streak = daily_streak(date(2026, 5, 4), state, cache, done)
    assert streak == 1


def test_daily_streak_walks_back_only_to_start_date():
    state = make_state(start=date(2026, 5, 4))
    cache: dict = {}
    done: set[str] = set()
    # Yesterday is May 3 (Sunday), bounded by start.
    streak = daily_streak(date(2026, 5, 4), state, cache, done)
    assert streak == 0  # nothing past start_date


# --- weekly_review_streak -----------------------------------------------------


def add_weekly_review(
    cache: dict, d: date, completion_set: set[str], task_id: str | None = None
) -> str:
    tid = task_id or f"wfr-{d.isoformat()}"
    ext, entry = cache_entry("weekly-friday-review", d, tid)
    cache[ext] = entry
    completion_set.add(tid)
    return tid


def write_filled_reflection(reflections_root: Path, d: date, status: str = "filled") -> None:
    iso = d.isocalendar()
    p = reflections_root / "weekly" / f"{iso.year}-W{iso.week:02d}.md"
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(
        f"---\nstatus: {status}\nword_count: 999\n---\nbody\n",
        encoding="utf-8",
    )


def test_weekly_streak_two_fridays(tmp_path: Path):
    state = make_state(start=date(2026, 1, 1))
    cache: dict = {}
    done: set[str] = set()
    # Today = Sat 2026-05-09, yesterday = Fri 5-8 (this Friday).
    for fri in (date(2026, 5, 8), date(2026, 5, 1)):
        add_weekly_review(cache, fri, done)
        write_filled_reflection(tmp_path, fri)
    streak = weekly_review_streak(date(2026, 5, 9), state, cache, done, tmp_path)
    assert streak == 2


def test_weekly_streak_breaks_when_reflection_not_filled(tmp_path: Path):
    state = make_state(start=date(2026, 1, 1))
    cache: dict = {}
    done: set[str] = set()
    add_weekly_review(cache, date(2026, 5, 8), done)
    write_filled_reflection(tmp_path, date(2026, 5, 8))
    add_weekly_review(cache, date(2026, 5, 1), done)
    write_filled_reflection(tmp_path, date(2026, 5, 1), status="stub")  # not filled
    streak = weekly_review_streak(date(2026, 5, 9), state, cache, done, tmp_path)
    assert streak == 1


def test_weekly_streak_breaks_when_task_not_completed(tmp_path: Path):
    state = make_state(start=date(2026, 1, 1))
    cache: dict = {}
    done: set[str] = set()
    add_weekly_review(cache, date(2026, 5, 8), done)
    write_filled_reflection(tmp_path, date(2026, 5, 8))
    # Friday May 1: cache exists but task_id NOT in completion_set
    ext, entry = cache_entry("weekly-friday-review", date(2026, 5, 1), "tid-x")
    cache[ext] = entry
    write_filled_reflection(tmp_path, date(2026, 5, 1))
    streak = weekly_review_streak(date(2026, 5, 9), state, cache, done, tmp_path)
    assert streak == 1


def test_weekly_streak_skips_friday_inside_pause(tmp_path: Path):
    state = make_state(
        start=date(2026, 1, 1),
        pause_history=[PauseInterval(date(2026, 4, 20), date(2026, 5, 5), "x")],
    )
    cache: dict = {}
    done: set[str] = set()
    # Today=Sat 5-9, Fri 5-8 done & filled, Fri 5-1 inside pause (skip without
    # breaking), Fri 4-24 inside pause (skip), Fri 4-17 done & filled.
    for fri in (date(2026, 5, 8), date(2026, 4, 17)):
        add_weekly_review(cache, fri, done)
        write_filled_reflection(tmp_path, fri)
    streak = weekly_review_streak(date(2026, 5, 9), state, cache, done, tmp_path)
    assert streak == 2


def test_weekly_streak_excludes_today_if_today_is_friday(tmp_path: Path):
    """Today = Fri; streak starts from yesterday's nearest Friday (= last Friday)."""
    state = make_state(start=date(2026, 1, 1))
    cache: dict = {}
    done: set[str] = set()
    add_weekly_review(cache, date(2026, 5, 1), done)
    write_filled_reflection(tmp_path, date(2026, 5, 1))
    # Today is Fri 2026-05-08. We walk back from yesterday's Friday-le = May 1.
    streak = weekly_review_streak(date(2026, 5, 8), state, cache, done, tmp_path)
    assert streak == 1


# --- monthly_post_streak ------------------------------------------------------


def test_monthly_streak_two_months():
    """Today = May 1; yesterday is Apr 30; first month-day-1 walked is Apr 1."""
    state = make_state(start=date(2026, 1, 1))
    cache: dict = {}
    done: set[str] = set()
    for d in (date(2026, 4, 1), date(2026, 3, 1)):
        ext, entry = cache_entry("monthly-blog-post", d, f"mb-{d.isoformat()}")
        cache[ext] = entry
        done.add(entry["todoist_task_id"])
    streak = monthly_post_streak(date(2026, 5, 1), state, cache, done)
    assert streak == 2


def test_monthly_streak_breaks_on_missing_post():
    """Today = May 1; April done, March not -> streak breaks at March."""
    state = make_state(start=date(2026, 1, 1))
    cache: dict = {}
    done: set[str] = set()
    ext, entry = cache_entry("monthly-blog-post", date(2026, 4, 1), "mb-apr")
    cache[ext] = entry
    done.add("mb-apr")
    streak = monthly_post_streak(date(2026, 5, 1), state, cache, done)
    assert streak == 1


def test_monthly_streak_breaks_when_current_month_post_missing():
    """Past day-1 of current month with no post -> streak breaks immediately."""
    state = make_state(start=date(2026, 1, 1))
    cache: dict = {}
    done: set[str] = set()
    # April + March done, but May 1 not done. Today=May 4 means May 1 is in scope.
    for d in (date(2026, 4, 1), date(2026, 3, 1)):
        ext, entry = cache_entry("monthly-blog-post", d, f"mb-{d.isoformat()}")
        cache[ext] = entry
        done.add(entry["todoist_task_id"])
    streak = monthly_post_streak(date(2026, 5, 4), state, cache, done)
    assert streak == 0


def test_monthly_streak_zero_when_no_history():
    state = make_state(start=date(2026, 5, 1))
    streak = monthly_post_streak(date(2026, 5, 4), state, {}, set())
    assert streak == 0


def test_monthly_streak_excludes_current_month():
    """Day 1 of current month with completion still doesn't count if today is later
    in the month — wait, actually: today=May 4, yesterday=May 3, walk back to
    May 1 of current month. So current month's day 1 IS included."""
    state = make_state(start=date(2026, 1, 1))
    cache: dict = {}
    done: set[str] = set()
    ext, entry = cache_entry("monthly-blog-post", date(2026, 5, 1), "mb-may")
    cache[ext] = entry
    done.add("mb-may")
    streak = monthly_post_streak(date(2026, 5, 4), state, cache, done)
    assert streak == 1
