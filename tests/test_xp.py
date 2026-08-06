from datetime import date
from pathlib import Path

import pytest
import yaml


def _cfg(**over):
    from src.xp import XPConfig, load_xp_config

    cfg = load_xp_config(Path("/nonexistent/xp.yaml"))  # defaults
    for k, v in over.items():
        setattr(cfg, k, v)
    return cfg


def _syllabus(tmp_path, *, cache=None, done=None, kinds=None, streak=0, start="2026-08-06"):
    root = tmp_path / "reflections-x"
    root.mkdir(exist_ok=True)
    return {
        "cache": cache or {},
        "completion_set": set(done or []),
        "template_kinds": kinds or {},
        "start_date": date.fromisoformat(start),
        "daily_streak": streak,
        "reflections_root": root,
    }


def _compute(tmp_path, per_syllabus, *, logs=None, gates=0, cfg=None):
    from src.xp import compute_xp

    return compute_xp(
        per_syllabus=per_syllabus,
        ladder_dir=tmp_path / "ladder",
        state_log_entries=logs or [],
        exam_gates=gates,
        cfg=cfg or _cfg(),
    )


def test_defaults_when_config_missing():
    from src.xp import load_xp_config

    cfg = load_xp_config(Path("/nonexistent/xp.yaml"))
    assert cfg.weights["daily"] == 10
    assert cfg.weights["rung_shipped"] == 200
    assert cfg.level_base == 100 and cfg.level_growth == 1.4
    assert cfg.rewards == []  # no file -> no rewards, only weights/curve default


def test_partial_config_fills_missing_keys(tmp_path):
    from src.xp import load_xp_config

    p = tmp_path / "xp.yaml"
    p.write_text(yaml.safe_dump({"weights": {"daily": 99}, "rewards": [{"level": 2, "reward": "movie"}]}))
    cfg = load_xp_config(p)
    assert cfg.weights["daily"] == 99
    assert cfg.weights["deep_block"] == 40  # default preserved
    assert cfg.rewards[0].level == 2


def test_malformed_reward_entry_skipped_valid_kept(tmp_path):
    from src.xp import load_xp_config

    p = tmp_path / "xp.yaml"
    p.write_text(yaml.safe_dump({
        "rewards": [
            {"level": "two", "reward": "bad"},
            {"level": 3, "reward": "good"},
        ]
    }))
    cfg = load_xp_config(p)
    assert len(cfg.rewards) == 1
    assert cfg.rewards[0].level == 3
    assert cfg.rewards[0].reward == "good"


def test_non_int_weight_falls_back_to_default(tmp_path):
    from src.xp import load_xp_config

    p = tmp_path / "xp.yaml"
    p.write_text(yaml.safe_dump({"weights": {"daily": "lots"}}))
    cfg = load_xp_config(p)
    assert cfg.weights["daily"] == 10


def test_invalid_yaml_syntax_falls_back_to_full_defaults(tmp_path):
    from src.xp import load_xp_config

    p = tmp_path / "xp.yaml"
    p.write_text("weights: {daily: 10\n  broken: [1, 2\n")  # unbalanced -> YAMLError
    cfg = load_xp_config(p)
    assert cfg.weights["daily"] == 10
    assert cfg.weights["rung_shipped"] == 200
    assert cfg.level_base == 100 and cfg.level_growth == 1.4
    assert cfg.rewards == []


def test_cache_walk_classifies_and_respects_start_date(tmp_path):
    cache = {
        "e1": {"todoist_task_id": "t1", "template_id": "anki", "due_date": "2026-08-06"},
        "e2": {"todoist_task_id": "t2", "template_id": "sat-block", "due_date": "2026-08-08"},
        "e3": {"todoist_task_id": "t3", "template_id": "anki", "due_date": "2026-08-01"},  # pre-start
        "e4": {"todoist_task_id": "t4", "template_id": "anki", "due_date": "2026-08-06"},  # not completed
        "e5": {"todoist_task_id": "t5", "template_id": "review", "due_date": "2026-08-09",
               "state_review_action": {"type": "advance_module"}},  # guard
    }
    kinds = {"anki": "daily", "sat-block": "deep_block", "review": "weekly_ritual"}
    result = _compute(
        tmp_path,
        {"mb": _syllabus(tmp_path, cache=cache, done=["t1", "t2", "t3", "t5"], kinds=kinds)},
    )
    assert result.by_source["daily"] == 10
    assert result.by_source["deep_block"] == 40
    assert result.by_source["weekly_ritual"] == 0


