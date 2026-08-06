import json
from pathlib import Path


def _write_data(root: Path, xp: dict | None):
    d = root / "docs" / "assets"
    d.mkdir(parents=True)
    payload = {"syllabuses": {}, "priority_order": []}
    if xp is not None:
        payload["xp"] = xp
    (d / "data.json").write_text(json.dumps(payload))


def test_build_xp_lines_breakdown_and_ladder(tmp_path):
    from src.lw.xp_view import build_xp_lines

    _write_data(tmp_path, {
        "total": 340, "level": 2, "level_progress": 76, "next_level_at": 466,
        "by_source": {"daily": 40, "rungs": 300, "deep_block": 0},
        "unlocked": [{"level": 2, "reward": "movie"}], "next_reward": {"level": 4, "reward": "lens"},
    })
    (tmp_path / "xp.yaml").write_text(
        "rewards:\n  - level: 2\n    reward: movie\n  - level: 4\n    reward: lens\n"
    )
    text = "\n".join(build_xp_lines(tmp_path))
    assert "rungs" in text and "daily" in text and "deep_block" not in text
    assert "Level 2" in text
    assert "🔓" in text and "🔒" in text and "lens" in text


def test_build_xp_lines_without_data(tmp_path):
    from src.lw.xp_view import build_xp_lines

    assert "No XP data yet" in build_xp_lines(tmp_path)[0]
