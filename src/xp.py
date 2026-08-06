"""Derived XP — recomputed from history every run, like streaks. No IO writes.

Scores completed cache entries, streak bonuses, filled reflections, ladder
rung outcomes, weekly reviews, and exam gates into a total, then maps the
total onto a level curve with owner-configurable reward unlocks.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, timedelta
from pathlib import Path
from typing import Any

import yaml

from src.reflections import split_frontmatter

DEFAULT_WEIGHTS: dict[str, int] = {
    "daily": 10,
    "weekly_ritual": 25,
    "reflection_filled": 30,
    "weekly_review": 40,
    "deep_block": 40,
    "rung_shipped": 200,
    "rung_zero_extension_bonus": 50,
    "rung_extension_penalty": 25,
    "rung_shipped_floor": 100,
    "rung_failed_moved_on": 50,
    "exam_gate": 300,
    "streak_bonus_per_task": 5,
    "streak_bonus_threshold": 7,
}

DEFAULT_LEVEL_BASE = 100
DEFAULT_LEVEL_GROWTH = 1.4

_REFLECTION_CADENCES = ("weekly", "monthly", "quarterly", "annual")


@dataclass(frozen=True)
class Reward:
    level: int
    reward: str


@dataclass
class XPConfig:
    weights: dict[str, int]
    level_base: int
    level_growth: float
    rewards: list[Reward]


def load_xp_config(path: Path) -> XPConfig:
    """Load xp.yaml, filling any missing keys from built-in defaults."""
    raw: dict[str, Any] = {}
    if path.exists():
        raw = yaml.safe_load(path.read_text(encoding="utf-8")) or {}

    weights = dict(DEFAULT_WEIGHTS)
    weights.update(raw.get("weights") or {})

    rewards = [
        Reward(level=int(r["level"]), reward=str(r["reward"]))
        for r in (raw.get("rewards") or [])
    ]

    return XPConfig(
        weights=weights,
        level_base=int(raw.get("level_base", DEFAULT_LEVEL_BASE)),
        level_growth=float(raw.get("level_growth", DEFAULT_LEVEL_GROWTH)),
        rewards=rewards,
    )


@dataclass
class XPResult:
    total: int
    by_source: dict[str, int]
    level: int
    level_progress: int
    next_level_at: int
    unlocked: list[Reward]
    next_reward: Reward | None


def level_threshold(n: int, cfg: XPConfig) -> int:
    """Cumulative XP required to reach level n. 0 for n <= 0."""
    if n <= 0:
        return 0
    return round(cfg.level_base * n**cfg.level_growth)


def _period_end(stem: str, cadence: str) -> date | None:
    try:
        if cadence == "weekly":
            year_s, week_s = stem.split("-W")
            return date.fromisocalendar(int(year_s), int(week_s), 7)
        if cadence == "monthly":
            year_s, month_s = stem.split("-")
            year, month = int(year_s), int(month_s)
            if month == 12:
                next_month_first = date(year + 1, 1, 1)
            else:
                next_month_first = date(year, month + 1, 1)
            return next_month_first - timedelta(days=1)
        if cadence == "quarterly":
            year_s, q_s = stem.split("-Q")
            year, quarter = int(year_s), int(q_s)
            last_month = quarter * 3
            if last_month == 12:
                next_month_first = date(year + 1, 1, 1)
            else:
                next_month_first = date(year, last_month + 1, 1)
            return next_month_first - timedelta(days=1)
        if cadence == "annual":
            return date(int(stem), 12, 31)
    except (ValueError, IndexError):
        return None
    return None


def _score_cache_walk(syl: dict[str, Any], weights: dict[str, int]) -> dict[str, int]:
    scores = {"daily": 0, "deep_block": 0, "weekly_ritual": 0}
    cache: dict[str, Any] = syl["cache"]
    completion_set: set[str] = syl["completion_set"]
    template_kinds: dict[str, str] = syl["template_kinds"]
    start_date: date = syl["start_date"]

    for entry in cache.values():
        if str(entry.get("todoist_task_id")) not in completion_set:
            continue
        due_date = date.fromisoformat(entry["due_date"])
        if due_date < start_date:
            continue
        if "state_review_action" in entry or "state_review_parent" in entry:
            continue
        kind = template_kinds.get(entry.get("template_id"), "none")
        if kind == "none" or kind not in scores:
            continue
        scores[kind] += weights[kind]
    return scores


def _score_reflections(syl: dict[str, Any], weights: dict[str, int]) -> int:
    reflections_root: Path = syl["reflections_root"]
    start_date: date = syl["start_date"]
    total = 0
    for cadence in _REFLECTION_CADENCES:
        cadence_dir = reflections_root / cadence
        if not cadence_dir.is_dir():
            continue
        for md_path in cadence_dir.glob("*.md"):
            fm, _ = split_frontmatter(md_path.read_text(encoding="utf-8"))
            if fm.get("status") != "filled":
                continue
            end = _period_end(md_path.stem, cadence)
            if end is None or end < start_date:
                continue
            total += weights["reflection_filled"]
    return total


def _score_rungs(ladder_dir: Path, weights: dict[str, int]) -> int:
    total = 0
    for meta_path in sorted(ladder_dir.glob("*/meta.yaml")):
        meta = yaml.safe_load(meta_path.read_text(encoding="utf-8")) or {}
        outcome = meta.get("outcome")
        if outcome == "shipped":
            extensions = meta.get("extensions") or []
            if extensions:
                bonus = -weights["rung_extension_penalty"] * len(extensions)
            else:
                bonus = weights["rung_zero_extension_bonus"]
            total += max(weights["rung_shipped"] + bonus, weights["rung_shipped_floor"])
        elif outcome == "failed":
            total += weights["rung_failed_moved_on"]
    return total


def compute_xp(
    *,
    per_syllabus: dict[str, dict],
    ladder_dir: Path,
    state_log_entries: list[dict],
    exam_gates: int,
    cfg: XPConfig,
) -> XPResult:
    weights = cfg.weights
    by_source = {
        "daily": 0,
        "weekly_ritual": 0,
        "weekly_review": 0,
        "reflections": 0,
        "deep_block": 0,
        "rungs": 0,
        "exam_gates": 0,
        "streak_bonus": 0,
    }

    for syl in per_syllabus.values():
        cache_scores = _score_cache_walk(syl, weights)
        by_source["daily"] += cache_scores["daily"]
        by_source["deep_block"] += cache_scores["deep_block"]
        by_source["weekly_ritual"] += cache_scores["weekly_ritual"]

        daily_streak = syl["daily_streak"]
        if daily_streak >= weights["streak_bonus_threshold"]:
            by_source["streak_bonus"] += weights["streak_bonus_per_task"] * daily_streak

        by_source["reflections"] += _score_reflections(syl, weights)

    by_source["rungs"] = _score_rungs(ladder_dir, weights)

    review_dates = {
        entry["timestamp"]
        for entry in state_log_entries
        if str(entry.get("todoist_task_id", "")).startswith("lw-review-")
    }
    by_source["weekly_review"] = weights["weekly_review"] * len(review_dates)

    by_source["exam_gates"] = weights["exam_gate"] * exam_gates

    total = sum(by_source.values())

    level = 0
    while total >= level_threshold(level + 1, cfg):
        level += 1

    unlocked = sorted((r for r in cfg.rewards if r.level <= level), key=lambda r: r.level)
    locked = sorted((r for r in cfg.rewards if r.level > level), key=lambda r: r.level)
    next_reward = locked[0] if locked else None

    return XPResult(
        total=total,
        by_source=by_source,
        level=level,
        level_progress=total - level_threshold(level, cfg),
        next_level_at=level_threshold(level + 1, cfg),
        unlocked=unlocked,
        next_reward=next_reward,
    )


def to_data_block(result: XPResult) -> dict:
    """JSON-safe dict for data.json."""
    return {
        "total": result.total,
        "level": result.level,
        "level_progress": result.level_progress,
        "next_level_at": result.next_level_at,
        "by_source": dict(result.by_source),
        "unlocked": [{"level": r.level, "reward": r.reward} for r in result.unlocked],
        "next_reward": (
            {"level": result.next_reward.level, "reward": result.next_reward.reward}
            if result.next_reward
            else None
        ),
    }
