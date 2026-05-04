"""Shared test fixtures.

Phase E added a dashboard render hook inside main.run(). Pre-Phase-E
tests that exercise the full run() do not care about the dashboard;
without isolation they would each spin up a real TodoistCompletionClient
and burn 7+ seconds in retry/backoff against an unmocked HTTP call.

This autouse fixture replaces TodoistCompletionClient module-wide with
a stub that returns an empty completion set instantly. Tests that DO
care about dashboard behavior (test_dashboard.py) call render() directly
and don't go through main, so they're unaffected.
"""

from __future__ import annotations

import pytest


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
