"""Hand-computed forecast cases + golden fixtures in tests/golden/seasons/.

Regenerate a fixture's `expected:` block with:
    uv run python -m tests.test_forecast tests/golden/seasons/<case>.yaml
"""

from __future__ import annotations

import sys
from datetime import date
from pathlib import Path

import pytest
import yaml

from src.forecast import Forecast, forecast
from src.seasons import MilestoneProgress, SeasonsState, load_seasons, load_seasons_state

GOLDEN = Path(__file__).parent / "golden" / "seasons"

ONE_LANE = """
todoist_project_id: p
rhythm:
  rest_week: true
  deep_blocks:
    monday: {start: "07:30", minutes: 60}
    tuesday: {start: "07:30", minutes: 60}
    wednesday: {start: "07:30", minutes: 60}
    thursday: {start: "07:30", minutes: 60}
    friday: {start: "07:30", minutes: 60}
bucket:
  - {id: a, name: A, area: Work, hours: 5}
  - {id: b, name: B, area: Work, hours: 2}
"""


def _seasons(tmp_path, text):
    p = tmp_path / "seasons.yaml"
    p.write_text(text)
    return load_seasons(p)


def test_one_lane_rest_week_by_hand(tmp_path):
    # Mon 2026-10-12. A = 5h at 60 min/weekday -> ends Fri 10-16.
    # Rest 10-17..10-23. B starts Sat 10-24 (continuous bar), blocks Mon 10-26 + Tue 10-27 -> ends 10-27.
    f = forecast(_seasons(tmp_path, ONE_LANE), SeasonsState(), date(2026, 10, 12))
    assert (f.main, f.side, f.resting) == ("a", None, False)
    a, b = f.milestones["a"], f.milestones["b"]
    assert (a.start, a.end) == (date(2026, 10, 12), date(2026, 10, 16))
    assert f.rests == [(date(2026, 10, 17), date(2026, 10, 23))]
    assert (b.start, b.end) == (date(2026, 10, 24), date(2026, 10, 27))
    assert [s.lane for s in a.segments] == ["main"]
    assert not f.overflow


def test_hours_reached_ends_today_and_pin_start_waits(tmp_path):
    text = ONE_LANE.replace("hours: 2}", "hours: 2, pin_start: 2026-10-28}")
    state = SeasonsState(milestones={"a": MilestoneProgress({date(2026, 10, 9): 300})})
    f = forecast(_seasons(tmp_path, text), state, date(2026, 10, 12))
    a, b = f.milestones["a"], f.milestones["b"]
    assert f.main == "a" and a.hours_reached and a.end == date(2026, 10, 12)
    assert f.rests == [(date(2026, 10, 13), date(2026, 10, 19))]
    # pin says not before Wed 10-28: Wed + Thu blocks -> ends 10-29
    assert (b.start, b.end) == (date(2026, 10, 28), date(2026, 10, 29))


def test_rest_until_from_state_blocks_both_lanes(tmp_path):
    state = SeasonsState(rest_until=date(2026, 10, 14))
    f = forecast(_seasons(tmp_path, ONE_LANE), state, date(2026, 10, 12))
    assert f.resting and f.main == "a"
    assert f.milestones["a"].start == date(2026, 10, 15)


# --- golden fixtures --------------------------------------------------------


def _as_plain(f: Forecast) -> dict:
    iso = lambda d: d.isoformat() if d else None  # noqa: E731
    return {
        "current": {"main": f.main, "side": f.side, "resting": f.resting},
        "milestones": {
            k: {
                "start": iso(v.start),
                "end": iso(v.end),
                "hours_reached": v.hours_reached,
                "segments": [{"lane": s.lane, "from": iso(s.start), "to": iso(s.end)} for s in v.segments],
            }
            for k, v in f.milestones.items()
        },
        "rests": [{"from": iso(a), "to": iso(b)} for a, b in f.rests],
        "overflow": f.overflow,
    }


def _run_fixture(path: Path, tmp_path: Path) -> tuple[dict, dict]:
    raw = yaml.safe_load(path.read_text())
    sp = tmp_path / "seasons.yaml"
    sp.write_text(yaml.safe_dump(raw["seasons"]))
    stp = tmp_path / "state.yaml"
    stp.write_text(yaml.safe_dump(raw.get("state") or {}))
    f = forecast(load_seasons(sp), load_seasons_state(stp), raw["today"])
    return _as_plain(f), raw.get("expected") or {}


@pytest.mark.parametrize("path", sorted(GOLDEN.glob("*.yaml")), ids=lambda p: p.stem)
def test_golden(path: Path, tmp_path: Path):
    actual, expected = _run_fixture(path, tmp_path)
    assert actual == expected


if __name__ == "__main__":  # regenerate expected blocks
    import tempfile

    for arg in sys.argv[1:]:
        p = Path(arg)
        raw = yaml.safe_load(p.read_text())
        with tempfile.TemporaryDirectory() as d:
            actual, _ = _run_fixture(p, Path(d))
        raw["expected"] = actual
        p.write_text(yaml.safe_dump(raw, sort_keys=False, allow_unicode=True))
        print(f"regenerated {p}")
