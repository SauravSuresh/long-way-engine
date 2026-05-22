"""Phase E dashboard renderer.

Pure deterministic HTML generator. Inputs go in, (html, data_json) come
out — no system clock, no random ordering, no network. The caller (main)
provides the clock-frozen `today` and the pre-fetched completion set.

Eight sections, no creep:

  1. _header        — title, date, current phase + module + book.
  2. _streaks       — daily, weekly review, monthly post counts.
  3. _progress_bar  — month-of-39 with Phase tick marks.
  4. _last_7_days   — color-coded grid of yesterday-and-back-six.
  5. _practice_tracker — code reading + 3 manual_counters.
  6. _books         — per-phase book list with state badge.
  7. _reflection_log   — reverse-chrono with GitHub blob link.
  8. _footer        — generation timestamp.

CSS is committed once to docs/assets/style.css and never regenerated.
"""

from __future__ import annotations

import html as _html
from calendar import monthrange
from dataclasses import asdict, dataclass, field
from datetime import date, timedelta
from pathlib import Path
from typing import Any

from src.clock import Clock
from src.config import Config
from src.ids import external_id
from src.reflections import split_frontmatter
from src.state import State
from src.streaks import (
    DAILY_TEMPLATES_REQUIRED,
    _is_in_pause_window,
    adherence_since_start,
    best_daily_streak,
    best_monthly_post_streak,
    best_weekly_review_streak,
    daily_hint,
    daily_streak,
    monthly_hint,
    monthly_post_streak,
    weekly_hint,
    weekly_review_streak,
)
from src.syllabus import Book, Syllabus

# Defaults — kept for any legacy caller that doesn't pass a Syllabus.
# render() recomputes from the live syllabus and overrides locally before
# calling helpers. Phase 1 = months 1–12, Phase 2 = 13–20, Phase 3 = 21–30,
# Phase 4 = 31–39.
DEFAULT_TOTAL_MONTHS = 39
DEFAULT_TOTAL_MODULES = 23
DEFAULT_PHASE_BOUNDARIES = (1, 13, 21, 31, 39)
PHASE_LABELS = ("Phase 1", "Phase 2", "Phase 3", "Phase 4", "End")
# Fallback phase-tick labels match the live curriculum/syllabus.yaml so
# render() output stays byte-identical when syllabus is None.
DEFAULT_PHASE_RANGES: tuple[tuple[int, int, str], ...] = (
    (1, 12, "Phase 1 · Foundations"),
    (13, 20, "Phase 2 · Go & the Backend Toolkit"),
    (21, 30, "Phase 3 · Distributed Systems & Booking"),
    (31, 39, "Phase 4 · Kubernetes, Observability, Synthesis"),
)
CADENCE_DIRS = ("weekly", "monthly", "quarterly", "annual")


def _phase_boundaries_from_syllabus(syllabus: Syllabus | None) -> tuple[int, ...]:
    """Phase tick positions: each phase's start_month, plus the final end_month."""
    if syllabus is None or not syllabus.phases:
        return DEFAULT_PHASE_BOUNDARIES
    phases = sorted(syllabus.phases, key=lambda p: p.number)
    return tuple([p.months[0] for p in phases] + [phases[-1].months[1]])


def _total_months_from_syllabus(syllabus: Syllabus | None) -> int:
    if syllabus is None or not syllabus.primary_book_by_month:
        return DEFAULT_TOTAL_MONTHS
    return max(syllabus.primary_book_by_month)


def _total_modules_from_syllabus(syllabus: Syllabus | None) -> int:
    if syllabus is None or not syllabus.modules:
        return DEFAULT_TOTAL_MODULES
    return len(syllabus.modules)


def _phase_tick_labels(
    syllabus: Syllabus | None,
    fallback: tuple[tuple[int, int, str], ...] = DEFAULT_PHASE_RANGES,
) -> tuple[tuple[int, int, str], ...]:
    if syllabus is None or not syllabus.phases:
        return fallback
    phases = sorted(syllabus.phases, key=lambda p: p.number)
    return tuple(
        (p.months[0], p.months[1], f"Phase {p.number} · {p.name}")
        for p in phases
    )


def _end_of_journey(start: date, months: int = DEFAULT_TOTAL_MONTHS) -> date:
    """`start` + N calendar months, clamping day-of-month if needed."""
    total = (start.month - 1) + months
    year = start.year + total // 12
    month = total % 12 + 1
    day = min(start.day, monthrange(year, month)[1])
    return date(year, month, day)


def _journey_day(
    today: date, state: State, total_months: int = DEFAULT_TOTAL_MONTHS
) -> tuple[int, int]:
    """Returns (day_n, day_total). Clamped to [0, day_total]."""
    end = _end_of_journey(state.start_date, months=total_months)
    day_total = (end - state.start_date).days + 1
    if today < state.start_date:
        return 0, day_total
    day_n = (today - state.start_date).days + 1
    return min(day_n, day_total), day_total


@dataclass
class ReflectionMeta:
    cadence: str
    file: str          # stem, e.g. "2026-W18"
    status: str        # "stub" | "filled" | other (verbatim)
    word_count: int
    relative_path: str  # "weekly/2026-W18.md"


