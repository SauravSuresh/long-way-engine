"""End-to-end smoke for src.main.run with a fake Todoist client."""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import date, datetime, timezone
from pathlib import Path

from src.config import Config, DashboardConfig, TodoistConfig
from src.main import SweepResult, append_log, run, sweep_past_due
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
    def __init__(
        self,
        *,
        token: str,
        project_id: str,
        clock=None,
        dry_run: bool = False,
    ) -> None:
        self.token = token
        self.project_id = project_id
        self.clock = clock
        self.dry_run = dry_run
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


def _isolated_paths(tmp_path: Path) -> dict:
    """All run() kwargs needed to keep filesystem effects inside tmp_path.

    Tests that don't pass these end up writing the engine's real docs/,
    .completion_cache.json, and mutating reflections/ via update_metadata.
    """
    refl_root = tmp_path / "reflections"
    refl_templates = tmp_path / "rtpl"
    refl_root.mkdir(parents=True, exist_ok=True)
    refl_templates.mkdir(parents=True, exist_ok=True)
    return {
        "reflections_root": refl_root,
        "reflection_templates_root": refl_templates,
        "completion_cache_path": tmp_path / ".completion_cache.json",
        "docs_html_path": tmp_path / "docs" / "index.html",
        "docs_data_path": tmp_path / "docs" / "assets" / "data.json",
        "docs_css_path": tmp_path / "docs" / "assets" / "style.css",
    }


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
        **_isolated_paths(tmp_path),
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
    paths = _isolated_paths(tmp_path)

    first = run(make_config(), make_state(), monday, tdir, cache_path, FakeClient, **paths)
    assert len(first.created) == 2

    second = run(make_config(), make_state(), monday, tdir, cache_path, FakeClient, **paths)
    assert len(second.created) == 0
    assert len(second.skipped) == 2
    assert second.errors == 0


def test_run_sunday_creates_zero(tmp_path: Path):
    tdir = _seed_templates(tmp_path)
    cache_path = tmp_path / ".task_cache.json"
    sunday = date(2026, 5, 3)
    summary = run(
        make_config(), make_state(), sunday, tdir, cache_path, FakeClient,
        **_isolated_paths(tmp_path),
    )
    assert len(summary.created) == 0
    assert len(summary.skipped) == 0
    assert summary.errors == 0


def test_append_log_creates_and_appends(tmp_path: Path):
    log = tmp_path / "LOG.md"
    paths_a = _isolated_paths(tmp_path / "a")
    summary_a = run(
        make_config(),
        make_state(),
        date(2026, 5, 4),
        _seed_templates(tmp_path / "a"),
        tmp_path / "a.json",
        FakeClient,
        **paths_a,
    )
    append_log(log, summary_a, "Asia/Kolkata")
    contents_a = log.read_text()
    assert "# Long Way Engine" in contents_a
    assert "2026-05-04" in contents_a
    assert "Created: 2" in contents_a

    paths_b = _isolated_paths(tmp_path / "b")
    summary_b = run(
        make_config(),
        make_state(),
        date(2026, 5, 5),
        _seed_templates(tmp_path / "b"),
        tmp_path / "b.json",
        FakeClient,
        **paths_b,
    )
    append_log(log, summary_b, "Asia/Kolkata")
    contents_b = log.read_text()
    assert "2026-05-05" in contents_b
    assert "2026-05-04" in contents_b  # earlier entry preserved


# --- Phase E: dashboard wiring -----------------------------------------------


def test_dashboard_renders_in_real_run(tmp_path: Path):
    tdir = _seed_templates(tmp_path)
    cache_path = tmp_path / ".task_cache.json"
    docs_html = tmp_path / "docs" / "index.html"
    docs_data = tmp_path / "docs" / "assets" / "data.json"
    docs_css = tmp_path / "docs" / "assets" / "style.css"
    refl_root = tmp_path / "reflections"
    refl_templates = tmp_path / "rtpl"
    refl_root.mkdir(); refl_templates.mkdir()

    summary = run(
        make_config(),
        make_state(),
        date(2026, 5, 4),
        tdir,
        cache_path,
        client_factory=FakeClient,
        reflections_root=refl_root,
        reflection_templates_root=refl_templates,
        completion_cache_path=tmp_path / ".completion_cache.json",
        docs_html_path=docs_html,
        docs_data_path=docs_data,
        docs_css_path=docs_css,
    )
    assert summary.dashboard_status == "ok"
    assert docs_html.exists()
    assert docs_data.exists()
    assert docs_css.exists()
    data = json.loads(docs_data.read_text())
    assert data["today"] == "2026-05-04"


