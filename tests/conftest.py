"""Shared test fixtures.

Phase E added a dashboard render hook inside main.run(). Pre-Phase-E
tests that exercise the full run() do not care about the dashboard;
without isolation they would each spin up a real TodoistCompletionClient
and burn 7+ seconds in retry/backoff against an unmocked HTTP call.

This autouse fixture replaces TodoistCompletionClient module-wide with
a stub that returns an empty completion set instantly. Tests that DO
care about dashboard behavior (test_dashboard.py) call render() directly
and don't go through main, so they're unaffected.

The second autouse fixture redirects the module-level path constants
that run() falls back to when a test doesn't pass explicit overrides.
Without it, any test that calls run() without `docs_*_path` /
`reflections_root` / `completion_cache_path` writes to the real repo
paths — overwriting docs/index.html, mutating reflections/, etc.
"""

from __future__ import annotations

import os
from pathlib import Path

import pytest


@pytest.fixture(autouse=True, scope="session")
def _ensure_todoist_token_for_tests():
    """CI environments don't have a real TODOIST_TOKEN, but several tests
    exercise `load_config()` which raises if the token is missing. Set a
    placeholder so those tests can proceed without hitting the network
    (the token is never USED — only required to be non-empty).
    """
    if not os.environ.get("TODOIST_TOKEN"):
        os.environ["TODOIST_TOKEN"] = "test-placeholder-token"
    yield


class _FakeCompletionClient:
    def __init__(self, *args, **kwargs):
        pass

    def get_completion_status(self, task_ids):
        return {tid: False for tid in task_ids}


@pytest.fixture(autouse=True)
def _stub_completion_client(monkeypatch):
    monkeypatch.setattr(
        "src.main.TodoistCompletionClient", _FakeCompletionClient
    )


@pytest.fixture(autouse=True)
def _isolate_engine_paths(monkeypatch, tmp_path_factory):
    """Redirect src.main's path constants into a per-test tmp dir.

    Tests that pass explicit overrides to run() are unaffected (kwargs
    take precedence inside run()). This is the safety net for tests
    that don't pass overrides.
    """
    root = tmp_path_factory.mktemp("engine-iso")
    reflections = root / "reflections"
    rtpl = root / "reflection_templates"
    reflections.mkdir()
    rtpl.mkdir()
    monkeypatch.setattr("src.main.REFLECTIONS_DIR", reflections)
    monkeypatch.setattr("src.main.REFLECTION_TEMPLATES_DIR", rtpl)
    monkeypatch.setattr(
        "src.main.COMPLETION_CACHE_PATH", root / ".completion_cache.json"
    )
    monkeypatch.setattr("src.main.DOCS_HTML_PATH", root / "docs" / "index.html")
    monkeypatch.setattr(
        "src.main.DOCS_DATA_PATH", root / "docs" / "assets" / "data.json"
    )
    monkeypatch.setattr(
        "src.main.DOCS_CSS_PATH", root / "docs" / "assets" / "style.css"
    )
