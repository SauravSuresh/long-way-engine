import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

from src.cache import load_cache, prune, save_cache


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
