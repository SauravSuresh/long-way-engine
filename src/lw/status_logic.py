"""Read-only status over engine state. No Todoist, no network."""
from __future__ import annotations

import json
from dataclasses import dataclass, replace
from datetime import date
from pathlib import Path
from typing import Any

import yaml

from src.config import Config, TodoistConfig, load_multi_syllabus_config
from src.scheduler import should_create_today
from src.state import load_shared_state, load_syllabus_state
from src.syllabus import current_module_name, load_syllabus_for_entry
from src.templates import MissingVariable, load_templates, resolve_string


@dataclass
class CurriculumCtx:
    entry: Any
    state: Any
    syllabus: Any
    templates: list


@dataclass
class EngineCtx:
    cfg: Any
    shared: Any
    per_key: dict[str, CurriculumCtx]
    repo_root: Path


def load_engine(repo_root: Path) -> EngineCtx:
    cfg = load_multi_syllabus_config(repo_root / "config.yaml", repo_root / ".env", strict=False)
    shared = load_shared_state(repo_root / "state" / "shared.yaml")
    per_key: dict[str, CurriculumCtx] = {}
    for key in cfg.priority_order:
        entry = cfg.syllabuses[key]
        if not entry.enabled:
            continue
        # entry.path is relative (from config.yaml); resolve against repo_root
        # so `lw` works when invoked from any cwd.
        entry = replace(entry, path=repo_root / entry.path)
        state = load_syllabus_state(repo_root / entry.state_file)
        syllabus = load_syllabus_for_entry(entry)
        templates = load_templates([entry.path / "rituals", entry.path / "modules.yaml"])
        per_key[key] = CurriculumCtx(entry, state, syllabus, templates)
    return EngineCtx(cfg, shared, per_key, repo_root)


def current_rung_meta(repo_root: Path, module_number: int) -> dict | None:
    """The picked challenge's meta.yaml for this rung, or None if not picked."""
    for d in sorted((repo_root / "ladder").glob(f"rung-{module_number:02d}[abc]-*")):
        meta_path = d / "meta.yaml"
        if meta_path.exists():
            return yaml.safe_load(meta_path.read_text(encoding="utf-8"))
    return None


def effective_deadline(meta: dict) -> str:
    exts = meta.get("extensions") or []
    return exts[-1]["new_deadline"] if exts else str(meta.get("deadline", ""))


def build_status(repo_root: Path, today: date) -> list[str]:
    ctx = load_engine(repo_root)
    lines: list[str] = []
    for key, cur in ctx.per_key.items():
        lines.append(f"## {key}")
        mod_no = cur.state.current_module
        lines.append(f"  module {mod_no}: {current_module_name(mod_no, cur.syllabus)}")
        meta = current_rung_meta(repo_root, mod_no)
        if meta:
            lines.append(_deadline_line(meta, today))
        elif _has_rungs(cur.templates):
            lines.append("  Rung not picked yet — run `lw rung start`")
        lines.extend(_due_today_lines(ctx, key, cur, today))
        lines.extend(_streak_lines(repo_root, key))
        lines.append("")
    return lines


def _deadline_line(meta: dict, today: date) -> str:
    """meta lacking a deadline (empty string, no extensions) renders without
    the countdown instead of crashing {days:+d} on days=None."""
    dl = effective_deadline(meta)
    days = (date.fromisoformat(dl) - today).days if dl else None
    ext = len(meta.get("extensions") or [])
    countdown = f" ({days:+d}d)" if days is not None else ""
    return (
        f"  Rung {meta['rung']} option {meta['option']} — deadline {dl}"
        f"{countdown}{' · %d extension(s)' % ext if ext else ''}"
    )


def _cfg_shim(ctx: EngineCtx, key: str) -> Config:
    """Per-syllabus Config shim for should_create_today/resolve_string,
    mirroring src/main.py's per_syllabus_cfg_shim (and reflect_logic._cfg_shim)."""
    entry = ctx.per_key[key].entry
    return Config(
        todoist=TodoistConfig(project_id=entry.todoist_project_id, labels={}),
        ritual_times=entry.ritual_times,
        sunday_off=ctx.cfg.sunday_off,
        pair_day=ctx.cfg.pair_day,
        dashboard=ctx.cfg.dashboard,
        todoist_token=ctx.cfg.todoist_token,
        curriculum_dir=entry.path,
    )


def _due_today_lines(ctx: EngineCtx, key: str, cur: CurriculumCtx, today: date) -> list[str]:
    """'due today' titles for this curriculum's templates that fire today,
    per scheduler.should_create_today. Read-only: no state writes, no
    Todoist. Titles are resolve_string'd where cheap; unresolvable
    placeholders fall back to the raw title rather than dropping the item."""
    cfg_shim = _cfg_shim(ctx, key)
    titles: list[str] = []
    for tpl in cur.templates:
        try:
            if not should_create_today(tpl, today, cur.state, cfg_shim):
                continue
        except NotImplementedError:
            continue
        try:
            titles.append(resolve_string(tpl.title, cur.state, cfg_shim, today, syllabus=cur.syllabus))
        except MissingVariable:
            titles.append(tpl.title)
    if not titles:
        return []
    return ["  due today: " + ", ".join(titles)]


def _has_rungs(templates: list) -> bool:
    return any(t.cadence == "once-per-module" and t.deadline_days for t in templates)


def _streak_lines(repo_root: Path, key: str) -> list[str]:
    data_path = repo_root / "docs" / "assets" / "data.json"
    if not data_path.exists():
        return []
    try:
        data = json.loads(data_path.read_text(encoding="utf-8"))
    except (ValueError, OSError):
        return []
    syl = (data.get("syllabuses") or {}).get(key) or {}
    streaks = syl.get("streaks") or {}
    if not streaks:
        return []
    gen = data.get("generated_at", "")
    stamp = f" (as of {gen[:10]})" if gen else ""
    return ["  streaks" + stamp + ": " + ", ".join(f"{k}={v}" for k, v in streaks.items())]
