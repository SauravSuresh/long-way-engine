"""Load config.yaml and the Todoist token from .env or env vars.

The token is the only secret. It must never be logged. The Config dataclass
redacts the token in its repr; a logging filter (installed in main.py)
strips token occurrences from any log record as a defense in depth.
"""

from __future__ import annotations

import logging
import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml

logger = logging.getLogger(__name__)

ENV_TOKEN_KEY = "TODOIST_TOKEN"


@dataclass
class TodoistConfig:
    project_id: str
    labels: dict[str, str] = field(default_factory=dict)


@dataclass
class DashboardConfig:
    github_username: str
    repo_name: str


@dataclass
class Config:
    todoist: TodoistConfig
    ritual_times: dict[str, str]
    sunday_off: bool
    dashboard: DashboardConfig
    todoist_token: str
    pair_day: str | None = None  # e.g. "thursday" — daily-evening-hands-on skips on this weekday
    curriculum_dir: Path = field(default_factory=lambda: Path("curriculum"))

    def __repr__(self) -> str:
        return (
            f"Config(todoist={self.todoist!r}, "
            f"ritual_times={self.ritual_times!r}, "
            f"sunday_off={self.sunday_off!r}, "
            f"pair_day={self.pair_day!r}, "
            f"dashboard={self.dashboard!r}, "
            f"curriculum_dir={self.curriculum_dir!r}, "
            f"todoist_token='***REDACTED***')"
        )


def parse_env_file(path: Path) -> dict[str, str]:
    """Tiny stdlib-only .env parser.

    Lines like KEY=value. Blank lines and lines starting with # are ignored.
    The value is taken verbatim after the first =, with surrounding whitespace
    stripped. Quotes are not stripped; if you use them, they become part of
    the value.
    """
    out: dict[str, str] = {}
    if not path.exists():
        return out
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        if "=" not in line:
            continue
        key, _, value = line.partition("=")
        out[key.strip()] = value.strip()
    return out


def _read_token(env_path: Path) -> str:
    """Token from .env if present, else from environment."""
    env_file = parse_env_file(env_path)
    token = env_file.get(ENV_TOKEN_KEY) or os.environ.get(ENV_TOKEN_KEY, "")
    if not token:
        raise RuntimeError(
            f"{ENV_TOKEN_KEY} not set. Put it in .env or export it in the shell."
        )
    return token


def load_config(yaml_path: Path, env_path: Path) -> Config:
    """Load config.yaml and resolve the Todoist token."""
    with yaml_path.open("r", encoding="utf-8") as f:
        raw: dict[str, Any] = yaml.safe_load(f)

    todoist_raw = raw["todoist"]
    todoist = TodoistConfig(
        project_id=str(todoist_raw["project_id"]),
        labels=dict(todoist_raw.get("labels", {})),
    )
    dashboard_raw = raw["dashboard"]
    dashboard = DashboardConfig(
        github_username=str(dashboard_raw["github_username"]),
        repo_name=str(dashboard_raw["repo_name"]),
    )
    pair_day = raw.get("pair_day")
    if pair_day is not None:
        pair_day = str(pair_day).lower()
    curriculum_dir = raw.get("curriculum_dir", "curriculum")
    curriculum_dir = Path(curriculum_dir)
    return Config(
        todoist=todoist,
        ritual_times=dict(raw.get("ritual_times", {})),
        sunday_off=bool(raw.get("sunday_off", True)),
        dashboard=dashboard,
        todoist_token=_read_token(env_path),
        pair_day=pair_day,
        curriculum_dir=curriculum_dir,
    )


@dataclass
class SyllabusEntry:
    key: str
    path: Path
    todoist_project_id: str
    state_file: Path
    enabled: bool
    ritual_times: dict[str, str]
    allow_slot_overlap: bool = False


