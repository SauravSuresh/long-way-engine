"""Tests for scripts/migrate_to_multi_syllabus.py"""
import json
from pathlib import Path

import yaml

from scripts.migrate_to_multi_syllabus import (
    classify_reflection,
    rewrite_config_yaml,
    run_migration,
    split_state_yaml,
    wrap_cache,
)


# ---------------------------------------------------------------------------
# Unit tests: pure functions
# ---------------------------------------------------------------------------


def test_split_state_yaml_basic():
    old = {
        "start_date": "2026-05-05",
        "timezone": "Asia/Kolkata",
        "phase": 1,
        "month": 1,
        "current_module": 7,
        "current_book": "CS:APP",
        "completed_modules": [1, 2],
        "books_state": {"CS:APP": "current"},
        "learning_tracks": {"Courses": {"boot.dev": "current"}},
        "paused": False,
        "paused_since": None,
        "pause_history": [],
        "manual_counters": {"anki_card_count": 99, "prs_opened": 3},
        "notes": "hello",
    }
    shared, syllabus = split_state_yaml(old)
    assert shared == {
        "timezone": "Asia/Kolkata",
        "manual_counters": {"anki_card_count": 99, "prs_opened": 3},
        "notes": "hello",
    }
    assert syllabus == {
        "start_date": "2026-05-05",
        "phase": 1,
        "month": 1,
        "current_module": 7,
        "current_book": "CS:APP",
        "completed_modules": [1, 2],
        "books_state": {"CS:APP": "current"},
        "learning_tracks": {"Courses": {"boot.dev": "current"}},
        "paused": False,
        "paused_since": None,
        "pause_history": [],
    }


def test_rewrite_config_yaml_basic():
    old = {
        "todoist": {"project_id": "ABC", "labels": {"daily": "daily-ritual"}},
        "ritual_times": {"morning_reading": "06:00", "anki": "08:30"},
        "sunday_off": True,
        "pair_day": "thursday",
        "curriculum_dir": "curriculum",
        "dashboard": {"github_username": "foo", "repo_name": "bar"},
    }
    new = rewrite_config_yaml(old, syllabus_name="long-way")
    assert new["priority_order"] == ["long-way"]
    assert new["syllabuses"]["long-way"] == {
        "path": "curricula/long-way",
        "todoist_project_id": "ABC",
        "state_file": "state/long-way.yaml",
        "enabled": True,
    }
    # Top-level ritual_times preserved.
    assert new["ritual_times"]["morning_reading"] == "06:00"
    # dashboard, pair_day, sunday_off preserved.
    assert new["dashboard"] == {"github_username": "foo", "repo_name": "bar"}
    assert new["pair_day"] == "thursday"
    assert new["sunday_off"] is True
    # Old top-level keys gone.
    assert "todoist" not in new
    assert "curriculum_dir" not in new


def test_wrap_cache_namespaces():
    flat = {"ext-1": {"todoist_id": "100"}}
    wrapped = wrap_cache(flat, "long-way")
    assert wrapped == {"long-way": {"ext-1": {"todoist_id": "100"}}}


def test_wrap_cache_idempotent_if_already_wrapped():
    already = {"long-way": {"ext-1": {"todoist_id": "100"}}}
    assert wrap_cache(already, "long-way") == already


def test_classify_reflection_weekly():
    assert classify_reflection("2026-W21.md") == "weekly"


def test_classify_reflection_monthly():
    assert classify_reflection("2026-04.md") == "monthly"


def test_classify_reflection_quarterly():
    assert classify_reflection("2026-Q2.md") == "quarterly"


def test_classify_reflection_annual():
    assert classify_reflection("2026.md") == "annual"


def test_classify_reflection_unknown_returns_none():
    assert classify_reflection("notes.md") is None


# ---------------------------------------------------------------------------
# Edge-case unit tests
# ---------------------------------------------------------------------------


def test_wrap_cache_empty_returns_empty():
    assert wrap_cache({}, "long-way") == {}


def test_wrap_cache_already_wrapped_empty_namespace():
    """A wrapped-but-empty namespace must not be double-wrapped."""
    already = {"long-way": {}}
    assert wrap_cache(already, "long-way") == {"long-way": {}}


def test_split_state_yaml_only_shared_keys():
    """Keys that belong to neither bucket are silently dropped."""
    old = {"timezone": "UTC", "unknown_field": "x"}
    shared, syllabus = split_state_yaml(old)
    assert shared == {"timezone": "UTC"}
    assert syllabus == {}


def test_classify_reflection_zero_padded_week():
    assert classify_reflection("2026-W01.md") == "weekly"


def test_classify_reflection_double_digit_month():
    assert classify_reflection("2026-12.md") == "monthly"


# ---------------------------------------------------------------------------
# End-to-end integration tests (tmp_path)
# ---------------------------------------------------------------------------


