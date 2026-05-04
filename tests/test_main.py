"""End-to-end smoke for src.main.run with a fake Todoist client."""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import date, datetime, timezone
from pathlib import Path

from src.config import Config, DashboardConfig, TodoistConfig
from src.main import append_log, run
from src.state import State
from src.templates import ResolvedTemplate
from src.todoist import CreateResult
from tests.test_templates import TPL_YAML
from zoneinfo import ZoneInfo


def make_state() -> State:
    return State(
        start_date=date(2026, 5, 4),
        timezone=ZoneInfo("Asia/Kolkata"),
        phase=1,
        month=1,
        current_module=1,
        current_book="CSAPP",
    )


def make_config() -> Config:
    return Config(
        todoist=TodoistConfig(project_id="p", labels={"daily": "daily-ritual"}),
        ritual_times={"morning_reading": "06:00", "anki": "08:30"},
        sunday_off=True,
        dashboard=DashboardConfig(github_username="u", repo_name="r"),
        todoist_token="tok",
    )


@dataclass
class _FakeRecord:
    template_id: str
    todoist_task_id: str


class FakeClient:
    def __init__(self, *, token: str, project_id: str) -> None:
        self.token = token
        self.project_id = project_id
        self.creates: list[_FakeRecord] = []
        self._next_id = 1000

    def create_task_idempotent(
        self,
        template: ResolvedTemplate,
        due_date: date,
        external_id: str,
        cache: dict,
    ) -> CreateResult:
        if external_id in cache:
            return CreateResult(
                external_id=external_id,
                todoist_task_id=str(cache[external_id]["todoist_task_id"]),
                template_id=template.id,
                due_date=due_date,
                created_at=cache[external_id].get("created_at", ""),
                skipped=True,
            )
        self._next_id += 1
        tid = str(self._next_id)
        self.creates.append(_FakeRecord(template_id=template.id, todoist_task_id=tid))
        return CreateResult(
            external_id=external_id,
            todoist_task_id=tid,
            template_id=template.id,
            due_date=due_date,
            created_at=datetime.now(timezone.utc).isoformat(),
            skipped=False,
        )


def _seed_templates(tmp_path: Path) -> Path:
    tdir = tmp_path / "task_templates"
    tdir.mkdir(parents=True, exist_ok=True)
    (tdir / "daily.yaml").write_text(TPL_YAML)
    return tdir


def test_run_creates_two_tasks_on_monday(tmp_path: Path):
    tdir = _seed_templates(tmp_path)
    cache_path = tmp_path / ".task_cache.json"
    summary = run(
        make_config(),
        make_state(),
        date(2026, 5, 4),  # Monday
        tdir,
        cache_path,
        client_factory=FakeClient,
    )
    assert len(summary.created) == 2
    assert len(summary.skipped) == 0
    assert summary.errors == 0

    cache = json.loads(cache_path.read_text())
    assert len(cache) == 2


def test_run_twice_same_day_creates_zero_on_second(tmp_path: Path):
    tdir = _seed_templates(tmp_path)
    cache_path = tmp_path / ".task_cache.json"
    monday = date(2026, 5, 4)

    first = run(make_config(), make_state(), monday, tdir, cache_path, FakeClient)
    assert len(first.created) == 2

    second = run(make_config(), make_state(), monday, tdir, cache_path, FakeClient)
    assert len(second.created) == 0
    assert len(second.skipped) == 2
    assert second.errors == 0


def test_run_sunday_creates_zero(tmp_path: Path):
    tdir = _seed_templates(tmp_path)
    cache_path = tmp_path / ".task_cache.json"
    sunday = date(2026, 5, 3)
    summary = run(make_config(), make_state(), sunday, tdir, cache_path, FakeClient)
    assert len(summary.created) == 0
    assert len(summary.skipped) == 0
    assert summary.errors == 0


def test_append_log_creates_and_appends(tmp_path: Path):
    log = tmp_path / "LOG.md"
    summary_a = run(
        make_config(),
        make_state(),
        date(2026, 5, 4),
        _seed_templates(tmp_path / "a"),
        tmp_path / "a.json",
        FakeClient,
    )
    append_log(log, summary_a, "Asia/Kolkata")
    contents_a = log.read_text()
    assert "# Long Way Engine" in contents_a
    assert "2026-05-04" in contents_a
    assert "Created: 2" in contents_a

    summary_b = run(
        make_config(),
        make_state(),
        date(2026, 5, 5),
        _seed_templates(tmp_path / "b"),
        tmp_path / "b.json",
        FakeClient,
    )
    append_log(log, summary_b, "Asia/Kolkata")
    contents_b = log.read_text()
    assert "2026-05-05" in contents_b
    assert "2026-05-04" in contents_b  # earlier entry preserved