def _h(s: Any) -> str:
    """Shorthand for html.escape (text contexts only)."""
    return _html.escape(str(s), quote=True)


def _github_blob_url(config: Config, relative_path: str) -> str:
    return (
        f"https://github.com/{config.dashboard.github_username}/"
        f"{config.dashboard.repo_name}/blob/main/reflections/{relative_path}"
    )


def _paused_summary(state: State, today: date) -> str | None:
    if state.paused and state.paused_since is not None:
        days = (today - state.paused_since).days
        return f"Paused since {state.paused_since.isoformat()} ({days} days)"
    if state.paused:
        return "Paused"
    return None


def scan_reflections(reflections_root: Path) -> list[ReflectionMeta]:
    """Walk the four cadence dirs and parse status/word_count from frontmatter."""
    out: list[ReflectionMeta] = []
    for cadence in CADENCE_DIRS:
        dir_path = reflections_root / cadence
        if not dir_path.exists():
            continue
        for path in sorted(dir_path.glob("*.md")):
            try:
                text = path.read_text(encoding="utf-8")
            except OSError:
                continue
            fm, _ = split_frontmatter(text)
            out.append(ReflectionMeta(
                cadence=cadence,
                file=path.stem,
                status=str(fm.get("status", "stub")),
                word_count=int(fm.get("word_count", 0) or 0),
                relative_path=f"{cadence}/{path.name}",
            ))
    return out


# --- per-section renderers ----------------------------------------------------


def _adherence_class(percent: int | None) -> str:
    if percent is None:
        return "adh-empty"
    if percent >= 90:
        return "adh-strong"
    if percent >= 70:
        return "adh-ok"
    if percent >= 50:
        return "adh-warn"
    return "adh-bad"


def _header(
    state: State,
    config: Config,
    today: date,
    adherence: tuple[int, int],
    total_months: int = DEFAULT_TOTAL_MONTHS,
) -> str:
    """Hero: day-of-journey is orientation; adherence is the headline KPI.

    Layout (two-column on wide viewports, stacks on narrow):
        THE LONG WAY · 2026-05-17
        ┌─────────────────────┬──────────────────────┐
        │ Day 013 / 1189      │ Adherence  92%       │
        │                     │ 11/12 expected days  │
        │                     │ since 2026-05-05     │
        └─────────────────────┴──────────────────────┘
        Month 1 of 39 · Phase 1 · Module 1
        Reading: *Computer Systems…*
    """
    day_n, day_total = _journey_day(today, state, total_months=total_months)
    paused = _paused_summary(state, today)
    paused_html = (
        f'<div class="paused-banner">{_h(paused)}</div>' if paused else ""
    )
    day_label = f"{day_n:03d}" if day_n > 0 else "—"

    done, expected = adherence
    if expected == 0:
        adh_value_html = (
            '<span class="big">—</span>'
            '<span class="hero-total">%</span>'
        )
        adh_sub = "no expected days yet"
        adh_class = _adherence_class(None)
    else:
        percent = round(100 * done / expected)
        adh_value_html = (
            f'<span class="big">{percent}</span>'
            f'<span class="hero-total">%</span>'
        )
        adh_sub = (
            f'{done} of {expected} expected days · since {state.start_date.isoformat()}'
        )
        adh_class = _adherence_class(percent)

    return (
        f'<header class="hero">'
        f'<div class="hero-eyebrow">'
        f'The Long Way <span class="dot">&middot;</span> {_h(today.isoformat())}'
        f'</div>'
        f'<div class="hero-stats">'
        f'<div class="hero-stat hero-stat-day">'
        f'<div class="hero-stat-label">Day</div>'
        f'<div class="hero-stat-value">'
        f'<span class="big">{day_label}</span> '
        f'<span class="hero-total">/ {day_total}</span>'
        f'</div>'
        f'</div>'
        f'<div class="hero-stat hero-stat-adherence {adh_class}">'
        f'<div class="hero-stat-label">Adherence</div>'
        f'<div class="hero-stat-value">{adh_value_html}</div>'
        f'<div class="hero-stat-sub">{_h(adh_sub)}</div>'
        f'</div>'
        f'</div>'
        f'<div class="hero-meta">'
        f'Month {state.month} of {total_months} '
        f'<span class="dot">&middot;</span> '
        f'Phase {state.phase} '
        f'<span class="dot">&middot;</span> '
        f'Module {state.current_module}'
        f'</div>'
        f'<div class="hero-book">'
        f'Reading: <em>{_h(state.current_book)}</em>'
        f'</div>'
        f'{paused_html}'
        f'</header>'
    )


