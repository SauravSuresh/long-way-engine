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
    daily_streak,
    monthly_post_streak,
    weekly_review_streak,
)
from src.syllabus import Book

# Phase 1 = months 1–12, Phase 2 = 13–20, Phase 3 = 21–30, Phase 4 = 31–39.
TOTAL_MONTHS = 39
PHASE_BOUNDARIES = (1, 13, 21, 31, 39)
PHASE_LABELS = ("Phase 1", "Phase 2", "Phase 3", "Phase 4", "End")
CADENCE_DIRS = ("weekly", "monthly", "quarterly", "annual")


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


def _header(state: State, config: Config, today: date) -> str:
    paused = _paused_summary(state, today)
    paused_html = (
        f'<div class="paused-banner">{_h(paused)}</div>' if paused else ""
    )
    return (
        f'<header>'
        f'<h1>The Long Way</h1>'
        f'<div class="meta">'
        f'<span class="today">{_h(today.isoformat())}</span> &middot; '
        f'<span>Month {state.month}/{TOTAL_MONTHS}</span> &middot; '
        f'<span>Phase {state.phase}</span> &middot; '
        f'<span>Module {state.current_module}</span>'
        f'</div>'
        f'<div class="book">{_h(state.current_book)}</div>'
        f'{paused_html}'
        f'</header>'
    )


def _streaks_section(values: dict[str, int]) -> str:
    cards = "".join(
        f'<div class="streak-card">'
        f'<div class="streak-value">{v}</div>'
        f'<div class="streak-label">{_h(k)}</div>'
        f'</div>'
        for k, v in values.items()
    )
    return f'<section class="streaks"><h2>Streaks</h2>{cards}</section>'


def _progress_bar(state: State) -> str:
    pct = max(1, min(100, int(round(state.month / TOTAL_MONTHS * 100))))
    ticks = "".join(
        f'<div class="phase-tick" style="left:{int(round(b / TOTAL_MONTHS * 100))}%">'
        f'<span class="tick-label">{_h(label)}</span>'
        f'</div>'
        for b, label in zip(PHASE_BOUNDARIES, PHASE_LABELS)
    )
    return (
        f'<section class="progress"><h2>Progress</h2>'
        f'<div class="bar-track">'
        f'<div class="bar-fill" style="width:{pct}%"></div>'
        f'{ticks}'
        f'<div class="month-marker" style="left:{pct}%">M{state.month}</div>'
        f'</div></section>'
    )


def _last_7_color(
    d: date,
    state: State,
    cache: dict[str, Any],
    completion_set: set[str],
) -> str:
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


