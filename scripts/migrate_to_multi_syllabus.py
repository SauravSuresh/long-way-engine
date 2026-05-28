"""One-shot migration: single-syllabus repo -> multi-syllabus repo.

Idempotent. Run with --dry-run to see what would change without writing.
"""
from __future__ import annotations

import argparse
import json
import re
import shutil
import sys
from pathlib import Path
from typing import Any

import yaml


SHARED_KEYS = {"timezone", "manual_counters", "notes"}
SYLLABUS_KEYS = {
    "start_date",
    "phase",
    "month",
    "current_module",
    "current_book",
    "completed_modules",
    "active_branches",
    "books_state",
    "learning_tracks",
    "paused",
    "paused_since",
    "paused_until",
    "pause_history",
}


def split_state_yaml(old: dict[str, Any]) -> tuple[dict[str, Any], dict[str, Any]]:
    shared = {k: old[k] for k in SHARED_KEYS if k in old}
    syllabus = {k: old[k] for k in SYLLABUS_KEYS if k in old}
    return shared, syllabus


def rewrite_config_yaml(old: dict[str, Any], *, syllabus_name: str) -> dict[str, Any]:
    new: dict[str, Any] = {}
    if "ritual_times" in old:
        new["ritual_times"] = dict(old["ritual_times"])
    new["priority_order"] = [syllabus_name]
    new["syllabuses"] = {
        syllabus_name: {
            "path": f"curricula/{syllabus_name}",
            "todoist_project_id": str(old["todoist"]["project_id"]),
            "state_file": f"state/{syllabus_name}.yaml",
            "enabled": True,
        }
    }
    if "sunday_off" in old:
        new["sunday_off"] = bool(old["sunday_off"])
    if "pair_day" in old:
        new["pair_day"] = old["pair_day"]
    if "dashboard" in old:
        new["dashboard"] = dict(old["dashboard"])
    return new


def wrap_cache(content: dict[str, Any], syllabus_name: str) -> dict[str, Any]:
    if not content:
        return {}
    # Already wrapped? Heuristic: the top-level value is itself a dict of records.
    # A record contains `todoist_id`; a namespace bucket does not at its top level.
    first_val = next(iter(content.values()))
    if (
        isinstance(first_val, dict)
        and first_val
        and isinstance(next(iter(first_val.values()), {}), dict)
        and "todoist_id" not in first_val
    ):
        return content
    return {syllabus_name: dict(content)}


_WEEKLY = re.compile(r"^\d{4}-W\d{2}\.md$")
_MONTHLY = re.compile(r"^\d{4}-\d{2}\.md$")
_QUARTERLY = re.compile(r"^\d{4}-Q[1-4]\.md$")
_ANNUAL = re.compile(r"^\d{4}\.md$")


def classify_reflection(name: str) -> str | None:
    if _WEEKLY.match(name):
        return "weekly"
    if _MONTHLY.match(name):
        return "monthly"
    if _QUARTERLY.match(name):
        return "quarterly"
    if _ANNUAL.match(name):
        return "annual"
    return None


def _read_yaml(p: Path) -> dict[str, Any]:
    with p.open("r", encoding="utf-8") as f:
        return yaml.safe_load(f) or {}


def _write_yaml(p: Path, data: dict[str, Any]) -> None:
    p.parent.mkdir(parents=True, exist_ok=True)
    with p.open("w", encoding="utf-8") as f:
        yaml.safe_dump(data, f, sort_keys=False, allow_unicode=True)


def run_migration(repo_root: Path, *, syllabus_name: str, dry_run: bool) -> int:
    plan: list[str] = []

    old_curriculum = repo_root / "curriculum"
    new_curriculum = repo_root / "curricula" / syllabus_name
    if old_curriculum.exists() and not new_curriculum.exists():
        plan.append(f"move {old_curriculum} -> {new_curriculum}")

    old_state = repo_root / "state.yaml"
    new_shared = repo_root / "state" / "shared.yaml"
    new_syllabus_state = repo_root / "state" / f"{syllabus_name}.yaml"
    if old_state.exists() and not new_shared.exists():
        plan.append(f"split {old_state} -> {new_shared} + {new_syllabus_state}")

    old_config = repo_root / "config.yaml"
    if old_config.exists():
        raw = _read_yaml(old_config)
        if "syllabuses" not in raw:
            plan.append(f"rewrite {old_config}")

    for cache_name in (".task_cache.json", ".completion_cache.json"):
        p = repo_root / cache_name
        if not p.exists():
            continue
        content = json.loads(p.read_text() or "{}")
        if content and syllabus_name not in content:
            plan.append(f"wrap {p} under '{syllabus_name}'")

    old_refl = repo_root / "reflections"
    if old_refl.exists():
        for entry in old_refl.iterdir():
            if entry.is_file() and entry.suffix == ".md":
                cadence = classify_reflection(entry.name)
                if cadence:
                    target = old_refl / syllabus_name / cadence / entry.name
                    if not target.exists():
                        plan.append(f"move {entry} -> {target}")

    if not plan:
        print("nothing to do — repo is already migrated")
        return 0

    print("Plan:")
    for step in plan:
        print(f"  {step}")

    if dry_run:
        print("\n--dry-run: no changes made")
        return 0

    # Execute.
    if old_curriculum.exists() and not new_curriculum.exists():
        new_curriculum.parent.mkdir(parents=True, exist_ok=True)
        shutil.move(str(old_curriculum), str(new_curriculum))

    if old_state.exists() and not new_shared.exists():
        old = _read_yaml(old_state)
        shared, syllabus_data = split_state_yaml(old)
        _write_yaml(new_shared, shared)
        _write_yaml(new_syllabus_state, syllabus_data)
        old_state.unlink()

    if old_config.exists():
        raw = _read_yaml(old_config)
        if "syllabuses" not in raw:
            new_cfg = rewrite_config_yaml(raw, syllabus_name=syllabus_name)
            _write_yaml(old_config, new_cfg)

    for cache_name in (".task_cache.json", ".completion_cache.json"):
        p = repo_root / cache_name
        if not p.exists():
            continue
        content = json.loads(p.read_text() or "{}")
        if content and syllabus_name not in content:
            wrapped = wrap_cache(content, syllabus_name)
            p.write_text(json.dumps(wrapped, indent=2, sort_keys=True) + "\n")

    if old_refl.exists():
        for entry in list(old_refl.iterdir()):
            if entry.is_file() and entry.suffix == ".md":
                cadence = classify_reflection(entry.name)
                if cadence:
                    target = old_refl / syllabus_name / cadence / entry.name
                    target.parent.mkdir(parents=True, exist_ok=True)
                    shutil.move(str(entry), str(target))

    print("\nmigration complete")
    return 0


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(
        description="Migrate single-syllabus repo to multi-syllabus layout"
    )
    ap.add_argument("--name", default="long-way", help="syllabus key (default: long-way)")
    ap.add_argument("--dry-run", action="store_true", help="show plan without writing")
    ap.add_argument(
        "--repo-root", type=Path, default=Path("."), help="repo root (default: cwd)"
    )
    args = ap.parse_args(argv)
    return run_migration(args.repo_root, syllabus_name=args.name, dry_run=args.dry_run)


if __name__ == "__main__":
    sys.exit(main())
