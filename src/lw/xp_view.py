"""`lw xp` — XP breakdown and reward ladder. Plain print, no TUI."""
from __future__ import annotations

import json
from pathlib import Path

from src.xp import load_xp_config


def build_xp_lines(repo_root: Path) -> list[str]:
    data_path = repo_root / "docs" / "assets" / "data.json"
    xp = None
    if data_path.exists():
        try:
            data = json.loads(data_path.read_text(encoding="utf-8"))
        except (ValueError, OSError):
            data = None
        if data is not None:
            xp = data.get("xp")

    if not xp:
        return ["No XP data yet — runs after the next engine run."]

    lines: list[str] = []
    by_source = xp.get("by_source") or {}
    for source, value in sorted(by_source.items(), key=lambda kv: kv[1], reverse=True):
        if value:
            lines.append(f"  {source}: {value}")

    to_next = xp["next_level_at"] - xp["total"]
    lines.append(f"XP {xp['total']} · Level {xp['level']} · {to_next} to Level {xp['level'] + 1}")

    cfg = load_xp_config(repo_root / "xp.yaml")
    if not cfg.rewards:
        lines.append("No rewards configured — edit xp.yaml")
    else:
        level = xp["level"]
        for reward in sorted(cfg.rewards, key=lambda r: r.level):
            icon = "🔓" if reward.level <= level else "🔒"
            lines.append(f"  {icon} Level {reward.level}: {reward.reward}")

    return lines