def _today_panel(
    state: State,
    config: Config,
    today: date,
    cache: dict[str, Any],
    completion_set: set[str],
) -> str:
    """Single 'what to do now' panel above streaks.

    The dashboard otherwise renders only past + future. Without a Today
    block, an early-morning cron-rendered page leaves the owner guessing
    what's pending.
    """
    weekday_name = today.strftime("%A")
    iso = today.isoformat()
    eyebrow = (
        f'<div class="today-eyebrow">'
        f'Today <span class="dot">&middot;</span> {_h(weekday_name)}, {_h(iso)}'
        f'</div>'
    )

    if today < state.start_date:
        body = (
            f'<div class="today-status today-status-pending">'
            f'Journey starts {state.start_date.isoformat()}'
            f'</div>'
        )
        return f'<section class="today">{eyebrow}{body}</section>'

    if _is_in_pause_window(today, state) or state.paused:
        body = (
            f'<div class="today-status today-status-paused">'
            f'Paused &mdash; no rituals scheduled.'
            f'</div>'
        )
        return f'<section class="today">{eyebrow}{body}</section>'

    if today.weekday() == 6:
        body = (
            f'<div class="today-status today-status-rest">'
            f'Rest day &mdash; Sundays are off.'
            f'</div>'
        )
        return f'<section class="today">{eyebrow}{body}</section>'

    done = 0
    for tpl in DAILY_TEMPLATES_REQUIRED:
        ext = external_id(tpl, today)
        entry = cache.get(ext)
        if entry and str(entry.get("todoist_task_id")) in completion_set:
            done += 1
    total = len(DAILY_TEMPLATES_REQUIRED)

    if done == total:
        body = (
            f'<div class="today-status today-status-done">'
            f'All daily rituals done ({done}/{total}).'
            f'</div>'
        )
    else:
        rt = config.ritual_times or {}
        bits: list[str] = []
        if "morning_reading" in rt:
            bits.append(f"Morning reading {rt['morning_reading']}")
        else:
            bits.append("Morning reading")
        if "anki" in rt:
            bits.append(f"Anki {rt['anki']}")
        else:
            bits.append("Anki")
        ritual_line = (
            f'<div class="today-rituals">{" &middot; ".join(_h(b) for b in bits)}</div>'
        )
        body = (
            f'<div class="today-status today-status-pending">'
            f'{done} of {total} daily rituals done.'
            f'</div>{ritual_line}'
        )
    return f'<section class="today">{eyebrow}{body}</section>'


def _streaks_section(values: dict[str, dict[str, Any]]) -> str:
    """values: {label: {"count": int, "best": int, "hint": str}}"""
    cards: list[str] = []
    for label, v in values.items():
        count = int(v["count"])
        best = int(v["best"])
        hint = str(v["hint"])
        best_line = (
            f'best {best}' if best > 0 else 'no streaks yet'
        )
        cards.append(
            f'<div class="streak-card">'
            f'<div class="streak-value">{count}</div>'
            f'<div class="streak-label">{_h(label)}</div>'
            f'<div class="streak-best">{_h(best_line)}</div>'
            f'<div class="streak-hint">{_h(hint)}</div>'
            f'</div>'
        )
    return f'<section class="streaks"><h2>Streaks</h2>{"".join(cards)}</section>'


def _phase_tree(
    state: State,
    phase_ranges: tuple[tuple[int, int, str], ...] = DEFAULT_PHASE_RANGES,
) -> str:
    """Per-phase segmented progress bar.

    Replaces the previous 1.6rem numbered cells (1..39) — the digits were
    unreadable at that size and the count duplicated the hero. Each phase
    is one row: dot, label, "month X / Y in phase", segmented bar where
    each segment is one month (past / current / future). No numbers
    cluttering the segments themselves.
    """
    rows: list[str] = []
    for i, (start, end, label) in enumerate(phase_ranges):
        phase_complete = state.month > end
        phase_active = start <= state.month <= end
        node_class = (
            "complete" if phase_complete
            else "active" if phase_active
            else "future"
        )
        position_class = (
            "first" if i == 0
            else "last" if i == len(phase_ranges) - 1
            else "middle"
        )

        total = end - start + 1
        if phase_complete:
            done_in_phase = total
        elif phase_active:
            done_in_phase = state.month - start  # current month not yet "done"
        else:
            done_in_phase = 0
        progress_label = (
            f"month {state.month - start + 1} / {total}"
            if phase_active
            else (f"{total} / {total}" if phase_complete else f"0 / {total}")
        )

        segments: list[str] = []
        for m in range(start, end + 1):
            if m < state.month:
                cls = "past"
            elif m == state.month:
                cls = "current"
            else:
                cls = "future"
            segments.append(
                f'<span class="month-seg month-seg-{cls}" title="Month {m}"></span>'
            )

        rows.append(
            f'<div class="phase-row phase-{node_class} phase-{position_class}">'
            f'<div class="phase-node"></div>'
            f'<div class="phase-label">{_h(label)}</div>'
            f'<div class="phase-progress-label">{_h(progress_label)}</div>'
            f'<div class="phase-bar">{"".join(segments)}</div>'
            f'</div>'
        )
    return (
        f'<section class="phase-tree-section">'
        f'<h2>Progress</h2>'
        f'<div class="phase-tree">{"".join(rows)}</div>'
        f'</section>'
    )


