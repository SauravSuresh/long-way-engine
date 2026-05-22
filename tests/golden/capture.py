"""Golden-output capture: serialize run() decisions + dashboard data
for a given date into a stable, diffable JSON form.

Used twice: once before the refactor (pinned in tests/golden/<date>.json),
once after (test asserts the new output matches byte-for-byte).
"""

from __future__ import annotations

import json
from dataclasses import asdict, is_dataclass
from datetime import date
from pathlib import Path
from typing import Any

from src.cache import load_cache
from src.clock import Clock
from src.config import load_config
from src.scheduler import should_create_today
from src.state import load_state
from src.templates import load_templates, resolve_variables

REPO_ROOT = Path(__file__).resolve().parent.parent.parent


def _serialize(obj: Any) -> Any:
    if is_dataclass(obj):
        return {k: _serialize(v) for k, v in asdict(obj).items()}
    if isinstance(obj, dict):
        return {k: _serialize(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple, set)):
        return [_serialize(v) for v in obj]
    if isinstance(obj, Path):
        return str(obj)
    return obj


def capture(
    today: date,
    config_path: Path = REPO_ROOT / "config.yaml",
    state_path: Path = REPO_ROOT / "state.yaml",
    env_path: Path = REPO_ROOT / ".env",
    templates_dir: Path | None = None,
) -> dict[str, Any]:
    """Return a stable snapshot of every decision the engine makes for `today`.

    Captures: which templates fire, which skip (and why), resolved
    variables in titles, due strings, descriptions. Excludes: Todoist
    API state (network), cache writes (filesystem), wall-clock now().
    """
    config = load_config(config_path, env_path)
    state = load_state(state_path)
    if templates_dir is None:
        templates_dir = REPO_ROOT / "task_templates"
    templates = load_templates(templates_dir)

    out: dict[str, Any] = {"date": today.isoformat(), "templates": []}

    for tpl in templates:
        entry: dict[str, Any] = {"id": tpl.id, "cadence": tpl.cadence}
        try:
            fires = should_create_today(tpl, today, state, config)
        except NotImplementedError as e:
            entry["fires"] = False
            entry["error"] = str(e)
            out["templates"].append(entry)
            continue
        entry["fires"] = fires
        if fires:
            resolved = resolve_variables(tpl, state, config, today)
            if resolved is None:
                entry["error"] = "variable resolution failed"
            else:
                entry["title"] = resolved.title
                entry["description"] = resolved.description
                entry["due"] = resolved.due
                entry["labels"] = list(resolved.labels)
        out["templates"].append(entry)

    return out


def write_golden(today: date, out_dir: Path) -> Path:
    snapshot = capture(today)
    path = out_dir / f"{today.isoformat()}.json"
    path.write_text(
        json.dumps(snapshot, indent=2, sort_keys=True, default=str),
        encoding="utf-8",
    )
    return path


if __name__ == "__main__":
    import sys
    iso = sys.argv[1]
    y, m, d = (int(x) for x in iso.split("-"))
    out = capture(date(y, m, d))
    print(json.dumps(out, indent=2, sort_keys=True, default=str))
