"""scripts/show_timetable.py — preview the resolved weekly timetable.

Reads config.yaml and curricula/<key>/rituals/*.yaml for each enabled
syllabus.  Resolves each ritual template's effective clock-time from the
per-syllabus ritual_times map, figures out which weekdays it fires, and
prints a grid.  Surfaces (slot, time) collisions across syllabuses.

Exit code 0 — no collisions.
Exit code 1 — one or more collisions found.

Never calls Todoist; never reads or writes cache/state files.

Usage:
    python -m scripts.show_timetable [--config PATH] [--env PATH]
        [--repo-root PATH] [--syllabus KEY] [--json]
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from collections import defaultdict
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

WEEKDAYS = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]

WEEKDAY_BY_NAME: dict[str, str] = {
    "monday": "Mon",
    "tuesday": "Tue",
    "wednesday": "Wed",
    "thursday": "Thu",
    "friday": "Fri",
    "saturday": "Sat",
    "sunday": "Sun",
}

# Regex to extract the ritual_times key from a `due` string like
# "today at {ritual_times.morning_reading}"
_DUE_SLOT_RE = re.compile(r"\{ritual_times\.([^}]+)\}")


# ---------------------------------------------------------------------------
# Data classes
# ---------------------------------------------------------------------------


@dataclass
class TimetableRow:
    time: str
    weekdays: set[str]
    syllabus: str
    ritual: str
    slot: str = ""  # ritual_times key, e.g. "morning_reading"


@dataclass
class Collision:
    time: str
    weekday: str
    rows: list[TimetableRow] = field(default_factory=list)


# ---------------------------------------------------------------------------
# Core logic
# ---------------------------------------------------------------------------


def _extract_slot_key(tpl: dict[str, Any]) -> str | None:
    """Return the ritual_times slot key from a template dict.

    Accepts either:
    - an explicit ``ritual_time`` field (used in test fixtures and future YAML)
    - or the slot embedded in the ``due`` string: "today at {ritual_times.KEY}"
    """
    if "ritual_time" in tpl:
        return str(tpl["ritual_time"])
    due = tpl.get("due", "")
    if due:
        m = _DUE_SLOT_RE.search(str(due))
        if m:
            return m.group(1)
    return None


def _weekdays_for_template(tpl: dict[str, Any], *, sunday_off: bool) -> set[str]:
    """Return the set of WEEKDAYS short-names that this template fires on.

    Rules:
    - cadence == "daily": all weekdays, minus Sunday if sunday_off, minus any
      explicit "sunday" / "pair_day" in skip_if (we drop skip_if:pair_day too,
      since we don't know the actual pair_day here — it appears in the grid
      notes but we mark the slot as firing on that day).
    - cadence == "weekly": use ``day_of_week`` or ``weekday`` field.
    - cadence in {monthly, quarterly, annual}: use ``day_of_week`` or
      ``weekday`` if declared; otherwise empty set (calendar-dependent).
    - unknown cadences: same as monthly/quarterly/annual.
    """
    cadence = str(tpl.get("cadence", "")).lower()

    if cadence == "daily":
        days = set(WEEKDAYS)
        # Drop sunday if sunday_off
        skip_raw = tpl.get("skip_if", [])
        if isinstance(skip_raw, str):
            skip_raw = [skip_raw]
        skip_lower = {str(s).lower() for s in skip_raw}
        if sunday_off or "sunday" in skip_lower:
            days.discard("Sun")
        return days

    if cadence == "weekly":
        day_name = tpl.get("day_of_week") or tpl.get("weekday")
        if day_name:
            short = WEEKDAY_BY_NAME.get(str(day_name).lower())
            if short:
                return {short}
        return set()

    # monthly / quarterly / annual / once-per-module / unknown
    day_name = tpl.get("day_of_week") or tpl.get("weekday")
    if day_name:
        # day_of_month values like "last-saturday" or integer day numbers
        # are not weekday names — skip them
        val = str(day_name).lower()
        short = WEEKDAY_BY_NAME.get(val)
        if short:
            return {short}
    return set()


def _load_rituals_for_syllabus(rituals_dir: Path) -> list[dict[str, Any]]:
    """Load all YAML ritual templates from a syllabus rituals directory."""
    templates: list[dict[str, Any]] = []
    if not rituals_dir.is_dir():
        return templates
    for yaml_file in sorted(rituals_dir.glob("*.yaml")):
        with yaml_file.open("r", encoding="utf-8") as f:
            data = yaml.safe_load(f)
        if isinstance(data, list):
            templates.extend(data)
        elif isinstance(data, dict):
            templates.append(data)
    return templates


def build_rows(cfg: Any, repo_root: Path) -> list[TimetableRow]:
    """Walk every enabled syllabus's ritual templates and emit TimetableRows.

    Only emits rows for templates that have a resolvable ritual_times slot
    AND a non-empty weekdays set.

    ``cfg`` must be a ``MultiSyllabusConfig``-compatible object with:
        - .priority_order: list[str]
        - .syllabuses: dict[str, SyllabusEntry]  (each with .enabled, .path, .ritual_times)
        - .sunday_off: bool
    """
    rows: list[TimetableRow] = []

    for key in cfg.priority_order:
        entry = cfg.syllabuses[key]
        if not entry.enabled:
            continue

        rituals_dir = repo_root / entry.path / "rituals"
        templates = _load_rituals_for_syllabus(rituals_dir)

        for tpl in templates:
            slot_key = _extract_slot_key(tpl)
            if slot_key is None:
                continue

            # Resolve clock time: per-syllabus override already merged into entry.ritual_times
            clock_time = entry.ritual_times.get(slot_key)
            if clock_time is None:
                # slot key not in any ritual_times map — skip
                continue

            weekdays = _weekdays_for_template(tpl, sunday_off=cfg.sunday_off)
            if not weekdays:
                continue

            rows.append(
                TimetableRow(
                    time=str(clock_time),
                    weekdays=weekdays,
                    syllabus=key,
                    ritual=str(tpl.get("id", slot_key)),
                    slot=slot_key,
                )
            )

    return rows


def find_collisions(rows: list[TimetableRow]) -> list[Collision]:
    """Return Collision objects for each (time, weekday) bucket with >1 syllabus."""
    # bucket by (time, weekday)
    buckets: dict[tuple[str, str], list[TimetableRow]] = defaultdict(list)
    for row in rows:
        for wd in row.weekdays:
            buckets[(row.time, wd)].append(row)

    collisions: list[Collision] = []
    for (time, weekday), bucket_rows in sorted(buckets.items()):
        syllabuses_in_bucket = {r.syllabus for r in bucket_rows}
        if len(syllabuses_in_bucket) > 1:
            collisions.append(Collision(time=time, weekday=weekday, rows=list(bucket_rows)))

    return collisions


def render(rows: list[TimetableRow], collisions: list[Collision]) -> str:
    """Render a human-readable weekly timetable grid."""
    lines: list[str] = []

    # Header
    lines.append("=" * 72)
    lines.append("  WEEKLY TIMETABLE")
    lines.append("=" * 72)

    # Group rows by time, then sort by time
    by_time: dict[str, list[TimetableRow]] = defaultdict(list)
    for row in rows:
        by_time[row.time].append(row)

    col_w = 8  # weekday column width

    # Header row
    header = f"{'TIME':<8}" + "".join(f"{wd:<{col_w}}" for wd in WEEKDAYS)
    lines.append(header)
    lines.append("-" * len(header))

    for time in sorted(by_time.keys()):
        time_rows = by_time[time]
        # Collect per-weekday info: list of "syllabus:ritual" strings
        per_wd: dict[str, list[str]] = defaultdict(list)
        for row in time_rows:
            label = f"{row.syllabus}:{row.ritual}"
            for wd in row.weekdays:
                per_wd[wd].append(label)

        # Find max lines needed across all weekdays
        max_lines = max((len(v) for v in per_wd.values()), default=1)

        for line_idx in range(max_lines):
            if line_idx == 0:
                prefix = f"{time:<8}"
            else:
                prefix = " " * 8
            cells = []
            for wd in WEEKDAYS:
                entries = per_wd.get(wd, [])
                if line_idx < len(entries):
                    cell = entries[line_idx]
                    # Truncate to column width - 1
                    cell = cell[: col_w - 1]
                else:
                    cell = ""
                cells.append(f"{cell:<{col_w}}")
            lines.append(prefix + "".join(cells))

    lines.append("")

    # Row listing (slot key visible here)
    lines.append("  All scheduled rituals:")
    for row in sorted(rows, key=lambda r: (r.time, r.syllabus, r.ritual)):
        days_str = ",".join(wd for wd in WEEKDAYS if wd in row.weekdays)
        lines.append(f"    {row.time}  [{row.slot}]  {row.syllabus}/{row.ritual}  ({days_str})")
    lines.append("")

    # Collision report
    if collisions:
        lines.append("!" * 72)
        lines.append(f"  COLLISIONS DETECTED: {len(collisions)}")
        lines.append("!" * 72)
        for col in collisions:
            lines.append(f"  {col.time} on {col.weekday}:")
            for row in col.rows:
                lines.append(f"    - {row.syllabus} / {row.ritual}")
        lines.append("")
    else:
        lines.append("  No collisions.")
        lines.append("")

    return "\n".join(lines)


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Preview the weekly ritual timetable across syllabuses."
    )
    parser.add_argument("--config", default="config.yaml", help="Path to config.yaml")
    parser.add_argument("--env", default=".env", help="Path to .env file")
    parser.add_argument("--repo-root", default=".", help="Repo root directory")
    parser.add_argument("--syllabus", default=None, help="Filter to one syllabus key")
    parser.add_argument("--json", action="store_true", help="Machine-readable JSON output")
    args = parser.parse_args(argv)

    repo_root = Path(args.repo_root).resolve()
    config_path = Path(args.config) if Path(args.config).is_absolute() else repo_root / args.config
    env_path = Path(args.env) if Path(args.env).is_absolute() else repo_root / args.env

    # Adjust for absolute paths passed directly (e.g. in tests)
    if Path(args.config).is_absolute():
        config_path = Path(args.config)
    if Path(args.env).is_absolute():
        env_path = Path(args.env)

    # Use lazy import so the script is importable without src on sys.path
    _repo_root = Path(__file__).resolve().parent.parent
    if str(_repo_root) not in sys.path:
        sys.path.insert(0, str(_repo_root))

    from src.config import load_multi_syllabus_config  # noqa: E402

    cfg = load_multi_syllabus_config(config_path, env_path, strict=False)

    # Optional single-syllabus filter
    if args.syllabus:
        if args.syllabus not in cfg.syllabuses:
            sys.stderr.write(f"Unknown syllabus key: {args.syllabus!r}\n")
            return 2
        # Narrow priority_order and syllabuses
        cfg.priority_order = [args.syllabus]

    rows = build_rows(cfg, repo_root)
    collisions = find_collisions(rows)

    if getattr(args, "json"):
        output = {
            "rows": [
                {
                    "time": r.time,
                    "weekdays": sorted(r.weekdays),
                    "syllabus": r.syllabus,
                    "ritual": r.ritual,
                }
                for r in rows
            ],
            "collisions": [
                {
                    "time": c.time,
                    "weekday": c.weekday,
                    "rows": [
                        {"time": r.time, "weekdays": sorted(r.weekdays), "syllabus": r.syllabus, "ritual": r.ritual}
                        for r in c.rows
                    ],
                }
                for c in collisions
            ],
        }
        sys.stdout.write(json.dumps(output, indent=2) + "\n")
    else:
        sys.stdout.write(render(rows, collisions))
        sys.stdout.write("\n")

    return 1 if collisions else 0


if __name__ == "__main__":
    sys.exit(main())
