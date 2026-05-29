"""Golden-output capture: serialize run() decisions for a given date into
a stable, diffable JSON form.

Uses the multi-syllabus config shape (T5+). Iterates over enabled syllabuses
in priority_order, annotates each template entry with its `syllabus_key`.

Used twice: once before the refactor (pinned in tests/golden/<date>.json),
once after (test asserts the new output matches byte-for-byte).
"""

from __future__ import annotations

import json
from datetime import date
from pathlib import Path
from typing import Any

import yaml

from src.config import Config, DashboardConfig, TodoistConfig, load_multi_syllabus_config
from src.scheduler import should_create_today
from src.state import load_shared_state, load_syllabus_state
from src.syllabus import load_syllabus
from src.templates import load_templates, resolve_variables

REPO_ROOT = Path(__file__).resolve().parent.parent.parent


def capture(
    today: date,
    config_path: Path = REPO_ROOT / "config.yaml",
    env_path: Path = REPO_ROOT / ".env",
) -> dict[str, Any]:
    """Return a stable snapshot of every decision the engine makes for `today`.

    Captures: which templates fire, which skip (and why), resolved
    variables in titles, due strings, descriptions, and the syllabus_key
    for each template entry. Excludes: Todoist API state (network),
    cache writes (filesystem), wall-clock now().
    """
    cfg = load_multi_syllabus_config(config_path, env_path)

    out: dict[str, Any] = {"date": today.isoformat(), "templates": []}

    for key in cfg.priority_order:
        entry = cfg.syllabuses[key]
        if not entry.enabled:
            continue

        state_path = entry.state_file if entry.state_file.is_absolute() else REPO_ROOT / entry.state_file
        syllabus_path = entry.path if entry.path.is_absolute() else REPO_ROOT / entry.path

        state = load_syllabus_state(state_path)
        syllabus = load_syllabus(syllabus_path)

        template_paths = [
            syllabus_path / "rituals",
            syllabus_path / "modules.yaml",
        ]
        templates = load_templates(template_paths)

        # Config shim: adapter so scheduler + resolve_variables keep working.
        per_cfg = Config(
            todoist=TodoistConfig(project_id=entry.todoist_project_id, labels={}),
            ritual_times=entry.ritual_times,
            sunday_off=cfg.sunday_off,
            pair_day=cfg.pair_day,
            dashboard=cfg.dashboard,
            todoist_token=cfg.todoist_token,
            curriculum_dir=syllabus_path,
        )

        for tpl in templates:
            entry_dict: dict[str, Any] = {
                "id": tpl.id,
                "cadence": tpl.cadence,
                "syllabus_key": key,
            }
            try:
                fires = should_create_today(tpl, today, state, per_cfg)
            except NotImplementedError as e:
                entry_dict["fires"] = False
                entry_dict["error"] = str(e)
                out["templates"].append(entry_dict)
                continue
            entry_dict["fires"] = fires
            if fires:
                resolved = resolve_variables(tpl, state, per_cfg, today, syllabus=syllabus)
                if resolved is None:
                    entry_dict["error"] = "variable resolution failed"
                else:
                    entry_dict["title"] = resolved.title
                    entry_dict["description"] = resolved.description
                    entry_dict["due"] = resolved.due
                    entry_dict["labels"] = list(resolved.labels)
            out["templates"].append(entry_dict)

    return out