def test_dashboard_skipped_when_flag_set(tmp_path: Path):
    tdir = _seed_templates(tmp_path)
    cache_path = tmp_path / ".task_cache.json"
    docs_html = tmp_path / "docs" / "index.html"
    refl_root = tmp_path / "reflections"
    refl_templates = tmp_path / "rtpl"
    refl_root.mkdir(); refl_templates.mkdir()

    summary = run(
        make_config(),
        make_state(),
        date(2026, 5, 4),
        tdir,
        cache_path,
        client_factory=FakeClient,
        reflections_root=refl_root,
        reflection_templates_root=refl_templates,
        skip_dashboard=True,
        docs_html_path=docs_html,
    )
    assert summary.dashboard_status == "skipped"
    assert not docs_html.exists()


def test_dashboard_none_in_dry_run(tmp_path: Path):
    tdir = _seed_templates(tmp_path)
    summary = run(
        make_config(),
        make_state(),
        date(2026, 5, 4),
        tdir,
        tmp_path / ".task_cache.json",
        client_factory=FakeClient,
        reflections_root=tmp_path / "reflections",
        reflection_templates_root=tmp_path / "rtpl",
        dry_run=True,
    )
    assert summary.dashboard_status is None


def test_dashboard_render_failure_logs_error_does_not_fail_run(tmp_path: Path, caplog):
    tdir = _seed_templates(tmp_path)
    refl_root = tmp_path / "reflections"
    refl_templates = tmp_path / "rtpl"
    refl_root.mkdir(); refl_templates.mkdir()

    class BoomClient:
        def __init__(self, **kwargs): pass
        def get_completion_status(self, task_ids):
            raise RuntimeError("network exploded")

    with caplog.at_level("WARNING"):
        summary = run(
            make_config(),
            make_state(),
            date(2026, 5, 4),
            tdir,
            tmp_path / ".task_cache.json",
            client_factory=FakeClient,
            reflections_root=refl_root,
            reflection_templates_root=refl_templates,
            completion_factory=BoomClient,
            docs_html_path=tmp_path / "docs" / "index.html",
            docs_data_path=tmp_path / "docs" / "assets" / "data.json",
            docs_css_path=tmp_path / "docs" / "assets" / "style.css",
        )
    assert summary.dashboard_status == "error"
    assert summary.errors == 0  # render failure doesn't add to engine errors
    assert any("dashboard render failed" in r.getMessage().lower() for r in caplog.records)


def test_dashboard_status_in_log_line(tmp_path: Path):
    tdir = _seed_templates(tmp_path)
    summary = run(
        make_config(),
        make_state(),
        date(2026, 5, 4),
        tdir,
        tmp_path / ".task_cache.json",
        client_factory=FakeClient,
        skip_dashboard=True,
        **_isolated_paths(tmp_path),
    )
    log = tmp_path / "LOG.md"
    append_log(log, summary, "Asia/Kolkata")
    assert "Dashboard: skipped" in log.read_text()


def test_dashboard_renders_when_paused(tmp_path: Path):
    """Per Phase A failure-modes: pause should NOT freeze the dashboard."""
    tdir = _seed_templates(tmp_path)
    refl_root = tmp_path / "reflections"
    refl_templates = tmp_path / "rtpl"
    refl_root.mkdir(); refl_templates.mkdir()
    paused_state = State(
        start_date=date(2026, 5, 4),
        timezone=ZoneInfo("Asia/Kolkata"),
        phase=1, month=1, current_module=1, current_book="CSAPP",
        paused=True, paused_since=date(2026, 5, 4),
    )
    summary = run(
        make_config(),
        paused_state,
        date(2026, 5, 4),
        tdir,
        tmp_path / ".task_cache.json",
        client_factory=FakeClient,
        reflections_root=refl_root,
        reflection_templates_root=refl_templates,
        completion_cache_path=tmp_path / ".completion_cache.json",
        docs_html_path=tmp_path / "docs" / "index.html",
        docs_data_path=tmp_path / "docs" / "assets" / "data.json",
        docs_css_path=tmp_path / "docs" / "assets" / "style.css",
    )
    assert summary.dashboard_status == "ok"


