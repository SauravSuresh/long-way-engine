"""Tests for scripts/rebuild_cache.py — Phase F item 2."""

from __future__ import annotations

import importlib.util
import sys
from datetime import date
from pathlib import Path

import pytest

from src.ids import external_id, module_external_id

REPO_ROOT = Path(__file__).resolve().parent.parent
SCRIPT_PATH = REPO_ROOT / "scripts" / "rebuild_cache.py"


@pytest.fixture(scope="module")
def rebuild_cache():
    """Import scripts/rebuild_cache.py without running its CLI."""
    spec = importlib.util.spec_from_file_location("rebuild_cache", SCRIPT_PATH)
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    sys.modules["rebuild_cache"] = mod
    spec.loader.exec_module(mod)
    return mod


# --- index ------------------------------------------------------------------


def test_build_index_covers_date_window(tmp_path: Path, rebuild_cache):
    tdir = tmp_path / "tpl"
    tdir.mkdir()
    (tdir / "daily.yaml").write_text(
        "- id: daily-anki\n"
        "  title: Anki review\n"
        "  cadence: daily\n"
        "  skip_if: sunday\n"
    )
    index = rebuild_cache.build_external_id_index(
        [tdir], since=date(2026, 5, 1), until=date(2026, 5, 3)
    )
    # 1 template × 3 dates = 3 entries.
    assert len(index) == 3
    assert index[external_id("daily-anki", date(2026, 5, 2))] == (
        "daily-anki", "2026-05-02"
    )


def test_build_index_includes_module_keyed_templates(tmp_path: Path, rebuild_cache):
    tdir = tmp_path / "tpl"
    tdir.mkdir()
    (tdir / "modules.yaml").write_text(
        "- id: module-01-onboarding\n"
        "  title: Module 1\n"
        "  cadence: once-per-module\n"
        "  module_number: 1\n"
        "- id: module-02-onboarding\n"
        "  title: Module 2\n"
        "  cadence: once-per-module\n"
        "  module_number: 2\n"
    )
    index = rebuild_cache.build_external_id_index(
        [tdir], since=date(2026, 5, 1), until=date(2026, 5, 1)
    )
    assert index[module_external_id("module-01-onboarding", 1)] == (
        "module-01-onboarding", "module:1"
    )
    assert index[module_external_id("module-02-onboarding", 2)] == (
        "module-02-onboarding", "module:2"
    )


def test_build_index_skips_module_template_without_number(
    tmp_path: Path, rebuild_cache
):
    tdir = tmp_path / "tpl"
    tdir.mkdir()
    (tdir / "broken.yaml").write_text(
        "- id: missing-number\n"
        "  title: Missing\n"
        "  cadence: once-per-module\n"
    )
    index = rebuild_cache.build_external_id_index(
        [tdir], since=date(2026, 5, 1), until=date(2026, 5, 1)
    )
    assert index == {}


# --- cache_entries_from_tasks -----------------------------------------------


def _task(task_id: str, marker_ext: str | None, **extra) -> dict:
    desc = ""
    if marker_ext is not None:
        desc = f"some prose\n\n<!--LW:{marker_ext}-->"
    base = {"id": task_id, "description": desc}
    base.update(extra)
    return base


def test_cache_entries_match_index(rebuild_cache):
    ext = external_id("daily-anki", date(2026, 5, 4))
    index = {ext: ("daily-anki", "2026-05-04")}
    cache, unmatched = rebuild_cache.cache_entries_from_tasks(
        [_task("T1", ext, added_at="2026-05-04T03:00:00Z")],
        index,
        fallback_now_iso="2026-05-04T05:00:00+00:00",
    )
    assert unmatched == 0
    assert cache[ext] == {
        "todoist_task_id": "T1",
        "created_at": "2026-05-04T03:00:00Z",
        "template_id": "daily-anki",
        "due_date": "2026-05-04",
    }


def test_cache_entries_unmatched_marker_kept_with_blank_fields(
    rebuild_cache, caplog
):
    unknown_ext = "deadbeefdeadbeef"
    with caplog.at_level("WARNING"):
        cache, unmatched = rebuild_cache.cache_entries_from_tasks(
            [_task("T9", unknown_ext, added_at="2026-05-04T03:00:00Z")],
            index={},
            fallback_now_iso="2026-05-04T05:00:00+00:00",
        )
    assert unmatched == 1
    assert cache[unknown_ext]["todoist_task_id"] == "T9"
    assert cache[unknown_ext]["template_id"] == ""
    assert cache[unknown_ext]["due_date"] == ""
    assert any("did not match" in r.getMessage() for r in caplog.records)


def test_cache_entries_skip_tasks_without_marker(rebuild_cache):
    cache, unmatched = rebuild_cache.cache_entries_from_tasks(
        [_task("T1", None)],
        index={},
        fallback_now_iso="2026-05-04T05:00:00+00:00",
    )
    assert cache == {}
    assert unmatched == 0


def test_cache_entries_use_completed_at_when_no_added_at(rebuild_cache):
    ext = external_id("daily-anki", date(2026, 5, 4))
    index = {ext: ("daily-anki", "2026-05-04")}
    cache, _ = rebuild_cache.cache_entries_from_tasks(
        [{"id": "T1", "description": f"<!--LW:{ext}-->", "completed_at": "2026-05-04T08:30:00Z"}],
        index,
        fallback_now_iso="2026-05-04T05:00:00+00:00",
    )
    assert cache[ext]["created_at"] == "2026-05-04T08:30:00Z"


def test_cache_entries_fall_back_to_now_when_neither(rebuild_cache):
    ext = external_id("daily-anki", date(2026, 5, 4))
    index = {ext: ("daily-anki", "2026-05-04")}
    cache, _ = rebuild_cache.cache_entries_from_tasks(
        [{"id": "T1", "description": f"<!--LW:{ext}-->"}],
        index,
        fallback_now_iso="2026-05-04T05:00:00+00:00",
    )
    assert cache[ext]["created_at"] == "2026-05-04T05:00:00+00:00"


def test_cache_entries_drop_tasks_without_id(rebuild_cache):
    ext = external_id("daily-anki", date(2026, 5, 4))
    index = {ext: ("daily-anki", "2026-05-04")}
    cache, _ = rebuild_cache.cache_entries_from_tasks(
        [{"id": "", "description": f"<!--LW:{ext}-->"}],
        index,
        fallback_now_iso="2026-05-04T05:00:00+00:00",
    )
    assert cache == {}
