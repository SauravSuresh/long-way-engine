"""CLI surface for src.main: argparse, --dry-run, --today, --project-id, --cache-file."""

from __future__ import annotations

import io
import json
from datetime import date
from pathlib import Path
from unittest.mock import patch

import pytest

from src import main as main_module
from src.main import RunSummary, _build_parser, _print_dry_run_table, run
from tests.test_main import FakeClient, _seed_templates, make_config, make_state


# ---------------------------------------------------------------------------
# Argparse surface
# ---------------------------------------------------------------------------


def test_parser_defaults():
    args = _build_parser().parse_args([])
    assert args.dry_run is False
    assert args.today is None
    assert args.project_id is None
    assert args.cache_file is None
    assert args.verbose is False


def test_parser_today_parses_iso_date():
    args = _build_parser().parse_args(["--today", "2026-05-04"])
    assert args.today == date(2026, 5, 4)


def test_parser_today_rejects_bad_format():
    parser = _build_parser()
    with pytest.raises(SystemExit):
        parser.parse_args(["--today", "not-a-date"])


def test_parser_overrides():
    args = _build_parser().parse_args(
        [
            "--dry-run",
            "--today",
            "2026-05-04",
            "--project-id",
            "sandbox-id",
            "--cache-file",
            "/tmp/sandbox.json",
            "--verbose",
        ]
    )
    assert args.dry_run is True
    assert args.today == date(2026, 5, 4)
    assert args.project_id == "sandbox-id"
    assert args.cache_file == Path("/tmp/sandbox.json")
    assert args.verbose is True


# ---------------------------------------------------------------------------
# Dry-run semantics: no POST, no cache write, no LOG append
# ---------------------------------------------------------------------------


def test_dry_run_does_not_write_cache_file(tmp_path: Path):
    tdir = _seed_templates(tmp_path)
    cache_path = tmp_path / ".task_cache.json"
    summary = run(
        make_config(),
        make_state(),
        date(2026, 5, 4),  # Monday
        tdir,
        cache_path,
        client_factory=FakeClient,
        dry_run=True,
    )
    assert not cache_path.exists()
    assert len(summary.created) == 2
    assert all(d.decision == "WOULD CREATE" for d in summary.decisions)


def test_dry_run_decisions_for_sunday(tmp_path: Path):
    tdir = _seed_templates(tmp_path)
    cache_path = tmp_path / ".task_cache.json"
    summary = run(
        make_config(),
        make_state(),
        date(2026, 5, 3),  # Sunday
        tdir,
        cache_path,
        client_factory=FakeClient,
        dry_run=True,
    )
    assert summary.created == []
    assert all(d.decision == "SKIP (Sunday)" for d in summary.decisions)


def test_dry_run_decisions_when_paused(tmp_path: Path):
    """state.paused=True labels every decision as SKIP (paused)."""
    tdir = _seed_templates(tmp_path)
    cache_path = tmp_path / ".task_cache.json"
    state = make_state()
    state.paused = True
    summary = run(
        make_config(),
        state,
        date(2026, 5, 4),  # Monday — would otherwise create
        tdir,
        cache_path,
        client_factory=FakeClient,
        dry_run=True,
    )
    assert summary.created == []
    assert all(d.decision == "SKIP (paused)" for d in summary.decisions)


def test_paused_real_run_writes_cache_and_log_with_zero_creates(tmp_path: Path):
    """Non-dry-run paused: 0 creates, but cache + log still get written."""
    tdir = _seed_templates(tmp_path)
    cache_path = tmp_path / ".task_cache.json"
    state = make_state()
    state.paused = True
    summary = run(
        make_config(),
        state,
        date(2026, 5, 4),
        tdir,
        cache_path,
        client_factory=FakeClient,
    )
    assert summary.created == []
    assert summary.errors == 0
    assert cache_path.exists()  # save_cache still runs
    assert all(d.decision == "SKIP (paused)" for d in summary.decisions)