def test_streak_bonus_only_at_threshold(tmp_path):
    below = _compute(tmp_path, {"mb": _syllabus(tmp_path, streak=6)})
    at = _compute(tmp_path, {"mb": _syllabus(tmp_path, streak=7)})
    assert below.by_source["streak_bonus"] == 0
    assert at.by_source["streak_bonus"] == 35


def test_reflections_filled_after_start_only(tmp_path):
    syl = _syllabus(tmp_path, start="2026-08-06")
    weekly = syl["reflections_root"] / "weekly"
    weekly.mkdir(parents=True)
    (weekly / "2026-W32.md").write_text("---\nstatus: filled\n---\nbody\n")  # week ends 08-09
    (weekly / "2026-W20.md").write_text("---\nstatus: filled\n---\nbody\n")  # pre-start
    (weekly / "2026-W33.md").write_text("---\nstatus: stub\n---\n\n")  # not filled
    result = _compute(tmp_path, {"mb": syl})
    assert result.by_source["reflections"] == 30


def test_rung_scoring_extension_penalty_and_floor(tmp_path):
    ladder = tmp_path / "ladder"

    def rung(name, outcome, n_ext):
        d = ladder / name
        d.mkdir(parents=True)
        (d / "meta.yaml").write_text(yaml.safe_dump({
            "rung": 1, "option": "a", "outcome": outcome,
            "extensions": [{"date": "2026-08-20"}] * n_ext,
        }))

    rung("rung-01a-x", "shipped", 0)   # 200 + 50
    rung("rung-02a-x", "shipped", 2)   # 200 - 50
    rung("rung-03a-x", "shipped", 9)   # floored at 100
    rung("rung-04a-x", "failed", 0)    # 50
    rung("rung-05a-x", None, 0)        # 0
    result = _compute(tmp_path, {"mb": _syllabus(tmp_path)})
    assert result.by_source["rungs"] == 250 + 150 + 100 + 50


def test_weekly_review_counts_distinct_dates(tmp_path):
    logs = [
        {"timestamp": "2026-08-09", "todoist_task_id": "lw-review-2026-08-09-0"},
        {"timestamp": "2026-08-09", "todoist_task_id": "lw-review-2026-08-09-1"},
        {"timestamp": "2026-08-16", "todoist_task_id": "lw-review-2026-08-16-0"},
        {"timestamp": "2026-08-16", "todoist_task_id": "cron-thing"},
    ]
    result = _compute(tmp_path, {"mb": _syllabus(tmp_path)}, logs=logs)
    assert result.by_source["weekly_review"] == 80


def test_levels_and_rewards(tmp_path):
    from src.xp import Reward, level_threshold

    cfg = _cfg()
    cfg.rewards = [Reward(2, "movie"), Reward(4, "lens")]
    assert level_threshold(1, cfg) == 100
    assert level_threshold(2, cfg) == 264
    # 2 gates = 600 XP -> past L2 (264) and L3 (466), short of L4 (696)
    result = _compute(tmp_path, {"mb": _syllabus(tmp_path)}, gates=2, cfg=cfg)
    assert result.total == 600
    assert result.level == 3
    assert result.level_progress == 600 - level_threshold(3, cfg)
    assert result.next_level_at == level_threshold(4, cfg)
    assert [r.reward for r in result.unlocked] == ["movie"]
    assert result.next_reward.reward == "lens"


def test_to_data_block_json_safe(tmp_path):
    import json

    from src.xp import to_data_block

    result = _compute(tmp_path, {"mb": _syllabus(tmp_path)}, gates=1)
    block = to_data_block(result)
    json.dumps(block)  # must not raise
    assert block["total"] == 300 and block["by_source"]["exam_gates"] == 300
    assert block["next_reward"] is None
    assert block["ladder"] == []  # no rewards configured


def test_to_data_block_ladder_marks_unlocked(tmp_path):
    from src.xp import Reward, to_data_block

    cfg = _cfg()
    cfg.rewards = [Reward(1, "dessert"), Reward(9, "spa")]
    result = _compute(tmp_path, {"mb": _syllabus(tmp_path)}, gates=1, cfg=cfg)  # 300 XP -> L2
    block = to_data_block(result)
    assert block["ladder"] == [
        {"level": 1, "reward": "dessert", "unlocked": True},
        {"level": 9, "reward": "spa", "unlocked": False},
    ]
