"""Idempotency cache. Maps external_id -> task creation record.

The cache is the fast path for dedup. The content marker embedded in each
task description (see todoist.py) is the safety net: if the cache is lost,
a future rebuild script (Phase F) reconstructs from the markers.
"""

from __future__ import annotations

import json
import logging
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
