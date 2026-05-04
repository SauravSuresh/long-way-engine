"""Phase E dashboard tests.

Includes snapshot tests for four states: empty, partial, full, paused.
Fixtures live at tests/fixtures/dashboard/*.html. Set DASHBOARD_REGEN=1
in the env to regenerate fixture files (run + diff manually before
committing).
"""

from __future__ import annotations

import os
from datetime import date
from pathlib import Path
from zoneinfo import ZoneInfo

import pytest

from src.clock import FrozenClock
from src.config import Config, DashboardConfig, TodoistConfig
from src.dashboard import (
    CSS,
    ReflectionMeta,
    _github_blob_url,
    _last_7_color,
    _paused_summary,
    render,
    scan_reflections,
    write_css_if_absent,
)
from src.ids import external_id
from src.state import PauseInterval, State
from src.syllabus import Book

IST = ZoneInfo("Asia/Kolkata")
FIXTURES = Path(__file__).parent / "fixtures" / "dashboard"
REGEN = os.environ.get("DASHBOARD_REGEN") == "1"


def make_config() -> Config:
    return Config(
        todoist=TodoistConfig(project_id="p", labels={}),
        ritual_times={"morning_reading": "06:00", "anki": "08:30"},
        sunday_off=True,
        dashboard=DashboardConfig(
            github_username="SauravSuresh", repo_name="long-way-engine"
        ),
        todoist_token="t",
        pair_day="thursday",
    )


def make_state(**overrides) -> State:
    base = dict(
        start_date=date(2026, 1, 1),
        timezone=IST,
        phase=1,
        month=4,
        current_module=2,
        current_book="Computer Systems: A Programmer's Perspective",
        paused=False,
        paused_since=None,
        pause_history=[],
        books_state={},
        learning_tracks={},
        manual_counters={"traces_completed": 0, "prs_opened": 0},
    )
    base.update(overrides)
    return State(**base)


def add_daily_pair(cache: dict, d: date, completion: set[str]) -> None:
    for tpl in ("daily-anki", "daily-morning-reading"):
        ext = external_id(tpl, d)
        tid = f"{tpl}-{d.isoformat()}"
        cache[ext] = {
            "todoist_task_id": tid,
            "created_at": "2026-05-04T03:00:00+00:00",
            "template_id": tpl,
            "due_date": d.isoformat(),
        }
        completion.add(tid)


# --- helpers + small units ----------------------------------------------------


def test_paused_summary_open_window():
    state = make_state(paused=True, paused_since=date(2026, 5, 1))
    assert _paused_summary(state, date(2026, 5, 4)) == "Paused since 2026-05-01 (3 days)"


def test_paused_summary_paused_no_since():
    state = make_state(paused=True, paused_since=None)
    assert _paused_summary(state, date(2026, 5, 4)) == "Paused"


def test_paused_summary_not_paused():
    assert _paused_summary(make_state(), date(2026, 5, 4)) is None


def test_github_blob_url():
    cfg = make_config()
    assert _github_blob_url(cfg, "weekly/2026-W18.md") == (
        "https://github.com/SauravSuresh/long-way-engine/blob/main/"
        "reflections/weekly/2026-W18.md"
    )


def test_last_7_color_gray_on_sunday():
    assert _last_7_color(date(2026, 5, 3), make_state(), {}, set()) == "gray"


def test_last_7_color_gray_in_pause_history():
    state = make_state(
        pause_history=[PauseInterval(date(2026, 4, 15), date(2026, 4, 30), "x")]
    )
    assert _last_7_color(date(2026, 4, 20), state, {}, set()) == "gray"


def test_last_7_color_gray_when_currently_paused():
    state = make_state(paused=True, paused_since=date(2026, 5, 1))
    assert _last_7_color(date(2026, 5, 4), state, {}, set()) == "gray"


def test_last_7_color_green_both_done():
    cache: dict = {}
    done: set[str] = set()
    add_daily_pair(cache, date(2026, 5, 4), done)  # Monday
    assert _last_7_color(date(2026, 5, 4), make_state(), cache, done) == "green"


def test_last_7_color_yellow_one_done():
    cache: dict = {}
    done: set[str] = set()
    ext = external_id("daily-anki", date(2026, 5, 4))
    cache[ext] = {
        "todoist_task_id": "anki-tid",
        "created_at": "x",
        "template_id": "daily-anki",
        "due_date": "2026-05-04",
    }
    done.add("anki-tid")
    assert _last_7_color(date(2026, 5, 4), make_state(), cache, done) == "yellow"


def test_last_7_color_red_neither():
    assert _last_7_color(date(2026, 5, 4), make_state(), {}, set()) == "red"