# --- Sweep tests --------------------------------------------------------------


class _FakeAdmin:
    def __init__(self, *, token: str, **_):
        self.token = token
        self.deleted: list[str] = []
        self.fail_on: set[str] = set()
        self.notfound_on: set[str] = set()

    def delete_task(self, task_id: str) -> None:
        if task_id in self.notfound_on:
            raise RuntimeError("todoist DELETE /tasks/X 404: not found")
        if task_id in self.fail_on:
            raise RuntimeError("todoist DELETE /tasks/X 500: oops")
        self.deleted.append(task_id)


class _FakeCompletion:
    def __init__(self, completed: set[str] | None = None, *, raises: bool = False):
        self.completed = completed or set()
        self.raises = raises
        self.queried: list[list[str]] = []

    def __call__(self, **_):
        return self

    def get_completion_status(self, task_ids):
        self.queried.append(list(task_ids))
        if self.raises:
            raise RuntimeError("network down")
        return {tid: tid in self.completed for tid in task_ids}


def _cache_entry(task_id, due, template_id="weekly-read-real-code", **extra):
    return {
        "todoist_task_id": task_id,
        "created_at": "2026-05-01T00:00:00+00:00",
        "template_id": template_id,
        "due_date": due,
        **extra,
    }


def test_sweep_marks_missed_and_deletes_uncompleted_past_due():
    today = date(2026, 5, 4)
    cache = {
        "wrr-2026-04-25": _cache_entry("100", "2026-04-25"),
        "wrr-2026-05-02": _cache_entry("101", "2026-05-02"),
    }
    admin = _FakeAdmin(token="t")
    comp = _FakeCompletion(completed=set())
    result = sweep_past_due(
        cache, today=today,
        completion_client=comp, admin_client=admin, dry_run=False,
    )
    assert result.checked == 2
    assert result.missed_marked == 2
    assert result.deleted == 2
    assert result.completed_marked == 0
    assert set(admin.deleted) == {"100", "101"}
    for ext in cache:
        assert cache[ext]["status"] == "missed"
        assert cache[ext]["missed_at"] == "2026-05-04"


def test_sweep_marks_completed_when_completion_set_has_it():
    today = date(2026, 5, 4)
    cache = {"wrr-2026-04-25": _cache_entry("100", "2026-04-25")}
    admin = _FakeAdmin(token="t")
    comp = _FakeCompletion(completed={"100"})
    result = sweep_past_due(
        cache, today=today,
        completion_client=comp, admin_client=admin, dry_run=False,
    )
    assert result.completed_marked == 1
    assert result.missed_marked == 0
    assert result.deleted == 0  # completed tasks are NOT deleted from Todoist
    assert admin.deleted == []
    assert cache["wrr-2026-04-25"]["status"] == "completed"
    assert cache["wrr-2026-04-25"]["completed_at"] == "2026-05-04"


def test_sweep_skips_todays_and_future():
    today = date(2026, 5, 4)
    cache = {
        "today":   _cache_entry("200", "2026-05-04"),
        "future":  _cache_entry("201", "2026-05-10"),
    }
    admin = _FakeAdmin(token="t")
    comp = _FakeCompletion(completed=set())
    result = sweep_past_due(
        cache, today=today,
        completion_client=comp, admin_client=admin, dry_run=False,
    )
    assert result.checked == 0
    assert admin.deleted == []
    assert "status" not in cache["today"]
    assert "status" not in cache["future"]


def test_sweep_skips_already_marked_entries():
    today = date(2026, 5, 4)
    cache = {
        "old-missed":   _cache_entry("300", "2026-04-01", status="missed"),
        "old-complete": _cache_entry("301", "2026-04-02", status="completed"),
    }
    admin = _FakeAdmin(token="t")
    comp = _FakeCompletion(completed=set())
    result = sweep_past_due(
        cache, today=today,
        completion_client=comp, admin_client=admin, dry_run=False,
    )
    assert result.checked == 0
    assert comp.queried == []  # never even called