def _last_7_color(
    d: date,
    state: State,
    cache: dict[str, Any],
    completion_set: set[str],
) -> str:
    # Days before the journey's start_date aren't 'missed' — they're
    # outside the journey. Treat them as a gray skip-day, the same way
    # Sundays and pause windows are coloured. Without this, a freshly
    # initialised state.yaml shows the prior 6 days as red (= both
    # dailies missed) which reads as failure before day 1.
    if d < state.start_date:
        return "gray"
    if d.weekday() == 6 or _is_in_pause_window(d, state):
        return "gray"
    done = 0
    for tpl in DAILY_TEMPLATES_REQUIRED:
        ext = external_id(tpl, d)
        entry = cache.get(ext)
        if entry and str(entry.get("todoist_task_id")) in completion_set:
            done += 1
    if done == 2:
        return "green"
    if done == 1:
        return "yellow"
    return "red"


_LAST7_LEGEND = (
    ("green", "both dailies done"),
    ("yellow", "one of two"),
    ("red", "missed"),
    ("gray", "rest / paused"),
)


def _last_7_days(
    today: date,
    state: State,
    cache: dict[str, Any],
    completion_set: set[str],
) -> tuple[str, list[dict[str, str]]]:
    cells: list[str] = []
    data: list[dict[str, str]] = []
    counts = {"green": 0, "yellow": 0, "red": 0, "gray": 0}
    for offset in range(7, 0, -1):
        d = today - timedelta(days=offset)
        color = _last_7_color(d, state, cache, completion_set)
        counts[color] += 1
        weekday = d.strftime("%a")
        cells.append(
            f'<div class="day day-{color}" title="{_h(d.isoformat())}">'
            f'<span class="dow">{_h(weekday)}</span>'
            f'<span class="dom">{d.day}</span>'
            f'</div>'
        )
        data.append({"date": d.isoformat(), "state": color})

    tally_parts: list[str] = []
    if counts["green"]:
        tally_parts.append(f"{counts['green']} full")
    if counts["yellow"]:
        tally_parts.append(f"{counts['yellow']} partial")
    if counts["red"]:
        tally_parts.append(f"{counts['red']} missed")
    if counts["gray"]:
        tally_parts.append(f"{counts['gray']} rest")
    tally = " &middot; ".join(tally_parts) if tally_parts else "no days yet"

    legend = " &nbsp; ".join(
        f'<span class="last7-key last7-key-{cls}">'
        f'<span class="last7-swatch last7-swatch-{cls}"></span>{_h(label)}'
        f'</span>'
        for cls, label in _LAST7_LEGEND
    )

    html = (
        f'<section class="last7"><h2>Last 7 days</h2>'
        f'<div class="day-row">{"".join(cells)}</div>'
        f'<div class="last7-tally">{tally}</div>'
        f'<div class="last7-legend">{legend}</div>'
        f'</section>'
    )
    return html, data


def _practice_counts(
    state: State, cache: dict[str, Any], completion_set: set[str]
) -> dict[str, int]:
    code_reading = sum(
        1
        for entry in cache.values()
        if entry.get("template_id") == "weekly-read-real-code"
        and (
            entry.get("status") == "completed"
            or str(entry.get("todoist_task_id")) in completion_set
        )
    )
    mc = state.manual_counters
    return {
        "Code reading sessions": code_reading,
        "Traces completed": int(mc.get("traces_completed", 0) or 0),
        "PRs opened": int(mc.get("prs_opened", 0) or 0),
        "Pair sessions": int(mc.get("pair_sessions", 0) or 0),
    }


def _practice_tracker(values: dict[str, int]) -> str:
    cards = "".join(
        f'<div class="practice-card">'
        f'<div class="practice-value">{v}</div>'
        f'<div class="practice-label">{_h(k)}</div>'
        f'</div>'
        for k, v in values.items()
    )
    return f'<section class="practices"><h2>Active practices</h2>{cards}</section>'


def _books_section(state: State, books: list[Book]) -> str:
    """Per-phase reading list. "not_started" books fade rather than flag.

    A NOT STARTED pill on every future book read as failure, so the
    badge is only rendered for "current" and "done" — not-started books
    visually recede via a CSS class but carry no explicit pill.
    """
    by_phase: dict[int, list[Book]] = {}
    for b in books:
        by_phase.setdefault(b.phase, []).append(b)
    parts: list[str] = []
    for phase in sorted(by_phase.keys()):
        rows: list[str] = []
        for b in by_phase[phase]:
            badge = state.books_state.get(b.title, "not_started")
            timing = (
                f"months {b.start_month}–{b.end_month}"
                if b.start_month and b.end_month and b.start_month != b.end_month
                else f"month {b.start_month}" if b.start_month
                else "reference"
            )
            pill = (
                f'<span class="book-badge">{_h(badge.replace("_", " "))}</span>'
                if badge in ("current", "done") else ""
            )
            rows.append(
                f'<li class="book-row book-{_h(badge)}">'
                f'<span class="book-title">{_h(b.title)}</span>'
                f' &mdash; <span class="book-author">{_h(b.author)}</span> '
                f'<span class="book-timing">({_h(timing)})</span>'
                f'{pill}'
                f'</li>'
            )
        parts.append(
            f'<div class="phase-block"><h3>Phase {phase}</h3>'
            f'<ul class="book-list">{"".join(rows)}</ul></div>'
        )
    return f'<section class="books"><h2>Books</h2>{"".join(parts)}</section>'