def _last_7_days(
    today: date,
    state: State,
    cache: dict[str, Any],
    completion_set: set[str],
) -> tuple[str, list[dict[str, str]]]:
    cells: list[str] = []
    data: list[dict[str, str]] = []
    for offset in range(7, 0, -1):
        d = today - timedelta(days=offset)
        color = _last_7_color(d, state, cache, completion_set)
        weekday = d.strftime("%a")
        cells.append(
            f'<div class="day day-{color}" title="{_h(d.isoformat())}">'
            f'<span class="dow">{_h(weekday)}</span>'
            f'<span class="dom">{d.day}</span>'
            f'</div>'
        )
        data.append({"date": d.isoformat(), "state": color})
    html = (
        f'<section class="last7"><h2>Last 7 days</h2>'
        f'<div class="day-row">{"".join(cells)}</div>'
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
        and str(entry.get("todoist_task_id")) in completion_set
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
            rows.append(
                f'<li class="book-row book-{_h(badge)}">'
                f'<span class="book-title">{_h(b.title)}</span>'
                f' &mdash; <span class="book-author">{_h(b.author)}</span> '
                f'<span class="book-timing">({_h(timing)})</span>'
                f'<span class="book-badge">{_h(badge.replace("_", " "))}</span>'
                f'</li>'
            )
        parts.append(
            f'<div class="phase-block"><h3>Phase {phase}</h3>'
            f'<ul class="book-list">{"".join(rows)}</ul></div>'
        )
    return f'<section class="books"><h2>Books</h2>{"".join(parts)}</section>'


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
) -> tuple[str, dict[str, Any]]:
    """Render dashboard. Returns (html_string, data_json_dict)."""
    streaks = {
        "Daily": daily_streak(today, state, cache, completion_set),
        "Weekly review": weekly_review_streak(
            today, state, cache, completion_set, reflections_root
        ),
        "Monthly post": monthly_post_streak(today, state, cache, completion_set),
    }
    last7_html, last7_data = _last_7_days(today, state, cache, completion_set)
    practices = _practice_counts(state, cache, completion_set)

    body = "".join(
        (
            _header(state, config, today),
            _streaks_section(streaks),
            _progress_bar(state),
            last7_html,
            _practice_tracker(practices),
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

    data: dict[str, Any] = {
        "today": today.isoformat(),
        "phase": state.phase,
        "month": state.month,
        "current_module": state.current_module,
        "current_book": state.current_book,
        "paused": _paused_summary(state, today),
        "streaks": streaks,
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
  --accent: #0a5;
  --warn: #d94;
  --bad: #c33;
  --line: #ddd;
  --skip: #cfcfcf;
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
header { border-bottom: 1px solid var(--line); padding-bottom: 1rem; margin-bottom: 1rem; }
header h1 { margin: 0 0 .25rem; font-size: 1.5rem; }
header .meta { color: var(--muted); font-size: .9rem; }
header .book { margin-top: .25rem; font-style: italic; }
.paused-banner {
  margin-top: .5rem; padding: .5rem .75rem;
  background: #fff4d6; border: 1px solid #e0c060; border-radius: 4px;
}
section { margin: 1.5rem 0; }
section h2 { font-size: 1.1rem; margin: 0 0 .5rem; }
section h3 { font-size: 1rem; margin: .75rem 0 .25rem; }
.streaks, .practices { display: flex; gap: .75rem; flex-wrap: wrap; }
.streaks h2, .practices h2 { width: 100%; }
.streak-card, .practice-card {
  flex: 1 1 8rem; min-width: 8rem;
  border: 1px solid var(--line); border-radius: 6px;
  padding: .75rem; background: white; text-align: center;
}
.streak-value, .practice-value { font-size: 1.5rem; font-weight: 600; }
.streak-label, .practice-label { color: var(--muted); font-size: .85rem; }
.bar-track {
  position: relative; height: 1.5rem; background: white;
  border: 1px solid var(--line); border-radius: 999px;
  margin: 2rem 0 1.5rem;
}
.bar-fill {
  height: 100%; background: var(--accent);
  border-radius: 999px; transition: width .3s;
}
.phase-tick {
  position: absolute; top: -1.25rem; width: 1px; height: 2.75rem;
  background: var(--muted);
}
.phase-tick .tick-label {
  position: absolute; top: -1rem; left: 0;
  font-size: .7rem; color: var(--muted);
  transform: translateX(-50%); white-space: nowrap;
}
.month-marker {
  position: absolute; top: -1.5rem;
  font-size: .7rem; font-weight: 600;
  background: var(--fg); color: white;
  padding: 1px 4px; border-radius: 3px;
  transform: translateX(-50%);
}
.day-row { display: flex; gap: .25rem; }
.day {
  flex: 1; min-width: 2rem; padding: .5rem .25rem;
  border-radius: 4px; text-align: center;
  display: flex; flex-direction: column; gap: .15rem;
}
.day .dow { font-size: .7rem; opacity: .8; }
.day .dom { font-size: 1rem; font-weight: 600; }
.day-green  { background: #c6efc6; color: #084; }
.day-yellow { background: #fce39e; color: #864; }
.day-red    { background: #f3c4c4; color: #944; }
.day-gray   { background: var(--skip); color: var(--muted); }
.book-list { list-style: none; padding: 0; margin: 0; }
.book-row {
  border-bottom: 1px solid var(--line); padding: .25rem 0;
  display: flex; align-items: baseline; gap: .25rem; flex-wrap: wrap;
}
.book-title { font-weight: 600; }
.book-author { color: var(--muted); }
.book-timing { color: var(--muted); font-size: .85rem; }
.book-badge {
  margin-left: auto; font-size: .7rem;
  padding: 1px 6px; border-radius: 3px;
  background: var(--line); text-transform: uppercase;
}
.book-current .book-badge { background: var(--accent); color: white; }
.book-done .book-badge    { background: var(--muted); color: white; }
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
.ref-words { color: var(--muted); font-size: .85rem; }
footer { margin-top: 2rem; padding-top: 1rem; border-top: 1px solid var(--line);
         color: var(--muted); font-size: .8rem; text-align: center; }
@media print {
  body { background: white; padding: 0; }
  .dashboard { max-width: none; }
  a { text-decoration: none; color: var(--fg); }
  .paused-banner { background: white; }
}
"""


def write_css_if_absent(css_path: Path) -> bool:
    """Write the bundled CSS exactly once. Returns True iff it wrote."""
    if css_path.exists():
        return False
    css_path.parent.mkdir(parents=True, exist_ok=True)
    css_path.write_text(CSS, encoding="utf-8")
    return True