def test_last_7_color_gray_before_start_date():
    """Days before state.start_date are outside the journey — gray, not red."""
    state = make_state(start_date=date(2026, 5, 5))
    # 2026-05-02 is a Saturday (would normally be red without completions),
    # but it's before start_date — should render gray.
    assert _last_7_color(date(2026, 5, 2), state, {}, set()) == "gray"
    assert _last_7_color(date(2026, 5, 4), state, {}, set()) == "gray"  # day before start
    # Start date itself and after are normal.
    assert _last_7_color(date(2026, 5, 5), state, {}, set()) == "red"


def test_scan_reflections_reads_frontmatter(tmp_path: Path):
    weekly = tmp_path / "weekly"
    weekly.mkdir()
    (weekly / "2026-W18.md").write_text(
        "---\nstatus: filled\nword_count: 412\n---\nbody",
        encoding="utf-8",
    )
    (weekly / "2026-W17.md").write_text(
        "---\nstatus: stub\nword_count: 0\n---\n",
        encoding="utf-8",
    )
    refs = scan_reflections(tmp_path)
    by_file = {r.file: r for r in refs}
    assert by_file["2026-W18"].status == "filled"
    assert by_file["2026-W18"].word_count == 412
    assert by_file["2026-W17"].status == "stub"
    assert by_file["2026-W17"].relative_path == "weekly/2026-W17.md"


def test_write_css_if_absent_writes_once(tmp_path: Path):
    p = tmp_path / "style.css"
    assert write_css_if_absent(p) is True
    assert p.read_text(encoding="utf-8") == CSS
    # Second call: present, no write.
    p.write_text("EDITED", encoding="utf-8")
    assert write_css_if_absent(p) is False
    assert p.read_text(encoding="utf-8") == "EDITED"


# --- snapshot fixtures --------------------------------------------------------


def _assert_or_regen(name: str, html: str) -> None:
    fixture = FIXTURES / name
    if REGEN or not fixture.exists():
        fixture.parent.mkdir(parents=True, exist_ok=True)
        fixture.write_text(html, encoding="utf-8")
        if not REGEN:
            pytest.skip(f"bootstrapped fixture {name}; rerun")
    expected = fixture.read_text(encoding="utf-8")
    assert html == expected, f"snapshot mismatch for {name}; set DASHBOARD_REGEN=1 to regen"


def _empty_inputs(today: date, tmp_root: Path):
    state = make_state(month=1)
    return (
        state,
        make_config(),
        set(),         # completion_set
        {},            # cache
        [],            # reflections
        [],            # books
        today,
        FrozenClock(today, IST),
        tmp_root,      # reflections_root (empty)
    )


def _partial_inputs(today: date, tmp_root: Path):
    cache: dict = {}
    done: set[str] = set()
    # Some daily pairs done in last 7 days
    for d in (date(2026, 5, 1), date(2026, 5, 2), date(2026, 4, 30)):
        add_daily_pair(cache, d, done)
    state = make_state(
        month=4,
        manual_counters={"traces_completed": 3, "prs_opened": 1, "pair_sessions": 2},
        books_state={
            "Computer Systems: A Programmer's Perspective": "current",
            "Computer Networking: A Top-Down Approach": "not_started",
        },
    )
    refs = [
        ReflectionMeta("weekly", "2026-W17", "filled", 412, "weekly/2026-W17.md"),
        ReflectionMeta("monthly", "2026-04", "stub", 12, "monthly/2026-04.md"),
    ]
    books = [
        Book(phase=1, title="Computer Systems: A Programmer's Perspective",
             author="Bryant & O'Hallaron", start_month=1, end_month=6),
        Book(phase=1, title="Computer Networking: A Top-Down Approach",
             author="Kurose & Ross", start_month=7, end_month=10),
    ]
    return (
        state, make_config(), done, cache, refs, books,
        today, FrozenClock(today, IST), tmp_root,
    )