@dataclass
class MultiSyllabusConfig:
    """Repo-wide config for the multi-syllabus engine.

    `default_ritual_times` is the top-level fallback. Per-syllabus effective
    times live on `syllabuses[key].ritual_times` after override merging — use
    those when scheduling tasks, not this field.
    """

    default_ritual_times: dict[str, str]
    priority_order: list[str]
    syllabuses: dict[str, SyllabusEntry]
    sunday_off: bool
    pair_day: str | None
    dashboard: DashboardConfig
    todoist_token: str


class SlotCollisionError(ValueError):
    """Two enabled syllabuses claim the same (ritual_times_key, clock_time)."""


def load_multi_syllabus_config(yaml_path: Path, env_path: Path, *, strict: bool = True) -> MultiSyllabusConfig:
    with yaml_path.open("r", encoding="utf-8") as f:
        raw: dict[str, Any] = yaml.safe_load(f) or {}

    top_rt = dict(raw.get("ritual_times") or {})
    priority_order = list(raw.get("priority_order") or [])
    syllabuses_raw = dict(raw.get("syllabuses") or {})

    syllabuses: dict[str, SyllabusEntry] = {}
    for key, block in syllabuses_raw.items():
        rt = dict(top_rt)
        rt.update(dict(block.get("ritual_times") or {}))
        syllabuses[key] = SyllabusEntry(
            key=key,
            path=Path(block["path"]),
            todoist_project_id=str(block["todoist_project_id"]),
            state_file=Path(block["state_file"]),
            enabled=bool(block.get("enabled", True)),
            ritual_times=rt,
            allow_slot_overlap=bool(block.get("allow_slot_overlap", False)),
        )

    # priority_order must equal the set of enabled syllabuses.
    enabled_keys = {k for k, s in syllabuses.items() if s.enabled}
    if set(priority_order) != enabled_keys:
        raise ValueError(
            f"priority_order {sorted(priority_order)} must equal the set of enabled "
            f"syllabuses {sorted(enabled_keys)}"
        )

    # Slot-collision check: (slot, clock_time) unique across enabled syllabuses
    # unless at least one party has allow_slot_overlap=True.
    # Skip when strict=False (e.g. the timetable visualizer wants to show collisions).
    if strict:
        seen: dict[tuple[str, str], str] = {}
        for key in priority_order:
            sy = syllabuses[key]
            for slot, when in sy.ritual_times.items():
                existing = seen.get((slot, when))
                if existing is None:
                    seen[(slot, when)] = key
                    continue
                other = syllabuses[existing]
                if sy.allow_slot_overlap or other.allow_slot_overlap:
                    continue
                raise SlotCollisionError(
                    f"slot collision: {existing}:{slot}@{when} and {key}:{slot}@{when} "
                    f"— change one clock time or set allow_slot_overlap on one side"
                )

    dashboard_raw = raw["dashboard"]
    dashboard = DashboardConfig(
        github_username=str(dashboard_raw["github_username"]),
        repo_name=str(dashboard_raw["repo_name"]),
    )
    pair_day = raw.get("pair_day")
    if pair_day is not None:
        pair_day = str(pair_day).lower()

    return MultiSyllabusConfig(
        default_ritual_times=top_rt,
        priority_order=priority_order,
        syllabuses=syllabuses,
        sunday_off=bool(raw.get("sunday_off", True)),
        pair_day=pair_day,
        dashboard=dashboard,
        todoist_token=_read_token(env_path),
    )


class TokenRedactingFilter(logging.Filter):
    """Strip the Todoist token from any log record. Defense in depth."""

    def __init__(self, token: str) -> None:
        super().__init__()
        self._token = token

    def filter(self, record: logging.LogRecord) -> bool:
        if not self._token:
            return True
        if isinstance(record.msg, str) and self._token in record.msg:
            record.msg = record.msg.replace(self._token, "***REDACTED***")
        if record.args:
            try:
                redacted = tuple(
                    a.replace(self._token, "***REDACTED***") if isinstance(a, str) else a
                    for a in record.args
                )
                record.args = redacted
            except Exception:
                pass
        return True
