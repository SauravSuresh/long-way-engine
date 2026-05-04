"""Tests for scripts/render_dashboard.py — synthetic-completion debug tool."""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
SCRIPT_PATH = REPO_ROOT / "scripts" / "render_dashboard.py"


@pytest.fixture(scope="module")
def render_dashboard_mod():
    spec = importlib.util.spec_from_file_location("render_dashboard", SCRIPT_PATH)
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    sys.modules["render_dashboard"] = mod
    spec.loader.exec_module(mod)
    return mod


def test_inject_banner_prepends_inside_body(render_dashboard_mod):
    html = "<!doctype html><html><head></head><body><main></main></body></html>"
    out = render_dashboard_mod.inject_banner(html)
    assert render_dashboard_mod.BANNER_HTML in out
    body_idx = out.index("<body>") + len("<body>")
    main_idx = out.index("<main>")
    banner_idx = out.index(render_dashboard_mod.BANNER_HTML)
    assert body_idx <= banner_idx < main_idx


def test_inject_banner_raises_when_body_missing(render_dashboard_mod):
    with pytest.raises(RuntimeError, match="missing <body>"):
        render_dashboard_mod.inject_banner("<!doctype html><html></html>")


def test_synthetic_completion_skips_dry_run_ids(render_dashboard_mod):
    cache = {
        "ext1": {"todoist_task_id": "T1"},
        "ext2": {"todoist_task_id": "DRY-RUN-foo"},
        "ext3": {"todoist_task_id": "T3"},
        "ext4": {},  # no task_id
    }
    out = render_dashboard_mod.synthetic_completion_set(cache)
    assert out == {"T1", "T3"}


def test_main_refuses_out_under_docs(render_dashboard_mod, tmp_path: Path, capsys):
    docs_target = REPO_ROOT / "docs" / "index.html"
    rc = render_dashboard_mod.main(["--out", str(docs_target)])
    err = capsys.readouterr().err
    assert rc == 2
    assert "owned by the daily workflow" in err


def test_main_writes_html_with_banner(
    render_dashboard_mod, tmp_path: Path, capsys, monkeypatch
):
    """End-to-end: run main(), load output, banner appears at the top."""
    # CI doesn't carry .env, and load_config() refuses to load without a
    # token. The harness never USES the token (no API calls), but the
    # config loader is shared with the engine and validates token presence.
    # Provide a stub so the test runs identically locally and in CI.
    monkeypatch.setenv("TODOIST_TOKEN", "test-token-not-used")
    out = tmp_path / "render.html"
    rc = render_dashboard_mod.main(
        ["--today", "2026-05-04", "--out", str(out)]
    )
    assert rc == 0, capsys.readouterr()
    assert out.exists()
    text = out.read_text(encoding="utf-8")
    assert "SYNTHETIC RENDER" in text
    assert text.startswith("<!doctype html>")
    # Banner must be inside the body, before any main content.
    assert text.index("synthetic-banner") < text.index('class="dashboard"')
    captured = capsys.readouterr()
    assert "SYNTHETIC RENDER" in captured.out