def _module_trunk(
    state: State,
    module_titles: dict[int, str],
    total_modules: int = DEFAULT_TOTAL_MODULES,
) -> str:
    """N-module progression spine. Always renders; current_module is required state.

    Header: 'N/total — <current title>'. Cells: 1..total coloured past/current/
    future. n is 'past' if n in completed_modules OR n < current_module
    (the latter handles owners advancing without explicitly backfilling
    completed_modules).
    """
    current = state.current_module
    completed = set(state.completed_modules)
    title = module_titles.get(current, f"Module {current}")
    cells: list[str] = []
    for n in range(1, total_modules + 1):
        if n == current:
            cls = "current"
        elif n in completed or n < current:
            cls = "past"
        else:
            cls = "future"
        cells.append(
            f'<span class="module-cell module-{cls}" title="Module {n}">{n}</span>'
        )
    return (
        f'<section class="module-trunk"><h2>Module trunk</h2>'
        f'<div class="trunk-header">'
        f'<span class="trunk-counter">{current}/{total_modules}</span>'
        f'<span class="trunk-current-title">{_h(title)}</span>'
        f'</div>'
        f'<div class="trunk-cells">{"".join(cells)}</div>'
        f'</section>'
    )


def _learning_tracks(state: State) -> str:
    """Owner-curated multi-track panel. Hides when no non-empty categories.

    Empty inner dicts and the entirely-empty learning_tracks both yield
    the empty string; the body concat in render() treats it as a no-op,
    keeping the empty/partial/paused snapshot fixtures byte-equal.
    """
    blocks: list[str] = []
    for category, items in state.learning_tracks.items():
        if not items:
            continue
        rows = "".join(
            f'<li class="track-row track-{_h(badge)}">'
            f'<span class="track-item">{_h(item)}</span>'
            f'<span class="track-badge">{_h(badge.replace("_", " "))}</span>'
            f'</li>'
            for item, badge in items.items()
        )
        blocks.append(
            f'<div class="track-block"><h3>{_h(category)}</h3>'
            f'<ul class="track-list">{rows}</ul></div>'
        )
    if not blocks:
        return ""
    return f'<section class="tracks"><h2>Tracks</h2>{"".join(blocks)}</section>'


_TYPE_ORDER = {"weekly": 0, "monthly": 1, "quarterly": 2, "annual": 3}


def _reflection_log(
    config: Config, reflections: list[ReflectionMeta]
) -> str:
    if not reflections:
        return (
            '<section class="reflections"><h2>Reflections</h2>'
            '<p class="empty">No reflections yet.</p></section>'
        )
    # Reverse-chrono. Sort by file stem desc; then by cadence order (just to
    # keep deterministic order on cross-cadence collisions).
    sorted_refs = sorted(
        reflections,
        key=lambda r: (r.file, _TYPE_ORDER.get(r.cadence, 99)),
        reverse=True,
    )
    rows = "".join(
        f'<li class="reflection-row reflection-{_h(r.status)}">'
        f'<a href="{_h(_github_blob_url(config, r.relative_path))}">'
        f'<span class="ref-cadence">{_h(r.cadence)}</span> '
        f'<span class="ref-file">{_h(r.file)}</span>'
        f'</a>'
        f' <span class="ref-status">{_h(r.status)}</span>'
        f' <span class="ref-words">{r.word_count} words</span>'
        f'</li>'
        for r in sorted_refs
    )
    return (
        f'<section class="reflections"><h2>Reflections</h2>'
        f'<ul class="reflection-list">{rows}</ul></section>'
    )


def _footer(today: date) -> str:
    return (
        f'<footer><div class="footer-line">'
        f'Generated {_h(today.isoformat())}'
        f'</div></footer>'
    )


# --- top-level render ---------------------------------------------------------


