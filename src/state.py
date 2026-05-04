"""Load and validate state.yaml.

The owner edits state.yaml; the engine never writes to it. Phase A reads
start_date, timezone, and current_book. Other fields are scaffolded for
later phases (paused, current_module, completed_modules, etc.) so the
schema is stable.
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


def _fail(message: str) -> None:
    print(f"state.yaml: {message}", file=sys.stderr)
    raise SystemExit(2)


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
        manual_counters=dict(raw.get("manual_counters", {}) or {}),
        notes=str(raw.get("notes", "") or ""),
    )
