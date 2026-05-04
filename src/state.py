"""Load and validate state.yaml.

The owner edits state.yaml; the engine never writes to it. Phase A reads
start_date, timezone, and current_book. Other fields are scaffolded for
later phases (paused, current_module, completed_modules, etc.) so the
schema is stable.

Phase E adds three optional fields with default-if-absent loading so
Phase A–D state files keep loading unchanged:

  - paused_since: date | None — set on the day the owner pauses; cleared
    on unpause. Indefinite-pause window has no closed interval yet, so
    streak walks consult paused_since for the open period.
  - pause_history: list[PauseInterval] — closed pause windows. Each
    {start, end, reason}. Streak walks treat dates inside any interval
    as "not counted as a break" (same as Sunday).
  - books_state: dict[title -> "not_started"|"current"|"done"] — owner
    maintained, dashboard reads.
"""

from __future__ import annotations

import sys
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

import yaml


@dataclass
class PauseInterval:
    start: date
    end: date
    reason: str = ""


@dataclass
class State:
    start_date: date
    timezone: ZoneInfo
    phase: int
    month: int
    current_module: int
    current_book: str
    completed_modules: list[int] = field(default_factory=list)
    active_branches: list[str] = field(default_factory=list)
    paused: bool = False
    paused_since: date | None = None
    pause_history: list[PauseInterval] = field(default_factory=list)
    books_state: dict[str, str] = field(default_factory=dict)
    learning_tracks: dict[str, dict[str, str]] = field(default_factory=dict)
    manual_counters: dict[str, Any] = field(default_factory=dict)
    notes: str = ""


REQUIRED_KEYS = (
    "start_date",
    "timezone",
    "phase",
    "month",
    "current_module",
    "current_book",
)

_VALID_BOOK_STATES = {"not_started", "current", "done"}


def _fail(message: str) -> None:
    print(f"state.yaml: {message}", file=sys.stderr)
    raise SystemExit(2)


def _parse_pause_history(raw: Any) -> list[PauseInterval]:
    if raw is None:
        return []
    if not isinstance(raw, list):
        _fail("pause_history must be a list")
    intervals: list[PauseInterval] = []
    for i, entry in enumerate(raw):
        if not isinstance(entry, dict):
            _fail(f"pause_history[{i}] must be a mapping")
        start = entry.get("start")
        end = entry.get("end")
        reason = entry.get("reason", "") or ""
        if not isinstance(start, date):
            _fail(f"pause_history[{i}].start must be a YAML date")
        if not isinstance(end, date):
            _fail(f"pause_history[{i}].end must be a YAML date")
        if start > end:
            _fail(f"pause_history[{i}] start ({start}) > end ({end})")
        intervals.append(PauseInterval(start=start, end=end, reason=str(reason)))
    return intervals


def _parse_paused_since(raw: Any) -> date | None:
    if raw is None:
        return None
    if not isinstance(raw, date):
        _fail(f"paused_since must be a YAML date or absent (got {type(raw).__name__})")
    return raw


def _parse_learning_tracks(raw: Any) -> dict[str, dict[str, str]]:
    """Owner-curated parallel learning surfaces (courses, branches, certs, ...).

    Strict on shape (top-level dict, each category is a dict, each leaf
    state is in the locked vocabulary), but permissive on content —
    category and item names are arbitrary strings the engine never
    inspects. Per the Phase G design constraint: a typo in 'Lineage
    detours' produces a silent extra category at first render rather
    than an error, keeping the field uniformly owner-agency.
    """
    if raw is None:
        return {}
    if not isinstance(raw, dict):
        _fail("learning_tracks must be a mapping of category -> {item: state}")
    out: dict[str, dict[str, str]] = {}
    for category, items in raw.items():
        if not isinstance(items, dict):
            _fail(
                f"learning_tracks[{category!r}] must be a mapping of "
                f"item -> state (got {type(items).__name__})"
            )
        cat_items: dict[str, str] = {}
        for item, state_val in items.items():
            s = str(state_val)
            if s not in _VALID_BOOK_STATES:
                _fail(
                    f"learning_tracks[{category!r}][{item!r}] = {s!r}; "
                    f"must be one of {sorted(_VALID_BOOK_STATES)}"
                )
            cat_items[str(item)] = s
        out[str(category)] = cat_items
    return out


def _parse_books_state(raw: Any) -> dict[str, str]:
    if raw is None:
        return {}
    if not isinstance(raw, dict):
        _fail("books_state must be a mapping of title -> state")
    out: dict[str, str] = {}
    for title, state_val in raw.items():
        s = str(state_val)
        if s not in _VALID_BOOK_STATES:
            _fail(
                f"books_state[{title!r}] = {s!r}; must be one of "
                f"{sorted(_VALID_BOOK_STATES)}"
            )
        out[str(title)] = s
    return out


def load_state(path: Path) -> State:
    with path.open("r", encoding="utf-8") as f:
        raw: dict[str, Any] = yaml.safe_load(f) or {}

    for key in REQUIRED_KEYS:
        if key not in raw:
            _fail(f"missing required key '{key}'")

    start = raw["start_date"]
    if not isinstance(start, date):
        _fail(f"start_date must be a YAML date (got {type(start).__name__})")

    tz_name = raw["timezone"]
    try:
        tz = ZoneInfo(str(tz_name))
    except Exception as e:
        _fail(f"invalid timezone {tz_name!r}: {e}")
        raise  # unreachable, satisfies type-checkers

    return State(
        start_date=start,
        timezone=tz,
        phase=int(raw["phase"]),
        month=int(raw["month"]),
        current_module=int(raw["current_module"]),
        current_book=str(raw["current_book"]),
        completed_modules=list(raw.get("completed_modules", []) or []),
        active_branches=list(raw.get("active_branches", []) or []),
        paused=bool(raw.get("paused", False)),
        paused_since=_parse_paused_since(raw.get("paused_since")),
        pause_history=_parse_pause_history(raw.get("pause_history")),
        books_state=_parse_books_state(raw.get("books_state")),
        learning_tracks=_parse_learning_tracks(raw.get("learning_tracks")),
        manual_counters=dict(raw.get("manual_counters", {}) or {}),
        notes=str(raw.get("notes", "") or ""),
    )