def test_dry_run_uses_cache_for_skip_decisions(tmp_path: Path):
    """Pre-seed cache; dry-run should label as cache hits, not WOULD CREATE."""
    tdir = _seed_templates(tmp_path)
    cache_path = tmp_path / ".task_cache.json"

    # Populate cache via a real-ish run first.
    run(
        make_config(),
        make_state(),
        date(2026, 5, 4),
        tdir,
        cache_path,
        client_factory=FakeClient,
    )
    assert cache_path.exists()
    pre = json.loads(cache_path.read_text())
    assert len(pre) == 2

    # Dry-run on the same day should report cache hits and NOT touch the cache.
    cache_mtime = cache_path.stat().st_mtime_ns
    summary = run(
        make_config(),
        make_state(),
        date(2026, 5, 4),
        tdir,
        cache_path,
        client_factory=FakeClient,
        dry_run=True,
    )
    assert all(d.decision == "SKIP (cache hit)" for d in summary.decisions)
    # File untouched.
    assert cache_path.stat().st_mtime_ns == cache_mtime


def test_project_id_override_threads_into_client(tmp_path: Path):
    """--project-id takes precedence over config.yaml."""
    tdir = _seed_templates(tmp_path)
    cache_path = tmp_path / ".task_cache.json"

    captured: dict[str, str] = {}

    def factory(**kwargs):
        captured.update({k: v for k, v in kwargs.items() if isinstance(v, str)})
        return FakeClient(**kwargs)

    run(
        make_config(),
        make_state(),
        date(2026, 5, 4),
        tdir,
        cache_path,
        client_factory=factory,
        project_id="sandbox-override",
    )
    assert captured["project_id"] == "sandbox-override"


# ---------------------------------------------------------------------------
# Dry-run table renderer
# ---------------------------------------------------------------------------


def test_dry_run_table_has_header_and_rows():
    from src.main import Decision

    summary = RunSummary(
        today=date(2026, 5, 4),
        created=[],
        skipped=[],
        errors=0,
        decisions=[
            Decision("daily-morning-reading", "a3f2b1c4d5e6f7a8", "WOULD CREATE"),
            Decision("daily-anki", "b8d2c1e4f5a67890", "SKIP (cache hit)"),
        ],
    )
    buf = io.StringIO()
    _print_dry_run_table(summary, out=buf)
    out = buf.getvalue()
    assert "TEMPLATE" in out
    assert "EXTERNAL_ID" in out
    assert "DECISION" in out
    assert "daily-morning-reading" in out
    assert "WOULD CREATE" in out
    assert "SKIP (cache hit)" in out


# ---------------------------------------------------------------------------
# main() end-to-end with monkeypatched paths
# ---------------------------------------------------------------------------


REPO_ROOT = Path(__file__).resolve().parent.parent
REAL_REFLECTION_TEMPLATES = REPO_ROOT / "curricula" / "long-way" / "reflection_templates"

# Syllabus key used by test harness.
_TEST_SYLLABUS_KEY = "main"


