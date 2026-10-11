"""The planner's JS forecast must match the Python one on every golden fixture."""

from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path

import pytest
import yaml

ROOT = Path(__file__).resolve().parent.parent
GOLDEN = ROOT / "tests" / "golden" / "seasons"
RUNNER = ROOT / "tests" / "forecast_runner.mjs"

node = shutil.which("node")


def _jsonable(x):
    if isinstance(x, dict):
        return {str(k): _jsonable(v) for k, v in x.items()}
    if isinstance(x, list):
        return [_jsonable(v) for v in x]
    return json.loads(json.dumps(x, default=str))


@pytest.mark.skipif(node is None, reason="node not installed")
@pytest.mark.parametrize("path", sorted(GOLDEN.glob("*.yaml")), ids=lambda p: p.stem)
def test_js_matches_golden(path: Path):
    raw = yaml.safe_load(path.read_text())
    payload = json.dumps({"seasons": _jsonable(raw["seasons"]), "state": _jsonable(raw.get("state") or {}), "today": str(raw["today"])})
    out = subprocess.run([node, str(RUNNER)], input=payload, capture_output=True, text=True, check=True)
    assert json.loads(out.stdout) == _jsonable(raw["expected"])
