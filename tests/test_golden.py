"""Golden-output regression test.

For each pinned date in tests/golden/, re-run capture() against the
CURRENT codebase and assert byte-identical output. Any divergence
means the refactor changed task generation for some date.

These tests bypass the autouse path-isolation fixture in conftest.py
because they intentionally read the real config.yaml + state.yaml +
task_templates/ — they're testing the live engine output, not a
sandboxed run().
"""

from __future__ import annotations

import json
from datetime import date
from pathlib import Path

import pytest

from tests.golden.capture import capture

GOLDEN_DIR = Path(__file__).parent / "golden"

# Discover every pinned date by listing the golden directory.
GOLDEN_DATES = sorted(
    p.stem for p in GOLDEN_DIR.glob("*.json") if p.stem != "__init__"
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