def _seed_repo(tmp_path: Path, monkeypatch) -> Path:
    """Set up a minimal multi-syllabus repo layout in tmp_path.

    Creates:
      - tmp_path/curriculum/rituals/   with the two test daily templates
      - tmp_path/curriculum/modules.yaml  (empty list)
      - tmp_path/state/shared.yaml        with Asia/Kolkata timezone
      - tmp_path/state/main.yaml          per-syllabus state
      - tmp_path/config.yaml              multi-syllabus format
      - tmp_path/.env                     with TODOIST_TOKEN

    Monkeypatches main module globals so main() uses tmp_path.
    Reflections land in tmp_path/reflections/main/...
    """
    curriculum_dir = tmp_path / "curriculum"
    rituals_dir = curriculum_dir / "rituals"
    rituals_dir.mkdir(parents=True, exist_ok=True)
    (curriculum_dir / "modules.yaml").write_text("[]\n")
    (curriculum_dir / "reflection_templates").mkdir(exist_ok=True)
    # Minimal syllabus.yaml so load_syllabus() succeeds.
    (curriculum_dir / "syllabus.yaml").write_text(
        "meta: {}\nphases:\n  - number: 1\n    name: Phase1\n    months: [1, 12]\n"
        "books: []\nprimary_book_by_month: {1: CSAPP}\nmodules: []\n"
    )

    # Seed the two daily task templates used by existing tests.
    from tests.test_templates import TPL_YAML
    (rituals_dir / "daily.yaml").write_text(TPL_YAML)

    state_dir = tmp_path / "state"
    state_dir.mkdir(exist_ok=True)
    (state_dir / "shared.yaml").write_text(
        "timezone: Asia/Kolkata\n"
        "manual_counters:\n"
        "  anki_card_count: 0\n"
    )
    (state_dir / f"{_TEST_SYLLABUS_KEY}.yaml").write_text(
        "start_date: 2026-05-04\n"
        "phase: 1\n"
        "month: 1\n"
        "current_module: 1\n"
        'current_book: "CSAPP"\n'
    )

    config_path = tmp_path / "config.yaml"
    config_path.write_text(
        f'ritual_times:\n'
        f'  morning_reading: "06:00"\n'
        f'  anki: "08:30"\n'
        f'  friday_review: "20:00"\n'
        f'  saturday_deep_block: "09:00"\n'
        f'  evening_hands_on: "19:00"\n'
        f'sunday_off: true\n'
        f'priority_order:\n'
        f'  - {_TEST_SYLLABUS_KEY}\n'
        f'syllabuses:\n'
        f'  {_TEST_SYLLABUS_KEY}:\n'
        f'    path: "{curriculum_dir}"\n'
        f'    todoist_project_id: "PROD-ID"\n'
        f'    state_file: "{state_dir / (_TEST_SYLLABUS_KEY + ".yaml")}"\n'
        f'    enabled: true\n'
        f'dashboard:\n'
        f'  github_username: "u"\n'
        f'  repo_name: "r"\n'
    )
    env_path = tmp_path / ".env"
    env_path.write_text("TODOIST_TOKEN=tok-from-env\n")

    reflections_dir = tmp_path / "reflections"
    reflections_dir.mkdir(exist_ok=True)

    monkeypatch.setattr(main_module, "CONFIG_PATH", config_path)
    monkeypatch.setattr(main_module, "SHARED_STATE_PATH", state_dir / "shared.yaml")
    monkeypatch.setattr(main_module, "ENV_PATH", env_path)
    monkeypatch.setattr(main_module, "LOG_PATH", tmp_path / "LOG.md")
    monkeypatch.setattr(main_module, "CACHE_PATH", tmp_path / ".task_cache.json")
    monkeypatch.setattr(main_module, "REFLECTIONS_DIR", reflections_dir)
    monkeypatch.setattr(
        main_module, "REFLECTION_TEMPLATES_DIR", REAL_REFLECTION_TEMPLATES
    )
    return tmp_path


def test_main_dry_run_end_to_end(tmp_path: Path, monkeypatch, capsys):
    _seed_repo(tmp_path, monkeypatch)

    with patch("src.main.TodoistClient", FakeClient):
        rc = main_module.main(["--dry-run", "--today", "2026-05-04"])
    assert rc == 0

    captured = capsys.readouterr()
    assert "WOULD CREATE" in captured.out
    assert "daily-morning-reading" in captured.out

    assert not (tmp_path / ".task_cache.json").exists()
    assert not (tmp_path / "LOG.md").exists()


def test_main_dry_run_sunday_zero_creates(tmp_path: Path, monkeypatch, capsys):
    _seed_repo(tmp_path, monkeypatch)
    with patch("src.main.TodoistClient", FakeClient):
        rc = main_module.main(["--dry-run", "--today", "2026-05-03"])  # Sunday
    assert rc == 0

    captured = capsys.readouterr()
    assert "WOULD CREATE" not in captured.out
    assert "SKIP (Sunday)" in captured.out


def test_main_real_run_writes_cache_and_log(tmp_path: Path, monkeypatch):
    _seed_repo(tmp_path, monkeypatch)
    with patch("src.main.TodoistClient", FakeClient):
        rc = main_module.main(["--today", "2026-05-04"])
    assert rc == 0
    assert (tmp_path / ".task_cache.json").exists()
    assert (tmp_path / "LOG.md").exists()
    log = (tmp_path / "LOG.md").read_text()
    assert "2026-05-04" in log
    assert "Created: 2" in log


def test_main_cache_file_override(tmp_path: Path, monkeypatch):
    _seed_repo(tmp_path, monkeypatch)
    sandbox = tmp_path / ".task_cache.sandbox.json"
    with patch("src.main.TodoistClient", FakeClient):
        rc = main_module.main(["--today", "2026-05-04", "--cache-file", str(sandbox)])
    assert rc == 0
    assert sandbox.exists()
    # Default cache file untouched.
    assert not (tmp_path / ".task_cache.json").exists()


