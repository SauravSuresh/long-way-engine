"""Each example curriculum must pass the validator with its own ritual_times."""

from __future__ import annotations

from pathlib import Path

import pytest
import yaml

from src.curriculum_validator import validate

EXAMPLES_DIR = Path(__file__).parent.parent / "examples"


@pytest.mark.parametrize(
    "example",
    sorted(p.name for p in EXAMPLES_DIR.iterdir() if p.is_dir()),
)
def test_example_validates(example: str) -> None:
    cdir = EXAMPLES_DIR / example
    manifest = yaml.safe_load((cdir / "manifest.yaml").read_text())
    required = manifest.get("ritual_times_required") or []
    fake_ritual_times = {name: "06:00" for name in required}
    validate(cdir, ritual_times=fake_ritual_times)