def _full_inputs(today: date, tmp_root: Path):
    cache: dict = {}
    done: set[str] = set()
    # Full last-7 (excluding Sundays) of dailies
    from datetime import timedelta
    for offset in range(1, 8):
        d = today - timedelta(days=offset)
        if d.weekday() != 6:
            add_daily_pair(cache, d, done)
    # weekly-friday-review and reflection
    fri = date(2026, 5, 1)
    for tpl in ("weekly-friday-review",):
        ext = external_id(tpl, fri)
        tid = f"{tpl}-{fri.isoformat()}"
        cache[ext] = {
            "todoist_task_id": tid,
            "created_at": "x",
            "template_id": tpl,
            "due_date": fri.isoformat(),
        }
        done.add(tid)
    # Add some weekly-read-real-code completions
    for sat in (date(2026, 5, 2), date(2026, 4, 25)):
        ext = external_id("weekly-read-real-code", sat)
        tid = f"wrr-{sat.isoformat()}"
        cache[ext] = {
            "todoist_task_id": tid,
            "created_at": "x",
            "template_id": "weekly-read-real-code",
            "due_date": sat.isoformat(),
        }
        done.add(tid)
    # weekly reflection filled on disk for the streak walker
    weekly_dir = tmp_root / "weekly"
    weekly_dir.mkdir(parents=True, exist_ok=True)
    (weekly_dir / "2026-W18.md").write_text(
        "---\nstatus: filled\nword_count: 600\n---\nbody",
        encoding="utf-8",
    )
    state = make_state(
        month=8, phase=1, current_module=8,
        current_book="Computer Networking: A Top-Down Approach",
        manual_counters={"traces_completed": 12, "prs_opened": 4, "pair_sessions": 9},
        books_state={
            "Computer Systems: A Programmer's Perspective": "done",
            "Computer Networking: A Top-Down Approach": "current",
            "The Go Programming Language": "not_started",
        },
        learning_tracks={
            "Courses": {
                "boot.dev backend path": "current",
                "boot.dev DSA": "current",
                "boot.dev C memory": "not_started",
            },
            "Active branches": {
                "Text editor in C": "current",
                "Toy DNS resolver": "not_started",
            },
            "Certifications": {
                "LFCS": "current",
                "AWS SAA": "not_started",
            },
        },
    )
    refs = [
        ReflectionMeta("weekly", "2026-W18", "filled", 600, "weekly/2026-W18.md"),
        ReflectionMeta("weekly", "2026-W17", "filled", 580, "weekly/2026-W17.md"),
        ReflectionMeta("monthly", "2026-04", "filled", 1100, "monthly/2026-04.md"),
        ReflectionMeta("quarterly", "2026-Q1", "filled", 2000, "quarterly/2026-Q1.md"),
    ]
    books = [
        Book(phase=1, title="Computer Systems: A Programmer's Perspective",
             author="Bryant & O'Hallaron", start_month=1, end_month=6),
        Book(phase=1, title="Computer Networking: A Top-Down Approach",
             author="Kurose & Ross", start_month=7, end_month=10),
        Book(phase=2, title="The Go Programming Language",
             author="Donovan & Kernighan", start_month=14, end_month=18),
    ]
    return (
        state, make_config(), done, cache, refs, books,
        today, FrozenClock(today, IST), tmp_root,
    )


def _paused_inputs(today: date, tmp_root: Path):
    state = make_state(
        month=4,
        paused=True,
        paused_since=date(2026, 5, 1),
        pause_history=[PauseInterval(date(2026, 3, 1), date(2026, 3, 15), "travel")],
        manual_counters={"traces_completed": 5, "prs_opened": 2, "pair_sessions": 4},
    )
    cache: dict = {}
    done: set[str] = set()
    # Some pre-pause completions to verify streak preserved
    for d in (date(2026, 4, 28), date(2026, 4, 29), date(2026, 4, 30)):
        add_daily_pair(cache, d, done)
    refs = [
        ReflectionMeta("weekly", "2026-W17", "filled", 500, "weekly/2026-W17.md"),
    ]
    books: list[Book] = []
    return (
        state, make_config(), done, cache, refs, books,
        today, FrozenClock(today, IST), tmp_root,
    )


@pytest.mark.parametrize(
    "name, builder",
    [
        ("empty.html", _empty_inputs),
        ("partial.html", _partial_inputs),
        ("full.html", _full_inputs),
        ("paused.html", _paused_inputs),
    ],
)
def test_dashboard_snapshot(tmp_path: Path, name: str, builder):
    today = date(2026, 5, 4)  # Monday
    inputs = builder(today, tmp_path)
    html, data = render(*inputs)
    assert isinstance(html, str)
    assert isinstance(data, dict)
    assert "today" in data and data["today"] == today.isoformat()
    _assert_or_regen(name, html)


def test_render_returns_data_with_streaks(tmp_path: Path):
    today = date(2026, 5, 4)
    inputs = _empty_inputs(today, tmp_path)
    _, data = render(*inputs)
    assert set(data["streaks"].keys()) == {"Daily", "Weekly review", "Monthly post"}
    assert all(isinstance(v, int) for v in data["streaks"].values())


def test_render_last_7_data_has_seven_entries(tmp_path: Path):
    today = date(2026, 5, 4)
    _, data = render(*_partial_inputs(today, tmp_path))
    assert len(data["last_7_days"]) == 7
    assert all(set(d.keys()) == {"date", "state"} for d in data["last_7_days"])


def test_render_paused_data_includes_pause_summary(tmp_path: Path):
    today = date(2026, 5, 4)
    _, data = render(*_paused_inputs(today, tmp_path))
    assert data["paused"] == "Paused since 2026-05-01 (3 days)"