def test_sweep_skips_module_due_and_dry_run_task_ids():
    today = date(2026, 5, 4)
    cache = {
        "module": _cache_entry("400", "module:3"),
        "dryrun": _cache_entry("DRY-RUN-xyz", "2026-04-25"),
    }
    admin = _FakeAdmin(token="t")
    comp = _FakeCompletion(completed=set())
    result = sweep_past_due(
        cache, today=today,
        completion_client=comp, admin_client=admin, dry_run=False,
    )
    assert result.checked == 0


def test_sweep_dry_run_makes_no_changes():
    today = date(2026, 5, 4)
    cache = {"wrr-2026-04-25": _cache_entry("100", "2026-04-25")}
    admin = _FakeAdmin(token="t")
    comp = _FakeCompletion(completed=set())
    result = sweep_past_due(
        cache, today=today,
        completion_client=comp, admin_client=admin, dry_run=True,
    )
    assert result.checked == 1
    assert result.skipped == 1
    assert result.missed_marked == 0
    assert result.deleted == 0
    assert admin.deleted == []
    assert "status" not in cache["wrr-2026-04-25"]


def test_sweep_completion_lookup_failure_aborts_sweep():
    today = date(2026, 5, 4)
    cache = {"wrr-2026-04-25": _cache_entry("100", "2026-04-25")}
    admin = _FakeAdmin(token="t")
    comp = _FakeCompletion(raises=True)
    result = sweep_past_due(
        cache, today=today,
        completion_client=comp, admin_client=admin, dry_run=False,
    )
    assert result.errors == 1
    assert admin.deleted == []
    assert "status" not in cache["wrr-2026-04-25"]


def test_sweep_delete_404_still_marks_missed():
    today = date(2026, 5, 4)
    cache = {"wrr-2026-04-25": _cache_entry("100", "2026-04-25")}
    admin = _FakeAdmin(token="t")
    admin.notfound_on = {"100"}
    comp = _FakeCompletion(completed=set())
    result = sweep_past_due(
        cache, today=today,
        completion_client=comp, admin_client=admin, dry_run=False,
    )
    # Task already gone — record the miss anyway.
    assert result.missed_marked == 1
    assert result.deleted == 0
    assert cache["wrr-2026-04-25"]["status"] == "missed"


def test_sweep_delete_other_error_leaves_cache_for_retry():
    today = date(2026, 5, 4)
    cache = {"wrr-2026-04-25": _cache_entry("100", "2026-04-25")}
    admin = _FakeAdmin(token="t")
    admin.fail_on = {"100"}
    comp = _FakeCompletion(completed=set())
    result = sweep_past_due(
        cache, today=today,
        completion_client=comp, admin_client=admin, dry_run=False,
    )
    assert result.errors == 1
    assert result.missed_marked == 0
    assert "status" not in cache["wrr-2026-04-25"]


def test_run_with_sweep_disabled_skips_sweep_pass(tmp_path: Path):
    tdir = _seed_templates(tmp_path)
    cache_path = tmp_path / ".task_cache.json"
    # Seed a past-due cache entry; if sweep ran, it would mutate the cache.
    cache_path.write_text(json.dumps({
        "stale": _cache_entry("999", "2026-04-25"),
    }))
    refl = tmp_path / "reflections"; refl.mkdir()
    rtpl = tmp_path / "rtpl"; rtpl.mkdir()
    summary = run(
        make_config(), make_state(), date(2026, 5, 4), tdir, cache_path,
        client_factory=FakeClient,
        reflections_root=refl, reflection_templates_root=rtpl,
        completion_cache_path=tmp_path / ".completion_cache.json",
        docs_html_path=tmp_path / "docs" / "index.html",
        docs_data_path=tmp_path / "docs" / "assets" / "data.json",
        docs_css_path=tmp_path / "docs" / "assets" / "style.css",
        sweep=False,
    )
    cache = json.loads(cache_path.read_text())
    assert "status" not in cache["stale"]
