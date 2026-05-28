"""Golden-output regression test.

For each pinned date in tests/golden/, re-run capture() against the
CURRENT codebase and assert byte-identical output. Any divergence
means the refactor changed task generation for some date.

These tests bypass the autouse path-isolation fixture in conftest.py
because they intentionally read the real config.yaml + state/*.yaml +
curricula/ — they're testing the live engine output, not a sandboxed run().

The multi-syllabus fixture tests (test_multi_syllabus_*) use a fully
synthetic workspace built in tmp_path and compare against pinned snapshots
in tests/golden/multi-syllabus-*.json.
"""

from __future__ import annotations

import json
import tempfile
from datetime import date
from pathlib import Path

import pytest

from tests.golden.capture import build_multi_syllabus_scenario, capture

GOLDEN_DIR = Path(__file__).parent / "golden"

# Discover only date-shaped fixtures (YYYY-MM-DD stems). Multi-syllabus
# fixtures have longer stems and are handled by their own tests below.
GOLDEN_DATES = sorted(
    p.stem
    for p in GOLDEN_DIR.glob("*.json")
    if p.stem != "__init__" and len(p.stem.split("-")) == 3
)


@pytest.mark.parametrize("iso_date", GOLDEN_DATES)
def test_golden_matches(iso_date: str) -> None:
    """The capture for `iso_date` must match the pinned JSON byte-for-byte."""
    y, m, d = (int(x) for x in iso_date.split("-"))
    actual = capture(date(y, m, d))
    expected = json.loads((GOLDEN_DIR / f"{iso_date}.json").read_text())
    assert actual == expected, (
        f"Golden mismatch for {iso_date}. "
        f"Re-run tests/golden/capture.py to inspect diff."
    )


def test_every_golden_template_has_syllabus_key() -> None:
    """Guard against future drift: every template entry in every golden fixture
    must carry a non-empty syllabus_key."""
    for iso in GOLDEN_DATES:
        expected = json.loads((GOLDEN_DIR / f"{iso}.json").read_text())
        for entry in expected["templates"]:
            assert entry.get("syllabus_key"), (
                f"golden fixture {iso} has template {entry.get('id')} without syllabus_key"
            )


def test_multi_syllabus_clean_snapshot(tmp_path: Path) -> None:
    """Two syllabuses with non-overlapping clock times; both fire their morning_reading."""
    config_path, env_path = build_multi_syllabus_scenario(tmp_path, "clean")
    actual = capture(date(2026, 6, 1), config_path=config_path, env_path=env_path)
    expected = json.loads(
        (GOLDEN_DIR / "multi-syllabus-clean-2026-06-01.json").read_text()
    )
    assert actual == expected, (
        "multi-syllabus-clean snapshot mismatch. "
        "Re-run tests/golden/capture.py or the generation script to refresh."
    )


def test_multi_syllabus_overlap_snapshot(tmp_path: Path) -> None:
    """Two syllabuses where one slot collides; suppressed via allow_slot_overlap on beta-way."""
    config_path, env_path = build_multi_syllabus_scenario(tmp_path, "overlap")
    actual = capture(date(2026, 6, 1), config_path=config_path, env_path=env_path)
    expected = json.loads(
        (GOLDEN_DIR / "multi-syllabus-overlap-2026-06-01.json").read_text()
    )
    assert actual == expected, (
        "multi-syllabus-overlap snapshot mismatch. "
        "Re-run tests/golden/capture.py or the generation script to refresh."
    )