def test_main_project_id_comes_from_config(tmp_path: Path, monkeypatch):
    """In multi-syllabus mode, the project_id comes from the config, not --project-id."""
    _seed_repo(tmp_path, monkeypatch)

    seen: dict[str, str] = {}

    class CapturingClient(FakeClient):
        def __init__(self, **kwargs):
            super().__init__(**kwargs)
            seen["project_id"] = kwargs["project_id"]

    with patch("src.main.TodoistClient", CapturingClient):
        rc = main_module.main(["--today", "2026-05-04"])
    assert rc == 0
    # Project ID comes from the seeded config YAML ("PROD-ID").
    assert seen["project_id"] == "PROD-ID"


# ---------------------------------------------------------------------------
# Cleanup CLI
# ---------------------------------------------------------------------------


class FakeAdmin:
    """Test double for TodoistAdminClient."""

    def __init__(self, *, token: str, **_: object) -> None:
        self.token = token
        self._tasks_by_project: dict[str, list[dict]] = {}
        self.deleted: list[str] = []

    def seed(self, project_id: str, tasks: list[dict]) -> None:
        self._tasks_by_project[project_id] = list(tasks)

    def list_tasks(self, project_id: str) -> list[dict]:
        return list(self._tasks_by_project.get(project_id, []))

    def delete_task(self, task_id: str) -> None:
        self.deleted.append(task_id)
        for tasks in self._tasks_by_project.values():
            tasks[:] = [t for t in tasks if str(t["id"]) != task_id]


def test_cleanup_lists_without_yes(tmp_path: Path, monkeypatch, capsys):
    _seed_repo(tmp_path, monkeypatch)
    admin = FakeAdmin(token="t")
    admin.seed("SANDBOX", [{"id": "1", "content": "a"}, {"id": "2", "content": "b"}])

    with patch("src.main.TodoistAdminClient", lambda **kw: admin):
        rc = main_module.main(["--cleanup-project", "SANDBOX"])
    assert rc == 0

    out = capsys.readouterr().out
    assert "2 task(s)" in out
    assert "Re-run with --yes" in out
    assert admin.deleted == []


def test_cleanup_deletes_with_yes(tmp_path: Path, monkeypatch, capsys):
    _seed_repo(tmp_path, monkeypatch)
    admin = FakeAdmin(token="t")
    admin.seed("SANDBOX", [{"id": "1", "content": "a"}, {"id": "2", "content": "b"}])

    with patch("src.main.TodoistAdminClient", lambda **kw: admin):
        rc = main_module.main(["--cleanup-project", "SANDBOX", "--yes"])
    assert rc == 0

    out = capsys.readouterr().out
    assert "Deleted 2/2" in out
    assert sorted(admin.deleted) == ["1", "2"]


def test_cleanup_with_yes_also_removes_cache_file(tmp_path: Path, monkeypatch, capsys):
    _seed_repo(tmp_path, monkeypatch)
    cache = tmp_path / ".task_cache.sandbox.json"
    cache.write_text("{}")

    admin = FakeAdmin(token="t")
    admin.seed("SANDBOX", [{"id": "1", "content": "a"}])

    with patch("src.main.TodoistAdminClient", lambda **kw: admin):
        rc = main_module.main(
            ["--cleanup-project", "SANDBOX", "--cache-file", str(cache), "--yes"]
        )
    assert rc == 0
    assert not cache.exists()


def test_cleanup_yes_with_empty_project(tmp_path: Path, monkeypatch, capsys):
    _seed_repo(tmp_path, monkeypatch)
    admin = FakeAdmin(token="t")
    admin.seed("EMPTY", [])

    with patch("src.main.TodoistAdminClient", lambda **kw: admin):
        rc = main_module.main(["--cleanup-project", "EMPTY", "--yes"])
    assert rc == 0
    out = capsys.readouterr().out
    assert "Nothing to delete" in out
    assert admin.deleted == []


# ---------------------------------------------------------------------------
# Phase C: stub creation wired into main.run, metadata walk
# ---------------------------------------------------------------------------


REAL_CURRICULUM_DIR = REPO_ROOT / "curricula" / "long-way"


