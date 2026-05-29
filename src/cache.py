"""Idempotency cache. Maps external_id -> task creation record.

The cache is the fast path for dedup. The content marker embedded in each
task description (see todoist.py) is the safety net: if the cache is lost,
a future rebuild script (Phase F) reconstructs from the markers.
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

PRUNE_DAYS_DEFAULT = 60


def load_cache(path: Path) -> dict[str, dict[str, Any]]:
    """Load cache from disk. Missing or corrupt -> empty dict."""
    if not path.exists():
        return {}
    try:
        with path.open("r", encoding="utf-8") as f:
            data = json.load(f)
        if not isinstance(data, dict):
            logger.warning("cache file %s is not a JSON object; treating as empty", path)
            return {}
        return data
    except json.JSONDecodeError as e:
        logger.warning("cache file %s is corrupt (%s); treating as empty", path, e)
        return {}


def save_cache(path: Path, cache: dict[str, dict[str, Any]]) -> None:
    """Persist cache atomically."""
    tmp = path.with_suffix(path.suffix + ".tmp")
    with tmp.open("w", encoding="utf-8") as f:
        json.dump(cache, f, indent=2, sort_keys=True)
        f.write("\n")
    tmp.replace(path)


@dataclass
class NamespacedCache:
    data: dict[str, dict[str, dict[str, Any]]] = field(default_factory=dict)

    def get(self, syllabus: str, external_id: str) -> dict[str, Any] | None:
        return self.data.get(syllabus, {}).get(external_id)

    def set(self, syllabus: str, external_id: str, record: dict[str, Any]) -> None:
        self.data.setdefault(syllabus, {})[external_id] = record

    def for_syllabus(self, syllabus: str) -> dict[str, dict[str, Any]]:
        """Read-only view of records for one syllabus. Returns {} if unknown.

        To insert, use `.set()` instead — mutating the returned dict has no effect
        on cache state when the syllabus is absent (a fresh empty dict is returned).
        """
        return self.data.get(syllabus, {})


def _looks_like_flat_cache(d: dict[str, Any]) -> bool:
    """True if `d` looks like a legacy flat cache (top-level values are records).

    A record contains a `todoist_id` key; a namespace bucket is itself a dict
    of records, so it will NOT contain `todoist_id` at the top level.
    """
    if not d:
        return False
    return any(isinstance(v, dict) and "todoist_id" in v for v in d.values())


def load_namespaced_cache(path: Path) -> NamespacedCache:
    if not path.exists():
        return NamespacedCache()
    with path.open("r", encoding="utf-8") as f:
        try:
            data = json.load(f)
        except json.JSONDecodeError:
            return NamespacedCache()
    if not isinstance(data, dict):
        return NamespacedCache()
    if _looks_like_flat_cache(data):
        raise ValueError(
            "legacy flat cache detected; run scripts/migrate_to_multi_syllabus.py first"
        )
    return NamespacedCache(
        data={
            sk: {ek: dict(rec) for ek, rec in entries.items()}
            for sk, entries in data.items()
        }
    )


def save_namespaced_cache(path: Path, nc: NamespacedCache) -> None:
    tmp = path.with_suffix(path.suffix + ".tmp")
    with tmp.open("w", encoding="utf-8") as f:
        json.dump(nc.data, f, indent=2, sort_keys=True)
        f.write("\n")
    tmp.replace(path)


def lift_flat_cache_under_syllabus(
    flat: dict[str, dict[str, Any]], syllabus_key: str
) -> dict[str, dict[str, dict[str, Any]]]:
    return {syllabus_key: dict(flat)}


def prune(
    cache: dict[str, dict[str, Any]],
    *,
    now: datetime,
    days: int = PRUNE_DAYS_DEFAULT,
) -> dict[str, dict[str, Any]]:
    """Drop entries whose created_at is older than `days`. Returns a new dict.

    `now` is required (no system-clock default) so the call chain has a
    single injection point in src/clock.py.
    """
    cutoff = now - timedelta(days=days)
    kept: dict[str, dict[str, Any]] = {}
    for ext_id, entry in cache.items():
        created_at_raw = entry.get("created_at")
        if not created_at_raw:
            kept[ext_id] = entry
            continue
        try:
            created_at = datetime.fromisoformat(created_at_raw)
        except ValueError:
            kept[ext_id] = entry
            continue
        if created_at >= cutoff:
            kept[ext_id] = entry
    return kept