def test_run_migration_end_to_end(tmp_path: Path):
    repo = tmp_path / "repo"
    repo.mkdir()
    (repo / "curriculum").mkdir()
    (repo / "curriculum" / "syllabus.yaml").write_text("meta:\n  name: x\n")
    (repo / "state.yaml").write_text(
        "start_date: 2026-05-05\n"
        "timezone: Asia/Kolkata\n"
        "phase: 1\n"
        "month: 1\n"
        "current_module: 1\n"
        "current_book: foo\n"
        "manual_counters:\n  anki_card_count: 0\n"
        "notes: hi\n"
    )
    (repo / "config.yaml").write_text(
        "todoist:\n  project_id: ABC\n"
        "ritual_times:\n  morning_reading: '06:00'\n"
        "sunday_off: true\n"
        "curriculum_dir: curriculum\n"
        "dashboard:\n  github_username: u\n  repo_name: r\n"
    )
    (repo / ".task_cache.json").write_text(json.dumps({"ext-1": {"todoist_id": "100"}}))
    (repo / "reflections").mkdir()
    (repo / "reflections" / "2026-W21.md").write_text("week stub")

    rc = run_migration(repo, syllabus_name="long-way", dry_run=False)
    assert rc == 0
    assert (repo / "curricula" / "long-way" / "syllabus.yaml").exists()
    assert (repo / "state" / "shared.yaml").exists()
    assert (repo / "state" / "long-way.yaml").exists()
    assert not (repo / "state.yaml").exists()
    new_cfg = yaml.safe_load((repo / "config.yaml").read_text())
    assert new_cfg["priority_order"] == ["long-way"]
    assert new_cfg["syllabuses"]["long-way"]["todoist_project_id"] == "ABC"
    cache = json.loads((repo / ".task_cache.json").read_text())
    assert cache == {"long-way": {"ext-1": {"todoist_id": "100"}}}
    assert (repo / "reflections" / "long-way" / "weekly" / "2026-W21.md").exists()


def test_run_migration_idempotent(tmp_path: Path):
    repo = tmp_path / "repo"
    repo.mkdir()
    (repo / "curricula" / "long-way").mkdir(parents=True)
    (repo / "state").mkdir()
    (repo / "state" / "shared.yaml").write_text("timezone: UTC\n")
    (repo / "state" / "long-way.yaml").write_text(
        "start_date: 2026-05-05\ncurrent_module: 1\ncurrent_book: x\n"
    )
    (repo / "config.yaml").write_text(
        "ritual_times:\n  morning_reading: '06:00'\n"
        "priority_order: [long-way]\n"
        "syllabuses:\n  long-way:\n    path: curricula/long-way\n"
        "    todoist_project_id: ABC\n    state_file: state/long-way.yaml\n"
        "    enabled: true\n"
        "dashboard:\n  github_username: u\n  repo_name: r\n"
    )
    rc = run_migration(repo, syllabus_name="long-way", dry_run=False)
    assert rc == 0


def test_run_migration_dry_run_makes_no_changes(tmp_path: Path):
    repo = tmp_path / "repo"
    repo.mkdir()
    (repo / "curriculum").mkdir()
    (repo / "curriculum" / "mod.yaml").write_text("x: 1\n")
    (repo / "state.yaml").write_text("timezone: UTC\nstart_date: 2026-01-01\n")
    (repo / "config.yaml").write_text(
        "todoist:\n  project_id: XYZ\n"
        "ritual_times:\n  anki: '08:00'\n"
    )

    rc = run_migration(repo, syllabus_name="long-way", dry_run=True)
    assert rc == 0
    # Nothing moved
    assert (repo / "curriculum").exists()
    assert (repo / "state.yaml").exists()
    assert not (repo / "curricula").exists()
    assert not (repo / "state" / "shared.yaml").exists()


def test_run_migration_missing_optional_files(tmp_path: Path):
    """Migration succeeds even when caches and reflections are absent."""
    repo = tmp_path / "repo"
    repo.mkdir()
    (repo / "curriculum").mkdir()
    (repo / "state.yaml").write_text("timezone: UTC\nstart_date: 2026-01-01\n")
    (repo / "config.yaml").write_text(
        "todoist:\n  project_id: XYZ\n"
        "ritual_times:\n  anki: '08:00'\n"
    )
    # No .task_cache.json, no .completion_cache.json, no reflections/

    rc = run_migration(repo, syllabus_name="long-way", dry_run=False)
    assert rc == 0
    assert (repo / "curricula" / "long-way").exists()
    assert (repo / "state" / "shared.yaml").exists()


def test_run_migration_unknown_reflection_files_not_moved(tmp_path: Path):
    """Files that don't match any cadence pattern stay in reflections/."""
    repo = tmp_path / "repo"
    repo.mkdir()
    (repo / "curriculum").mkdir()
    (repo / "state.yaml").write_text("timezone: UTC\nstart_date: 2026-01-01\n")
    (repo / "config.yaml").write_text(
        "todoist:\n  project_id: XYZ\n"
    )
    (repo / "reflections").mkdir()
    (repo / "reflections" / "notes.md").write_text("random note")
    (repo / "reflections" / "2026-W10.md").write_text("weekly")

    rc = run_migration(repo, syllabus_name="long-way", dry_run=False)
    assert rc == 0
    # Unclassified file stays put
    assert (repo / "reflections" / "notes.md").exists()
    # Classified file moved
    assert (repo / "reflections" / "long-way" / "weekly" / "2026-W10.md").exists()