def render(
    state: State,
    config: Config,
    completion_set: set[str],
    cache: dict[str, Any],
    reflections: list[ReflectionMeta],
    books: list[Book],
    today: date,
    clock: Clock,
    reflections_root: Path,
    module_titles: dict[int, str] | None = None,
    syllabus: Syllabus | None = None,
) -> tuple[str, dict[str, Any]]:
    """Render dashboard. Returns (html_string, data_json_dict)."""
    if module_titles is None:
        module_titles = {}

    total_months = _total_months_from_syllabus(syllabus)
    total_modules = _total_modules_from_syllabus(syllabus)
    phase_tick_labels = _phase_tick_labels(syllabus)

    daily_count = daily_streak(today, state, cache, completion_set)
    weekly_count = weekly_review_streak(
        today, state, cache, completion_set, reflections_root
    )
    monthly_count = monthly_post_streak(today, state, cache, completion_set)
    streaks_view: dict[str, dict[str, Any]] = {
        "Daily": {
            "count": daily_count,
            "best": best_daily_streak(today, state, cache, completion_set),
            "hint": daily_hint(today, state, daily_count),
        },
        "Weekly review": {
            "count": weekly_count,
            "best": best_weekly_review_streak(
                today, state, cache, completion_set, reflections_root
            ),
            "hint": weekly_hint(today, state, weekly_count),
        },
        "Monthly post": {
            "count": monthly_count,
            "best": best_monthly_post_streak(
                today, state, cache, completion_set
            ),
            "hint": monthly_hint(today, state, monthly_count),
        },
    }

    last7_html, last7_data = _last_7_days(today, state, cache, completion_set)
    practices = _practice_counts(state, cache, completion_set)
    day_n, day_total = _journey_day(today, state, total_months=total_months)
    adherence = adherence_since_start(today, state, cache, completion_set)

    body = "".join(
        (
            _header(state, config, today, adherence, total_months=total_months),
            _today_panel(state, config, today, cache, completion_set),
            _streaks_section(streaks_view),
            _phase_tree(state, phase_ranges=phase_tick_labels),
            _module_trunk(state, module_titles, total_modules=total_modules),
            last7_html,
            _practice_tracker(practices),
            _learning_tracks(state),
            _books_section(state, books),
            _reflection_log(config, reflections),
            _footer(today),
        )
    )
    html_doc = (
        '<!doctype html>\n'
        '<html lang="en"><head>'
        '<meta charset="utf-8">'
        f'<title>The Long Way &mdash; {_h(today.isoformat())}</title>'
        '<meta name="viewport" content="width=device-width,initial-scale=1">'
        '<link rel="stylesheet" href="assets/style.css">'
        f'</head><body><main class="dashboard">{body}</main></body></html>\n'
    )

    adh_done, adh_expected = adherence
    adh_pct = round(100 * adh_done / adh_expected) if adh_expected > 0 else None

    data: dict[str, Any] = {
        "today": today.isoformat(),
        "day_of_journey": day_n,
        "day_total": day_total,
        "adherence": {
            "done": adh_done,
            "expected": adh_expected,
            "percent": adh_pct,
            "since": state.start_date.isoformat(),
        },
        "phase": state.phase,
        "month": state.month,
        "current_module": state.current_module,
        "current_book": state.current_book,
        "paused": _paused_summary(state, today),
        "streaks": {k: v["count"] for k, v in streaks_view.items()},
        "streaks_view": streaks_view,
        "last_7_days": last7_data,
        "practices": practices,
        "books": [asdict(b) for b in books],
        "books_state": state.books_state,
        "reflections": [asdict(r) for r in reflections],
    }
    return html_doc, data


# --- CSS lifecycle ------------------------------------------------------------

