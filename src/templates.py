"""Load task templates from YAML and resolve variable placeholders.

Phase A supports {current_book} (from state) and {ritual_times.<key>}
(from config). Unknown placeholders cause the affected template to be
skipped with a warning, not a crash.
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml

from src.config import Config
from src.state import State

logger = logging.getLogger(__name__)

_PLACEHOLDER = re.compile(r"\{([a-zA-Z_][\w.]*)\}")


@dataclass
class Template:
    id: str
    title: str
    description: str
    due: str
    labels: list[str]
    cadence: str
    skip_if: str | None = None
    raw: dict[str, Any] = field(default_factory=dict)


@dataclass
class ResolvedTemplate:
    id: str
    title: str
    description: str
    due: str
    labels: list[str]
    cadence: str
    skip_if: str | None


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
            templates.append(
                Template(
                    id=str(entry["id"]),
                    title=str(entry["title"]),
                    description=str(entry.get("description", "")),
                    due=str(entry.get("due", "")),
                    labels=list(entry.get("labels", []) or []),
                    cadence=str(entry["cadence"]),
                    skip_if=entry.get("skip_if"),
                    raw=entry,
                )
            )
    return templates


def _lookup(name: str, state: State, config: Config) -> str:
    """Resolve a single dotted placeholder name."""
    if name == "current_book":
        return state.current_book
    if name.startswith("ritual_times."):
        key = name.split(".", 1)[1]
        if key not in config.ritual_times:
            raise MissingVariable(f"ritual_times.{key} not in config")
        return config.ritual_times[key]
    raise MissingVariable(name)


def _resolve_string(s: str, state: State, config: Config) -> str:
    def replace(match: re.Match[str]) -> str:
        return _lookup(match.group(1), state, config)

    return _PLACEHOLDER.sub(replace, s)


def resolve_variables(
    template: Template, state: State, config: Config
) -> ResolvedTemplate | None:
    """Resolve placeholders. Returns None if any variable is missing."""
    try:
        return ResolvedTemplate(
            id=template.id,
            title=_resolve_string(template.title, state, config),
            description=_resolve_string(template.description, state, config),
            due=_resolve_string(template.due, state, config),
            labels=list(template.labels),
            cadence=template.cadence,
            skip_if=template.skip_if,
        )
    except MissingVariable as e:
        logger.warning(
            "template %s references missing variable %s; skipping",
            template.id,
            e,
        )
        return None
