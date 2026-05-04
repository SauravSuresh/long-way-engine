"""Phase F item 2: reconstruct .task_cache.json from project markers.

READ-ONLY. The script issues only HTTP GETs (against the active-tasks
endpoint and the completed-tasks endpoint) and never writes back to
Todoist. Audit pattern:

    grep -nE 'requests\\.(post|patch|delete|put)' scripts/rebuild_cache.py

(zero matches required.)

Why both endpoints? Runtime marker dedup only inspects active tasks,
because by the time a task is completed it can't (and shouldn't) be
recreated by the engine. But if `.task_cache.json` is wiped AFTER some
tasks have been completed within the prune window, naive runtime would
miss them on its next sweep and create duplicates. Rebuild therefore
walks active + the last-N-days completed window, unions the markers,
and writes a cache that lets runtime dedup pick up where it left off.

template_id + due_date are recovered by reverse-searching the engine's
templates × the search window. Unrecognized markers (template removed
or out of window) keep todoist_task_id + a created_at proxy and log a
WARNING. Runtime dedup still works for them — it only needs the
external_id -> todoist_task_id mapping.

Usage:

    python scripts/rebuild_cache.py [--project-id ID] [--days N] \\
        [--out PATH] [--dry-run]

`--dry-run` prints the resulting cache to stdout instead of writing.
Default --out is .task_cache.rebuilt.json so the existing
.task_cache.json is never clobbered without an explicit `mv`.
"""

from __future__ import annotations

import argparse
import json
import logging
import sys
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Any

import requests
import yaml

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))

from src.config import parse_env_file  # noqa: E402
from src.ids import external_id, module_external_id  # noqa: E402
from src.templates import load_templates  # noqa: E402
from src.todoist import API_ROOT, COMPLETION_PATH, MARKER_RE  # noqa: E402

logger = logging.getLogger("rebuild_cache")

DEFAULT_WINDOW_DAYS = 90
DEFAULT_PAGE_LIMIT = 200
DEFAULT_TIMEOUT = 30
TEMPLATES_DIR = REPO_ROOT / "task_templates"


# --- index ------------------------------------------------------------------


def build_external_id_index(
    templates_dir: Path, since: date, until: date
) -> dict[str, tuple[str, str]]:
    """Pre-compute external_id -> (template_id, due_date_or_module_key).

    Walks every loaded template across [since, until] inclusive for
    date-keyed cadences, plus once-per-module ids keyed by module_number.
    """
    templates = load_templates(templates_dir)
    index: dict[str, tuple[str, str]] = {}
    for tpl in templates:
        if tpl.cadence == "once-per-module":
            if tpl.module_number is None:
                continue
            ext = module_external_id(tpl.id, tpl.module_number)
            index[ext] = (tpl.id, f"module:{tpl.module_number}")
            continue
        d = since
        while d <= until:
            ext = external_id(tpl.id, d)
            index[ext] = (tpl.id, d.isoformat())
            d += timedelta(days=1)
    return index


# --- marker extraction ------------------------------------------------------


def cache_entries_from_tasks(
    tasks: list[dict[str, Any]],
    index: dict[str, tuple[str, str]],
    fallback_now_iso: str,
) -> tuple[dict[str, dict[str, Any]], int]:
    """Return (cache, unmatched_count). Later wins on duplicate external_ids."""
    out: dict[str, dict[str, Any]] = {}
    unmatched = 0
    for task in tasks:
        desc = task.get("description") or ""
        m = MARKER_RE.search(desc)
        if not m:
            continue
        ext_id = m.group(1)
        task_id = str(task.get("id", ""))
        if not task_id:
            continue
        created_at = (
            task.get("added_at")
            or task.get("completed_at")
            or fallback_now_iso
        )
        match = index.get(ext_id)
        if match is None:
            unmatched += 1
            logger.warning(
                "marker %s on task %s did not match any (template, date) "
                "in the search window — keeping with blank template_id/due_date",
                ext_id, task_id,
            )
            template_id = ""
            due_date_field = ""
        else:
            template_id, due_date_field = match
        out[ext_id] = {
            "todoist_task_id": task_id,
            "created_at": str(created_at),
            "template_id": template_id,
            "due_date": due_date_field,
        }
    return out, unmatched


# --- HTTP -------------------------------------------------------------------


def _headers(token: str) -> dict[str, str]:
    return {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
    }