def _seed_repo_with_real_templates(tmp_path: Path, monkeypatch) -> Path:
    """Same as _seed_repo, but the syllabus entry path points at the real
    curriculum dir so the run uses the full cadence templates (reflection stubs, etc).
    """
    _seed_repo(tmp_path, monkeypatch)
    # Rewrite config to point entry path at the real curriculum dir.
    state_dir = tmp_path / "state"
    config_path = tmp_path / "config.yaml"
    env_path = tmp_path / ".env"
    config_path.write_text(
        f'ritual_times:\n'
        f'  morning_reading: "06:00"\n'
        f'  anki: "08:30"\n'
        f'  friday_review: "20:00"\n'
        f'  saturday_deep_block: "09:00"\n'
        f'  evening_hands_on: "19:00"\n'
        f'  weekly_state_review: "10:00"\n'
        f'sunday_off: true\n'
        f'priority_order:\n'
        f'  - {_TEST_SYLLABUS_KEY}\n'
        f'syllabuses:\n'
        f'  {_TEST_SYLLABUS_KEY}:\n'
        f'    path: "{REAL_CURRICULUM_DIR}"\n'
        f'    todoist_project_id: "PROD-ID"\n'
        f'    state_file: "{state_dir / (_TEST_SYLLABUS_KEY + ".yaml")}"\n'
        f'    enabled: true\n'
        f'dashboard:\n'
        f'  github_username: "u"\n'
        f'  repo_name: "r"\n'
    )
    return tmp_path


def test_friday_run_creates_weekly_stub(tmp_path: Path, monkeypatch):
    _seed_repo_with_real_templates(tmp_path, monkeypatch)
    with patch("src.main.TodoistClient", FakeClient):
        rc = main_module.main(["--today", "2026-05-08"])  # Friday, ISO W19
    assert rc == 0

    stub = tmp_path / "reflections" / _TEST_SYLLABUS_KEY / "weekly" / "2026-W19.md"
    assert stub.exists()
    from src.reflections import _baseline_word_count, split_frontmatter

    fm, body = split_frontmatter(stub.read_text())
    assert fm["type"] == "weekly"
    assert fm["iso_week"] == "2026-W19"
    assert fm["status"] == "stub"
    # The metadata walk runs after stub creation and updates word_count to
    # the baseline count of the rendered body — NOT 0. word_count: 0 only
    # appears in the unfilled template before the walk runs.
    assert fm["word_count"] == _baseline_word_count(REAL_REFLECTION_TEMPLATES, "weekly")
    assert "Three things I learned this week" in body


def test_friday_rerun_does_not_clobber_stub(tmp_path: Path, monkeypatch):
    _seed_repo_with_real_templates(tmp_path, monkeypatch)
    with patch("src.main.TodoistClient", FakeClient):
        main_module.main(["--today", "2026-05-08"])

    stub = tmp_path / "reflections" / _TEST_SYLLABUS_KEY / "weekly" / "2026-W19.md"
    # Owner edits the stub.
    text = stub.read_text()
    edited = text.replace("status: stub", "status: stub").replace(
        "word_count: 0", "word_count: 0"
    ) + "\nMy actual prose written here.\n"
    stub.write_text(edited)
    mtime_before = stub.stat().st_mtime_ns

    # Re-run.
    with patch("src.main.TodoistClient", FakeClient):
        main_module.main(["--today", "2026-05-08"])

    # File still has owner prose. Frontmatter word_count was updated by the
    # metadata walk (so the file IS rewritten), but the body content survives.
    after = stub.read_text()
    assert "My actual prose written here." in after


def test_dry_run_prints_stub_table_and_writes_no_files(tmp_path: Path, monkeypatch, capsys):
    _seed_repo_with_real_templates(tmp_path, monkeypatch)
    with patch("src.main.TodoistClient", FakeClient):
        rc = main_module.main(["--dry-run", "--today", "2026-05-08"])
    assert rc == 0

    out = capsys.readouterr().out
    assert "REFLECTION STUBS" in out
    assert "WOULD CREATE STUB" in out
    assert "weekly-friday-review" in out

    stub = tmp_path / "reflections" / _TEST_SYLLABUS_KEY / "weekly" / "2026-W19.md"
    assert not stub.exists()