def build_multi_syllabus_scenario(tmp: Path, scenario: str) -> tuple[Path, Path]:
    """Write a fully-synthetic two-syllabus workspace into `tmp` and return
    (config_path, env_path).

    scenario="clean":   alpha-way and beta-way use non-overlapping clock times.
    scenario="overlap": both use the same clock times; beta-way has allow_slot_overlap=True.

    Both syllabuses have a single daily ritual (morning_reading) and no modules.yaml
    entries, so the captured output is short and fully deterministic.
    """
    alpha_path = tmp / "curricula" / "alpha-way"
    beta_path = tmp / "curricula" / "beta-way"
    for p in (alpha_path / "rituals", beta_path / "rituals"):
        p.mkdir(parents=True)

    _ALPHA_SYLLABUS = {
        "meta": {"name": "Alpha Way", "total_months": 12, "start_month_index": 1},
        "phases": [{"number": 1, "name": "Foundations", "months": [1, 12]}],
        "books": [
            {
                "title": "Foundations Book",
                "author": "Author A",
                "phase": 1,
                "months": [1, 6],
            }
        ],
        "modules": [{"number": 1, "name": "Module One", "phase": 1}],
        "primary_book_by_month": {1: "Foundations Book"},
    }
    _BETA_SYLLABUS = {
        "meta": {"name": "Beta Way", "total_months": 12, "start_month_index": 1},
        "phases": [{"number": 1, "name": "Foundations", "months": [1, 12]}],
        "books": [
            {
                "title": "Beta Book",
                "author": "Author B",
                "phase": 1,
                "months": [1, 6],
            }
        ],
        "modules": [{"number": 1, "name": "Beta Module", "phase": 1}],
        "primary_book_by_month": {1: "Beta Book"},
    }
    _ALPHA_DAILY = [
        {
            "id": "alpha-morning-reading",
            "title": "Alpha morning reading: {current_book}",
            "description": "30 min alpha reading.\nToday: {current_book}.\n",
            "due": "today at {ritual_times.morning_reading}",
            "labels": ["daily-ritual"],
            "cadence": "daily",
            "skip_if": "sunday",
        }
    ]
    _BETA_DAILY = [
        {
            "id": "beta-morning-reading",
            "title": "Beta morning reading: {current_book}",
            "description": "30 min beta reading.\nToday: {current_book}.\n",
            "due": "today at {ritual_times.morning_reading}",
            "labels": ["daily-ritual"],
            "cadence": "daily",
            "skip_if": "sunday",
        }
    ]
    _ALPHA_STATE = {
        "start_date": "2026-05-01",
        "phase": 1,
        "month": 2,
        "current_module": 1,
        "current_book": "Foundations Book",
        "completed_modules": [],
        "active_branches": [],
        "paused": False,
    }
    _BETA_STATE = {
        "start_date": "2026-05-01",
        "phase": 1,
        "month": 2,
        "current_module": 1,
        "current_book": "Beta Book",
        "completed_modules": [],
        "active_branches": [],
        "paused": False,
    }

    (alpha_path / "syllabus.yaml").write_text(yaml.dump(_ALPHA_SYLLABUS))
    (alpha_path / "rituals" / "daily.yaml").write_text(yaml.dump(_ALPHA_DAILY))
    (alpha_path / "modules.yaml").write_text("[]\n")

    (beta_path / "syllabus.yaml").write_text(yaml.dump(_BETA_SYLLABUS))
    (beta_path / "rituals" / "daily.yaml").write_text(yaml.dump(_BETA_DAILY))
    (beta_path / "modules.yaml").write_text("[]\n")

    (tmp / "state").mkdir(exist_ok=True)
    (tmp / "state" / "alpha-way.yaml").write_text(yaml.dump(_ALPHA_STATE))
    (tmp / "state" / "beta-way.yaml").write_text(yaml.dump(_BETA_STATE))
    (tmp / "state" / "shared.yaml").write_text("timezone: UTC\n")

    top_rt = {"morning_reading": "06:00", "anki": "08:30"}
    alpha_block: dict[str, Any] = {
        "path": str(alpha_path),
        "todoist_project_id": "alpha-project-001",
        "state_file": str(tmp / "state" / "alpha-way.yaml"),
        "enabled": True,
    }
    beta_block: dict[str, Any] = {
        "path": str(beta_path),
        "todoist_project_id": "beta-project-001",
        "state_file": str(tmp / "state" / "beta-way.yaml"),
        "enabled": True,
    }

    if scenario == "clean":
        beta_block["ritual_times"] = {"morning_reading": "07:00", "anki": "09:30"}
    else:
        # overlap: same times as alpha-way; allow_slot_overlap suppresses the error
        beta_block["allow_slot_overlap"] = True

    config_dict: dict[str, Any] = {
        "ritual_times": top_rt,
        "priority_order": ["alpha-way", "beta-way"],
        "syllabuses": {"alpha-way": alpha_block, "beta-way": beta_block},
        "sunday_off": True,
        "pair_day": "thursday",
        "dashboard": {
            "github_username": "SauravSuresh",
            "repo_name": "long-way-engine",
        },
    }

    config_path = tmp / "config.yaml"
    config_path.write_text(yaml.dump(config_dict))
    env_path = tmp / ".env"
    env_path.write_text("TODOIST_TOKEN=test-token\n")
    return config_path, env_path


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
