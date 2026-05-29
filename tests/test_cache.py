import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from src.cache import (
    NamespacedCache,
    lift_flat_cache_under_syllabus,
    load_cache,
    load_namespaced_cache,
    prune,
    save_cache,
    save_namespaced_cache,
)


def test_load_missing_returns_empty(tmp_path: Path):
    assert load_cache(tmp_path / "nope.json") == {}


def test_round_trip(tmp_path: Path):
    path = tmp_path / "cache.json"
    cache = {
        "abc123": {
            "todoist_task_id": "8901234567",
            "created_at": "2026-05-04T03:00:00+05:30",
            "template_id": "daily-anki",
            "due_date": "2026-05-04",
        }
    }
    save_cache(path, cache)
    assert load_cache(path) == cache


def test_corrupt_returns_empty(tmp_path: Path):
    path = tmp_path / "cache.json"
    path.write_text("{ this is not json")
    assert load_cache(path) == {}


def test_non_object_returns_empty(tmp_path: Path):
    path = tmp_path / "cache.json"
    path.write_text(json.dumps([1, 2, 3]))
    assert load_cache(path) == {}


def test_prune_drops_old_keeps_recent():
    now = datetime(2026, 5, 4, 0, 0, tzinfo=timezone.utc)
    old = (now - timedelta(days=61)).isoformat()
    recent = (now - timedelta(days=59)).isoformat()
    cache = {
        "old": {"created_at": old, "template_id": "x", "due_date": "2026-03-04"},
        "recent": {"created_at": recent, "template_id": "y", "due_date": "2026-03-06"},
    }
    out = prune(cache, days=60, now=now)
    assert "old" not in out
    assert "recent" in out


def test_prune_keeps_entries_with_unparseable_created_at():
    now = datetime(2026, 5, 4, tzinfo=timezone.utc)
    cache = {"weird": {"created_at": "not-a-date", "template_id": "x"}}
    out = prune(cache, days=60, now=now)
    assert "weird" in out


def test_prune_keeps_entries_missing_created_at():
    now = datetime(2026, 5, 4, tzinfo=timezone.utc)
    cache = {"old_format": {"template_id": "x"}}
    out = prune(cache, days=60, now=now)
    assert "old_format" in out


# ── NamespacedCache tests ─────────────────────────────────────────────────────


def test_lift_flat_cache_under_syllabus():
    flat = {"ext-1": {"todoist_id": "100"}, "ext-2": {"todoist_id": "101"}}
    namespaced = lift_flat_cache_under_syllabus(flat, "long-way")
    assert namespaced == {"long-way": flat}


def test_load_namespaced_cache_existing(tmp_path):
    import json
    p = tmp_path / "task_cache.json"
    p.write_text(json.dumps({"long-way": {"ext-1": {"todoist_id": "100"}}}))
    nc = load_namespaced_cache(p)
    assert isinstance(nc, NamespacedCache)
    assert nc.get("long-way", "ext-1") == {"todoist_id": "100"}
    assert nc.get("long-way", "ext-missing") is None
    assert nc.get("missing-syllabus", "ext-1") is None


def test_load_namespaced_cache_flat_legacy(tmp_path):
    """Legacy flat cache (no syllabus layer) is detected and rejected — migrate first."""
    import json
    import pytest
    p = tmp_path / "task_cache.json"
    p.write_text(json.dumps({"ext-1": {"todoist_id": "100"}}))
    with pytest.raises(ValueError, match="legacy flat cache"):
        load_namespaced_cache(p)


def test_save_and_round_trip(tmp_path):
    p = tmp_path / "task_cache.json"
    nc = NamespacedCache(data={"long-way": {"ext-1": {"todoist_id": "100"}}})
    nc.set("long-way", "ext-2", {"todoist_id": "101"})
    save_namespaced_cache(p, nc)
    nc2 = load_namespaced_cache(p)
    assert nc2.get("long-way", "ext-1") == {"todoist_id": "100"}
    assert nc2.get("long-way", "ext-2") == {"todoist_id": "101"}


def test_load_missing_file_returns_empty(tmp_path):
    nc = load_namespaced_cache(tmp_path / "absent.json")
    assert nc.get("any", "ext-1") is None


def test_load_namespaced_cache_corrupt_json_returns_empty(tmp_path):
    p = tmp_path / "task_cache.json"
    p.write_text("{not valid json")
    nc = load_namespaced_cache(p)
    assert nc.get("any", "ext") is None


def test_load_namespaced_cache_non_dict_top_level_returns_empty(tmp_path):
    p = tmp_path / "task_cache.json"
    p.write_text(json.dumps(["not", "a", "dict"]))
    nc = load_namespaced_cache(p)
    assert nc.get("any", "ext") is None


def test_load_namespaced_cache_detects_mixed_flat_record(tmp_path):
    """A file where one top-level entry is a flat record (legacy) must still be rejected,
    even if another top-level entry looks like a namespace.
    """
    p = tmp_path / "task_cache.json"
    p.write_text(json.dumps({
        "long-way": {"ext-a": {"todoist_id": "100"}},
        "ext-b": {"todoist_id": "200"},  # flat record at top level — should trigger detector
    }))
    with pytest.raises(ValueError, match="legacy flat cache"):
        load_namespaced_cache(p)