CSS = """\
:root {
  --bg: #fafafa;
  --fg: #1a1a1a;
  --muted: #666;
  --faint: #999;
  --accent: #0a5;
  --warn: #d94;
  --bad: #c33;
  --line: #ddd;
  --skip: #cfcfcf;
  --mono: ui-monospace, SFMono-Regular, "SF Mono", Menlo, Consolas, monospace;
}
* { box-sizing: border-box; }
body {
  font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto,
               "Helvetica Neue", Arial, sans-serif;
  background: var(--bg); color: var(--fg);
  margin: 0; padding: 1.5rem;
  line-height: 1.5;
}
.dashboard { max-width: 920px; margin: 0 auto; }
header.hero {
  border-bottom: 1px solid var(--line);
  padding-bottom: 1.25rem; margin-bottom: 1.25rem;
}
.hero-eyebrow {
  font-size: .75rem; color: var(--muted);
  text-transform: uppercase; letter-spacing: .12em;
  margin-bottom: .35rem;
  font-family: var(--mono);
}
.hero-eyebrow .dot { margin: 0 .35rem; opacity: .5; }
.hero-stats {
  display: flex; gap: 2rem; flex-wrap: wrap;
  margin: .35rem 0 .5rem;
}
.hero-stat {
  flex: 1 1 14rem; min-width: 12rem;
}
.hero-stat-label {
  font-size: .7rem; color: var(--muted);
  text-transform: uppercase; letter-spacing: .12em;
  font-family: var(--mono);
  margin-bottom: .1rem;
}
.hero-stat-value {
  font-size: 1.05rem; color: var(--muted);
  font-weight: 500; line-height: 1;
}
.hero-stat-value .big {
  font-size: 3.4rem; font-weight: 800; color: var(--fg);
  display: inline-block; line-height: 1;
  letter-spacing: -.04em;
  vertical-align: -.35rem;
  margin-right: .15rem;
  font-family: var(--mono);
  font-variant-numeric: tabular-nums;
}
.hero-stat-value .hero-total {
  font-family: var(--mono); color: var(--muted);
  font-variant-numeric: tabular-nums;
}
.hero-stat-sub {
  font-size: .75rem; color: var(--muted);
  margin-top: .5rem;
  font-family: var(--mono);
}
.hero-stat-adherence.adh-strong .big { color: var(--accent); }
.hero-stat-adherence.adh-ok     .big { color: var(--fg); }
.hero-stat-adherence.adh-warn   .big { color: var(--warn); }
.hero-stat-adherence.adh-bad    .big { color: var(--bad); }
.hero-stat-adherence.adh-empty  .big { color: var(--muted); }
.hero-meta {
  font-size: .95rem; color: var(--fg);
  margin-top: .35rem;
}
.hero-meta .dot { margin: 0 .35rem; color: var(--muted); }
.hero-book {
  font-size: .95rem; color: var(--muted);
  margin-top: .25rem;
}
.hero-book em {
  color: var(--accent); font-style: italic; font-weight: 600;
}
.paused-banner {
  margin-top: .75rem; padding: .5rem .75rem;
  background: #fff4d6; border: 1px solid #e0c060; border-radius: 4px;
}

section { margin: 1.25rem 0; }
section h2 { font-size: 1.05rem; margin: 0 0 .5rem; }
section h3 { font-size: .95rem; margin: .75rem 0 .25rem; }

/* TODAY panel */
.today {
  border: 1px solid var(--line); border-radius: 6px;
  padding: .75rem 1rem; background: white;
}
.today-eyebrow {
  font-size: .7rem; color: var(--muted);
  text-transform: uppercase; letter-spacing: .12em;
  margin-bottom: .35rem;
  font-family: var(--mono);
}
.today-eyebrow .dot { margin: 0 .35rem; opacity: .5; }
.today-status {
  font-size: 1rem; font-weight: 600;
}
.today-status-done    { color: var(--accent); }
.today-status-pending { color: var(--fg); }
.today-status-rest    { color: var(--muted); }
.today-status-paused  { color: var(--warn); }
.today-rituals {
  font-size: .85rem; color: var(--muted);
  margin-top: .2rem;
  font-family: var(--mono);
}

/* Streaks */
.streaks, .practices { display: flex; gap: .75rem; flex-wrap: wrap; }
.streaks h2, .practices h2 { width: 100%; }
.streak-card, .practice-card {
  flex: 1 1 10rem; min-width: 10rem;
  border: 1px solid var(--line); border-radius: 6px;
  padding: .75rem; background: white; text-align: center;
}
.streak-value, .practice-value {
  font-size: 1.6rem; font-weight: 700;
  font-family: var(--mono);
  font-variant-numeric: tabular-nums;
  line-height: 1.1;
}
.streak-label, .practice-label {
  color: var(--muted); font-size: .85rem;
}
.streak-best {
  font-size: .7rem; color: var(--faint);
  font-family: var(--mono);
  text-transform: uppercase; letter-spacing: .08em;
  margin-top: .2rem;
}
.streak-hint {
  font-size: .8rem; color: var(--muted);
  margin-top: .35rem; line-height: 1.3;
}

/* Phase tree: segmented bar instead of numbered cells */
.phase-tree { display: flex; flex-direction: column; gap: 0; }
.phase-row {
  display: flex; align-items: center; gap: .75rem;
  position: relative; padding: .5rem 0;
}
.phase-row::before {
  content: ""; position: absolute;
  left: .55rem; top: 0; bottom: 0;
  width: 2px; background: var(--line);
}
.phase-row.phase-first::before { top: 50%; }
.phase-row.phase-last::before { bottom: 50%; }
.phase-node {
  width: 1.2rem; height: 1.2rem; border-radius: 50%;
  background: white; border: 2px solid var(--line);
  position: relative; z-index: 1; flex-shrink: 0;
}
.phase-row.phase-complete .phase-node { background: var(--accent); border-color: var(--accent); }
.phase-row.phase-active .phase-node {
  background: var(--accent); border-color: var(--accent);
  box-shadow: 0 0 0 4px rgba(0,170,85,.18);
}
.phase-label {
  font-weight: 600; font-size: .9rem;
  min-width: 11rem; flex-shrink: 0;
}
.phase-row.phase-future .phase-label { color: var(--muted); }
.phase-progress-label {
  font-size: .75rem; color: var(--muted);
  min-width: 6rem;
  font-family: var(--mono);
  font-variant-numeric: tabular-nums;
  text-align: right;
}
.phase-row.phase-future .phase-progress-label { color: var(--faint); }
.phase-bar {
  display: flex; gap: 2px; flex: 1;
  height: .65rem;
  border-radius: 3px;
  overflow: hidden;
}
.month-seg {
  flex: 1 1 0;
  height: 100%;
  background: var(--line);
  border-radius: 1px;
}
.month-seg-past    { background: var(--accent); }
.month-seg-current {
  background: var(--accent);
  box-shadow: inset 0 0 0 2px white;
}
.month-seg-future  { background: #e8e8e8; }

/* Last 7 days */
.day-row { display: flex; gap: .25rem; }
.day {
  flex: 1; min-width: 2rem; padding: .5rem .25rem;
  border-radius: 4px; text-align: center;
  display: flex; flex-direction: column; gap: .15rem;
}
.day .dow { font-size: .7rem; opacity: .8; font-family: var(--mono); }
.day .dom { font-size: 1rem; font-weight: 600; font-family: var(--mono); }
.day-green  { background: #c6efc6; color: #084; }
.day-yellow { background: #fce39e; color: #864; }
.day-red    { background: #f3c4c4; color: #944; }
.day-gray   { background: var(--skip); color: var(--muted); }
.last7-tally {
  font-size: .85rem; color: var(--muted);
  margin-top: .5rem;
  font-family: var(--mono);
}
.last7-legend {
  font-size: .7rem; color: var(--faint);
  margin-top: .35rem;
  display: flex; gap: 1rem; flex-wrap: wrap;
  font-family: var(--mono);
  text-transform: uppercase; letter-spacing: .06em;
}
.last7-key { display: inline-flex; align-items: center; gap: .35rem; }
.last7-swatch {
  display: inline-block;
  width: .7rem; height: .7rem; border-radius: 2px;
}
.last7-swatch-green  { background: #c6efc6; }
.last7-swatch-yellow { background: #fce39e; }
.last7-swatch-red    { background: #f3c4c4; }
.last7-swatch-gray   { background: var(--skip); }

/* Module trunk (unchanged from prior iteration) */
.module-trunk h2 { margin-bottom: .5rem; }
.trunk-header {
  display: flex; align-items: baseline; gap: .75rem;
  margin: .25rem 0 .5rem;
}
.trunk-counter {
  font-size: 1.5rem; font-weight: 800; color: var(--accent);
  font-family: var(--mono);
  font-variant-numeric: tabular-nums; letter-spacing: -.02em;
}
.trunk-current-title { color: var(--fg); font-size: 1rem; }
.trunk-cells { display: flex; gap: .25rem; flex-wrap: wrap; }
.module-cell {
  width: 1.6rem; height: 1.6rem; border-radius: 4px;
  display: inline-flex; align-items: center; justify-content: center;
  font-size: .7rem; font-variant-numeric: tabular-nums;
  font-family: var(--mono);
  border: 1px solid var(--line); background: white; color: var(--muted);
}
.module-cell.module-past {
  background: var(--accent); border-color: var(--accent); color: white;
}
.module-cell.module-current {
  background: white; border: 2px solid var(--accent); color: var(--accent);
  font-weight: 800; box-shadow: 0 0 0 3px rgba(0,170,85,.2);
}

/* Tracks (unchanged) */
.tracks .track-block { margin-top: .75rem; }
.track-list { list-style: none; padding: 0; margin: 0; }
.track-row {
  border-bottom: 1px solid var(--line); padding: .25rem 0;
  display: flex; align-items: baseline; gap: .25rem; flex-wrap: wrap;
}
.track-item { font-weight: 500; flex: 1; }
.track-badge {
  font-size: .7rem; padding: 1px 6px; border-radius: 3px;
  background: var(--line); text-transform: uppercase;
}
.track-row.track-current .track-badge { background: var(--accent); color: white; }
.track-row.track-done .track-badge { background: var(--muted); color: white; }

/* Books — not_started fades, no pill */
.book-list { list-style: none; padding: 0; margin: 0; }
.book-row {
  border-bottom: 1px solid var(--line); padding: .35rem 0;
  display: flex; align-items: baseline; gap: .25rem; flex-wrap: wrap;
}
.book-title { font-weight: 600; }
.book-author { color: var(--muted); }
.book-timing { color: var(--muted); font-size: .85rem; }
.book-badge {
  margin-left: auto; font-size: .7rem;
  padding: 1px 6px; border-radius: 3px;
  background: var(--line); text-transform: uppercase;
  font-family: var(--mono);
}
.book-current .book-badge { background: var(--accent); color: white; }
.book-done .book-badge    { background: var(--muted); color: white; }
.book-not_started .book-title  { color: var(--faint); font-weight: 500; }
.book-not_started .book-author { color: var(--faint); }
.book-not_started .book-timing { color: var(--faint); }
.book-done .book-title  { color: var(--muted); }
.book-done .book-author { color: var(--faint); }

/* Reflections (unchanged) */
.reflection-list { list-style: none; padding: 0; margin: 0; }
.reflection-row {
  border-bottom: 1px solid var(--line); padding: .25rem 0;
  display: flex; align-items: baseline; gap: .5rem; flex-wrap: wrap;
}
.reflection-row a { color: var(--fg); text-decoration: none; flex: 1; }
.reflection-row a:hover { text-decoration: underline; }
.ref-cadence {
  font-size: .7rem; padding: 1px 6px; border-radius: 3px;
  background: var(--line); text-transform: uppercase;
}
.ref-status {
  font-size: .75rem; color: var(--muted);
  padding: 1px 6px; border-radius: 3px; background: white;
  border: 1px solid var(--line);
}
.reflection-filled .ref-status { background: var(--accent); color: white; border-color: var(--accent); }
.ref-words { color: var(--muted); font-size: .85rem; font-family: var(--mono); }

footer { margin-top: 2rem; padding-top: 1rem; border-top: 1px solid var(--line);
         color: var(--muted); font-size: .8rem; text-align: center;
         font-family: var(--mono); }

@media print {
  body { background: white; padding: 0; }
  .dashboard { max-width: none; }
  a { text-decoration: none; color: var(--fg); }
  .paused-banner { background: white; }
  .today { border: 1px solid #aaa; }
}
"""


def write_css_if_absent(css_path: Path) -> bool:
    """Write the bundled CSS exactly once. Returns True iff it wrote."""
    if css_path.exists():
        return False
    css_path.parent.mkdir(parents=True, exist_ok=True)
    css_path.write_text(CSS, encoding="utf-8")
    return True
