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