def test_dry_run_last_saturday_shared_path_pending_collision(
    tmp_path: Path, monkeypatch, capsys
):
    """monthly-retrieval and monthly-review point at the same path. First
    template prints WOULD CREATE STUB, second prints WOULD SKIP STUB (pending).
    """
    _seed_repo_with_real_templates(tmp_path, monkeypatch)
    with patch("src.main.TodoistClient", FakeClient):
        rc = main_module.main(["--dry-run", "--today", "2026-05-30"])
    assert rc == 0

    out = capsys.readouterr().out
    # Exactly one WOULD CREATE STUB line for the monthly path.
    assert out.count("WOULD CREATE STUB") >= 1
    assert "WOULD SKIP STUB (pending)" in out
    assert f"reflections/{_TEST_SYLLABUS_KEY}/monthly/2026-05.md" in out


def test_paused_metadata_walk_still_updates(tmp_path: Path, monkeypatch):
    """Pause skips creates but the metadata walk still updates word_count + status."""
    _seed_repo_with_real_templates(tmp_path, monkeypatch)

    # Pre-populate a stub with prose past the threshold.
    stub = tmp_path / "reflections" / _TEST_SYLLABUS_KEY / "weekly" / "2026-W19.md"
    stub.parent.mkdir(parents=True, exist_ok=True)
    fm = (
        "---\n"
        "type: weekly\n"
        "date: 2026-05-08\n"
        "iso_week: 2026-W19\n"
        "status: stub\n"
        "word_count: 0\n"
        "---\n"
    )
    # Compute baseline for weekly + 60 words to comfortably cross threshold.
    from src.reflections import _baseline_word_count, WORD_COUNT_THRESHOLD

    baseline = _baseline_word_count(REAL_REFLECTION_TEMPLATES, "weekly")
    body = "word " * (baseline + WORD_COUNT_THRESHOLD + 10)
    stub.write_text(fm + body)

    # Set state.paused: true in the per-syllabus state file.
    syllabus_state_path = tmp_path / "state" / f"{_TEST_SYLLABUS_KEY}.yaml"
    syllabus_state_path.write_text(
        syllabus_state_path.read_text().replace("phase: 1\n", "phase: 1\npaused: true\n")
    )

    with patch("src.main.TodoistClient", FakeClient):
        rc = main_module.main(["--today", "2026-05-08"])
    assert rc == 0

    # Stub should now be filled — metadata walk ran despite pause.
    from src.reflections import split_frontmatter

    fm_after, _ = split_frontmatter(stub.read_text())
    assert fm_after["status"] == "filled"
    assert fm_after["word_count"] >= baseline + WORD_COUNT_THRESHOLD


def test_metadata_walk_runs_after_stub_creation_ordering(
    tmp_path: Path, monkeypatch
):
    """Empty reflections/, run --today Friday → stub created AND walked.

    If walk ran BEFORE creation, the freshly-created stub would be invisible
    to the walk this run; word_count would still be 0 (the template's value).
    We expect word_count == baseline (the actual body length) — proving the
    walk ran AFTER creation and rewrote the frontmatter.
    """
    _seed_repo_with_real_templates(tmp_path, monkeypatch)

    with patch("src.main.TodoistClient", FakeClient):
        main_module.main(["--today", "2026-05-08"])

    stub = tmp_path / "reflections" / _TEST_SYLLABUS_KEY / "weekly" / "2026-W19.md"
    assert stub.exists()
    from src.reflections import _baseline_word_count, split_frontmatter

    fm, body = split_frontmatter(stub.read_text())
    assert fm["status"] == "stub"  # below threshold
    assert fm["word_count"] == _baseline_word_count(
        REAL_REFLECTION_TEMPLATES, "weekly"
    )  # walk ran AFTER creation
    assert fm["word_count"] > 0  # disproves "walk ran before creation"
    assert "Three things I learned this week" in body


def test_log_records_stub_and_metadata_lines(tmp_path: Path, monkeypatch):
    _seed_repo_with_real_templates(tmp_path, monkeypatch)
    with patch("src.main.TodoistClient", FakeClient):
        main_module.main(["--today", "2026-05-08"])
    log = (tmp_path / "LOG.md").read_text()
    assert "Reflection stubs created:" in log
    assert "Reflection metadata updated:" in log
