"""Seasons layer: owner file (`seasons.yaml`) and engine state (`state/seasons.yaml`).

Schema decided in wayfinder ticket #9 (see CONTEXT.md for the vocabulary).
Pure load / validate / save. No clock, no Todoist, no forecast here.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path
from typing import Any

import yaml

WEEKDAYS = ("monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday")
LANES = ("main", "side")
_SLUG = re.compile(r"^[a-z0-9]+(-[a-z0-9]+)*$")
_HHMM = re.compile(r"^([01]\d|2[0-3]):[0-5]\d$")


@dataclass(frozen=True)
class DeepBlock:
    start: str
    minutes: int
    lane: str = "main"


@dataclass(frozen=True)
class Rhythm:
    sleep_from: str
    sleep_to: str
    fixed_from: str
    fixed_to: str
    fixed_days: tuple[str, ...]
    shutdown: str
    rest_week: bool
    deep_blocks: dict[str, DeepBlock]  # weekday -> block; absent = no block


@dataclass(frozen=True)
class Milestone:
    id: str
    name: str
    area: str
    hours: float
    lane: str = "main"
    syllabus: str | None = None
    track: tuple[str, str] | None = None  # (category, item)
    modules: tuple[int, int] | None = None
    pin_start: date | None = None

    @property
    def bare(self) -> bool:
        return self.syllabus is None


@dataclass(frozen=True)
class Discipline:
    id: str
    name: str
    minutes: int
    start: str
    days: tuple[str, ...] = WEEKDAYS


@dataclass(frozen=True)
class Seasons:
    todoist_project_id: str
    rhythm: Rhythm
    bucket: tuple[Milestone, ...]
    disciplines: tuple[Discipline, ...]

    @property
    def two_lanes(self) -> bool:
        return any(b.lane == "side" for b in self.rhythm.deep_blocks.values())


@dataclass
class MilestoneProgress:
    logged: dict[date, int] = field(default_factory=dict)
    done: date | None = None

    @property
    def logged_minutes(self) -> int:
        return sum(self.logged.values())


@dataclass
class SeasonsState:
    milestones: dict[str, MilestoneProgress] = field(default_factory=dict)
    rest_until: date | None = None
    last_run: dict[str, Any] = field(default_factory=lambda: {"main": None, "side": None, "resting": False})


# --- loading ----------------------------------------------------------------


def _days(raw: Any, default: tuple[str, ...]) -> tuple[str, ...]:
    if raw is None:
        return default
    return tuple(str(d).lower() for d in raw)


def _date(raw: Any) -> date | None:
    if raw is None:
        return None
    return raw if isinstance(raw, date) else date.fromisoformat(str(raw))


def _milestone(raw: dict[str, Any]) -> Milestone:
    track = raw.get("track")
    modules = raw.get("modules")
    return Milestone(
        id=str(raw.get("id", "")),
        name=str(raw.get("name", "")),
        area=str(raw.get("area", "")),
        hours=float(raw.get("hours", 0)),
        lane=str(raw.get("lane", "main")),
        syllabus=raw.get("syllabus"),
        track=(str(track["category"]), str(track["item"])) if isinstance(track, dict) else None,
        modules=(int(modules[0]), int(modules[1])) if modules else None,
        pin_start=_date(raw.get("pin_start")),
    )


def load_seasons(path: Path) -> Seasons:
    raw = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    r = raw.get("rhythm") or {}
    sleep, fixed = r.get("sleep") or {}, r.get("fixed_hours") or {}
    blocks = {
        str(day).lower(): DeepBlock(str(b["start"]), int(b["minutes"]), str(b.get("lane", "main")))
        for day, b in (r.get("deep_blocks") or {}).items()
        if b
    }
    rhythm = Rhythm(
        sleep_from=str(sleep.get("from", "22:30")),
        sleep_to=str(sleep.get("to", "06:00")),
        fixed_from=str(fixed.get("from", "09:30")),
        fixed_to=str(fixed.get("to", "18:30")),
        fixed_days=_days(fixed.get("days"), WEEKDAYS[:5]),
        shutdown=str(r.get("shutdown", "21:00")),
        rest_week=bool(r.get("rest_week", True)),
        deep_blocks=blocks,
    )
    bucket = tuple(_milestone(m) for m in raw.get("bucket") or [])
    disciplines = tuple(
        Discipline(
            id=str(d.get("id", "")),
            name=str(d.get("name", "")),
            minutes=int(d.get("minutes", 0)),
            start=str(d.get("start", "")),
            days=_days(d.get("days"), WEEKDAYS),
        )
        for d in raw.get("disciplines") or []
    )
    return Seasons(str(raw.get("todoist_project_id", "")), rhythm, bucket, disciplines)


def load_seasons_state(path: Path) -> SeasonsState:
    """Missing file -> empty state (the layer is opt-in)."""
    if not path.exists():
        return SeasonsState()
    raw = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    milestones = {
        str(k): MilestoneProgress(
            logged={_date(d): int(m) for d, m in (v.get("logged") or {}).items()},
            done=_date(v.get("done")),
        )
        for k, v in (raw.get("milestones") or {}).items()
    }
    last_run = raw.get("last_run") or {}
    return SeasonsState(
        milestones=milestones,
        rest_until=_date(raw.get("rest_until")),
        last_run={"main": last_run.get("main"), "side": last_run.get("side"), "resting": bool(last_run.get("resting", False))},
    )


def save_seasons_state(path: Path, state: SeasonsState) -> None:
    raw = {
        "milestones": {
            k: {"logged": {d.isoformat(): m for d, m in sorted(v.logged.items())}, "done": v.done.isoformat() if v.done else None}
            for k, v in sorted(state.milestones.items())
        },
        "rest_until": state.rest_until.isoformat() if state.rest_until else None,
        "last_run": state.last_run,
    }
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(yaml.safe_dump(raw, sort_keys=False, allow_unicode=True), encoding="utf-8")


# --- validation -------------------------------------------------------------


@dataclass(frozen=True)
class SyllabusFacts:
    """What the validator needs to know about one syllabus in config.yaml."""

    enabled: bool
    tracks: frozenset[tuple[str, str]]
    module_count: int


def validate(
    seasons: Seasons,
    state: SeasonsState,
    syllabuses: dict[str, SyllabusFacts],
) -> tuple[list[str], list[str]]:
    """Return (errors, warnings). Errors block the run; warnings are logged."""
    errors: list[str] = []
    warnings: list[str] = []
    r = seasons.rhythm

    for label, t in (("sleep.from", r.sleep_from), ("sleep.to", r.sleep_to), ("fixed_hours.from", r.fixed_from), ("fixed_hours.to", r.fixed_to), ("shutdown", r.shutdown)):
        if not _HHMM.match(t):
            errors.append(f"rhythm.{label}: not HH:MM: {t!r}")
    errors += [f"rhythm.fixed_hours.days: unknown weekday {d!r}" for d in r.fixed_days if d not in WEEKDAYS]
    for day, b in r.deep_blocks.items():
        if day not in WEEKDAYS:
            errors.append(f"rhythm.deep_blocks: unknown weekday {day!r}")
        if not _HHMM.match(b.start):
            errors.append(f"rhythm.deep_blocks.{day}.start: not HH:MM: {b.start!r}")
        if b.minutes < 15:
            errors.append(f"rhythm.deep_blocks.{day}.minutes: must be >= 15, got {b.minutes}")
        if b.lane not in LANES:
            errors.append(f"rhythm.deep_blocks.{day}.lane: must be main|side, got {b.lane!r}")

    seen: set[str] = set()
    for m in seasons.bucket:
        where = f"bucket[{m.id or '?'}]"
        if not _SLUG.match(m.id):
            errors.append(f"{where}: id must be a slug, got {m.id!r}")
        if m.id in seen:
            errors.append(f"{where}: duplicate id")
        seen.add(m.id)
        if m.hours < 1:
            errors.append(f"{where}: hours must be >= 1, got {m.hours}")
        if m.lane not in LANES:
            errors.append(f"{where}: lane must be main|side, got {m.lane!r}")
        if m.track and m.modules:
            errors.append(f"{where}: at most one of track / modules")
        if m.bare:
            if m.track or m.modules:
                errors.append(f"{where}: track/modules need a syllabus")
            continue
        facts = syllabuses.get(m.syllabus or "")
        if facts is None:
            errors.append(f"{where}: unknown syllabus {m.syllabus!r}")
            continue
        if not facts.enabled:
            errors.append(f"{where}: syllabus {m.syllabus!r} is disabled in config.yaml")
        if m.track and m.track not in facts.tracks:
            errors.append(f"{where}: track {m.track!r} not declared by {m.syllabus!r}")
        if m.modules:
            lo, hi = m.modules
            if not (1 <= lo <= hi <= facts.module_count):
                errors.append(f"{where}: modules {list(m.modules)} outside 1..{facts.module_count}")

    dseen: set[str] = set()
    for d in seasons.disciplines:
        where = f"disciplines[{d.id or '?'}]"
        if not _SLUG.match(d.id):
            errors.append(f"{where}: id must be a slug, got {d.id!r}")
        if d.id in dseen:
            errors.append(f"{where}: duplicate id")
        dseen.add(d.id)
        if d.minutes < 5:
            errors.append(f"{where}: minutes must be >= 5, got {d.minutes}")
        if not _HHMM.match(d.start):
            errors.append(f"{where}: start not HH:MM: {d.start!r}")
        if not d.days:
            errors.append(f"{where}: days must be non-empty")
        errors += [f"{where}: unknown weekday {x!r}" for x in d.days if x not in WEEKDAYS]

    warnings += [f"state.milestones[{k}]: not in bucket (orphan)" for k in state.milestones if k not in seen]
    return errors, warnings