def fetch_active_tasks(
    session: requests.Session, token: str, project_id: str, timeout: float
) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    params: dict[str, Any] = {"project_id": project_id}
    while True:
        resp = session.get(
            f"{API_ROOT}/tasks",
            params=params,
            headers=_headers(token),
            timeout=timeout,
        )
        if resp.status_code != 200:
            raise RuntimeError(
                f"GET /tasks {resp.status_code}: {resp.text[:200]}"
            )
        data = resp.json()
        results = data.get("results") if isinstance(data, dict) else data
        if results:
            out.extend(results)
        cursor = data.get("next_cursor") if isinstance(data, dict) else None
        if not cursor:
            break
        params = {"project_id": project_id, "cursor": cursor}
    return out


def fetch_completed_tasks(
    session: requests.Session,
    token: str,
    project_id: str,
    since: datetime,
    until: datetime,
    timeout: float,
    page_limit: int = DEFAULT_PAGE_LIMIT,
) -> list[dict[str, Any]]:
    """Calls the verified v1 endpoint shape: {"items": [...]} with id key 'id'."""
    out: list[dict[str, Any]] = []
    params: dict[str, Any] = {
        "since": since.isoformat(),
        "until": until.isoformat(),
        "project_id": project_id,
        "limit": page_limit,
    }
    url = f"{API_ROOT}{COMPLETION_PATH}"
    while True:
        resp = session.get(
            url, params=params, headers=_headers(token), timeout=timeout
        )
        if resp.status_code != 200:
            raise RuntimeError(
                f"GET {COMPLETION_PATH} {resp.status_code}: {resp.text[:200]}"
            )
        data = resp.json()
        items = data.get("items") if isinstance(data, dict) else None
        if isinstance(items, list):
            out.extend(items)
        cursor = data.get("next_cursor") if isinstance(data, dict) else None
        if not cursor:
            break
        params = dict(params)
        params["cursor"] = cursor
    return out


# --- entry point ------------------------------------------------------------


def _load_token() -> str:
    env = parse_env_file(REPO_ROOT / ".env")
    token = env.get("TODOIST_TOKEN", "")
    if not token:
        sys.stderr.write("TODOIST_TOKEN missing from .env\n")
        sys.exit(2)
    return token


def _load_project_id() -> str:
    with (REPO_ROOT / "config.yaml").open("r", encoding="utf-8") as f:
        raw = yaml.safe_load(f) or {}
    return str(raw["todoist"]["project_id"])


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Rebuild .task_cache.json from Todoist project markers."
    )
    parser.add_argument("--project-id", default=None)
    parser.add_argument(
        "--days",
        type=int,
        default=DEFAULT_WINDOW_DAYS,
        help=f"Reverse-search + completed-task window (default {DEFAULT_WINDOW_DAYS}).",
    )
    parser.add_argument(
        "--out",
        type=Path,
        default=REPO_ROOT / ".task_cache.rebuilt.json",
        help="Output path. Default keeps the live cache untouched.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print the resulting cache to stdout instead of writing.",
    )
    parser.add_argument(
        "--verbose", action="store_true", help="DEBUG-level logging."
    )
    args = parser.parse_args(argv)

    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )

    token = _load_token()
    project_id = args.project_id or _load_project_id()

    now = datetime.now(timezone.utc)
    since_dt = now - timedelta(days=args.days)
    since = since_dt.date()
    until = now.date()

    logger.info(
        "rebuild start: project=%s window=[%s, %s] (%d days)",
        project_id, since, until, args.days,
    )

    session = requests.Session()
    active = fetch_active_tasks(session, token, project_id, DEFAULT_TIMEOUT)
    logger.info("active tasks fetched: %d", len(active))
    completed = fetch_completed_tasks(
        session, token, project_id, since_dt, now, DEFAULT_TIMEOUT
    )
    logger.info("completed tasks fetched: %d", len(completed))

    index = build_external_id_index(TEMPLATES_DIR, since, until)
    logger.info("template index size: %d", len(index))

    fallback_iso = now.isoformat()
    cache_active, unmatched_active = cache_entries_from_tasks(
        active, index, fallback_iso
    )
    cache_completed, unmatched_completed = cache_entries_from_tasks(
        completed, index, fallback_iso
    )
    cache = {**cache_completed, **cache_active}  # active wins on collision
    unmatched = unmatched_active + unmatched_completed

    logger.info(
        "rebuilt: %d cache entries (%d unmatched markers; out=%s)",
        len(cache), unmatched, args.out,
    )

    payload = json.dumps(cache, indent=2, sort_keys=True) + "\n"
    if args.dry_run:
        sys.stdout.write(payload)
    else:
        args.out.write_text(payload, encoding="utf-8")

    return 0


if __name__ == "__main__":
    sys.exit(main())
