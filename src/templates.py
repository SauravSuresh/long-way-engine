"""Load task templates from YAML and resolve variable placeholders.

Supported placeholders:
  - {current_book}                   from state
  - {ritual_times.<key>}             from config
  - {year}, {month}, {date}          from `today` (calendar)
  - {iso_year}, {iso_week}           from `today` (ISO calendar)
  - {quarter}                        1..4 derived from today.month

A format spec is allowed: {month:02d}, {iso_week:02d}, etc.

Unknown placeholders skip the affected template with a warning.
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path
from typing import Any

import yaml

from src import syllabus
from src.config import Config
from src.state import State

logger = logging.getLogger(__name__)

# {name} or {name:fmt}
_PLACEHOLDER = re.compile(r"\{([a-zA-Z_][\w.]*)(?::([^}]+))?\}")


@dataclass
class Template:
    id: str
    title: str
    description: str
    due: str
    labels: list[str]
    cadence: str
    skip_if: list[str] = field(default_factory=list)
    day_of_week: str | None = None
    day_of_month: int | str | None = None
    module_number: int | None = None
    raw: dict[str, Any] = field(default_factory=dict)


@dataclass
class ResolvedTemplate:
    id: str
    title: str
    description: str
    due: str
    labels: list[str]
    cadence: str
    skip_if: list[str] = field(default_factory=list)


class MissingVariable(KeyError):
    """Raised when a placeholder cannot be resolved from state/config."""


def load_templates(directory: Path) -> list[Template]:
    """Load every *.yaml in the directory, in lexical order."""
    templates: list[Template] = []
    for path in sorted(directory.glob("*.yaml")):
        with path.open("r", encoding="utf-8") as f:
            entries = yaml.safe_load(f) or []
        if not isinstance(entries, list):
            logger.warning("template file %s is not a list; skipping", path)
            continue
        for entry in entries:
            day_of_month = entry.get("day_of_month")
            if isinstance(day_of_month, bool):
                # YAML's `day_of_month: false` would otherwise sneak through as int 0.
                day_of_month = None
            module_number = entry.get("module_number")
            if module_number is not None:
                module_number = int(module_number)
            # skip_if accepts either a single string ("sunday") or a list
            # (["sunday", "pair_day"]). Normalize to list internally.
            skip_if_raw = entry.get("skip_if")
            if skip_if_raw is None:
                skip_if = []
            elif isinstance(skip_if_raw, list):
                skip_if = [str(s) for s in skip_if_raw]
            else:
                skip_if = [str(skip_if_raw)]
            templates.append(
                Template(
                    id=str(entry["id"]),
                    title=str(entry["title"]),
                    description=str(entry.get("description", "")),
                    due=str(entry.get("due", "")),
                    labels=list(entry.get("labels", []) or []),
                    cadence=str(entry["cadence"]),
                    skip_if=skip_if,
                    day_of_week=entry.get("day_of_week"),
                    day_of_month=day_of_month,
                    module_number=module_number,
                    raw=entry,
                )
            )
    return templates


def _lookup(name: str, state: State, config: Config, today: date) -> str | int:
    """Resolve a single dotted placeholder name. May return int for format-spec callers."""
    if name == "current_book":
        # Override path: state.current_book wins when non-empty (Phase D Q16).
        # Fallback path: syllabus.current_book(state.month) with carry-forward.
        if state.current_book:
            return state.current_book
        return syllabus.current_book(state.month)
    if name.startswith("ritual_times."):
        key = name.split(".", 1)[1]
        if key not in config.ritual_times:
            raise MissingVariable(f"ritual_times.{key} not in config")
        return config.ritual_times[key]
    if name == "year":
        return today.year
    if name == "month":
        return today.month
    if name == "date":
        return today.isoformat()
    iso = today.isocalendar()
    if name == "iso_year":
        return iso[0]
    if name == "iso_week":
        return iso[1]
    if name == "quarter":
        return (today.month - 1) // 3 + 1
    raise MissingVariable(name)


def resolve_string(s: str, state: State, config: Config, today: date) -> str:
    """Resolve placeholders in `s`. Public so reflections.py can reuse."""

    def replace(match: re.Match[str]) -> str:
        name = match.group(1)
        fmt = match.group(2)
        value = _lookup(name, state, config, today)
        if fmt is not None:
            return format(value, fmt)
        return str(value)

    return _PLACEHOLDER.sub(replace, s)


# Backwards-compat alias used internally; new callers should prefer resolve_string.
_resolve_string = resolve_string


def resolve_variables(
    template: Template, state: State, config: Config, today: date
) -> ResolvedTemplate | None:
    """Resolve placeholders. Returns None if any variable is missing."""
    try:
        return ResolvedTemplate(
            id=template.id,
            title=resolve_string(template.title, state, config, today),
            description=resolve_string(template.description, state, config, today),
            due=resolve_string(template.due, state, config, today),
            labels=list(template.labels),
            cadence=template.cadence,
            skip_if=list(template.skip_if),
        )
    except MissingVariable as e:
        logger.warning(
            "template %s references missing variable %s; skipping",
            template.id,
            e,
        )
        return None
