"""Phase F item 1: live-probe the v1 /tasks/completed/by_completion_date endpoint.

READ-ONLY. This script issues exactly one HTTP method — GET — and never
writes to Todoist or to local state. The audit pattern is:

    grep -nE 'requests\\.(post|patch|delete|put)' scripts/probe_completion.py
    # must return zero matches

Any future change that adds a write method must be rejected at review.

Usage:

    python scripts/probe_completion.py [--project-id ID] [--days N]

Loads TODOIST_TOKEN from .env (same loader as src.config). Prints the raw
JSON response, then a one-line summary identifying the response shape
(top-level keys, where the items list lives, first item's keys). Exits
non-zero on any non-200 status with the status code and body.
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

import requests
import yaml

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))

from src.config import parse_env_file  # noqa: E402

API_ROOT = "https://api.todoist.com/api/v1"
COMPLETION_PATH = "/tasks/completed/by_completion_date"
DEFAULT_WINDOW_DAYS = 30


def _load_token() -> str:
    env = parse_env_file(REPO_ROOT / ".env")
    token = env.get("TODOIST_TOKEN", "")
    if not token:
        sys.stderr.write("TODOIST_TOKEN missing from .env\n")
        sys.exit(2)
    return token


def _load_project_id_from_config() -> str:
    with (REPO_ROOT / "config.yaml").open("r", encoding="utf-8") as f:
        raw = yaml.safe_load(f) or {}
    return str(raw["todoist"]["project_id"])


def _summarize(data: object) -> str:
    if not isinstance(data, dict):
        kind = type(data).__name__
        return f"top-level: not a dict ({kind})"
    top_keys = sorted(data.keys())
    list_key = None
    for k in ("items", "results", "tasks", "completed_tasks"):
        if isinstance(data.get(k), list):
            list_key = k
            break
    parts = [f"top-level keys: {top_keys}"]
    if list_key is None:
        parts.append("no list-valued top-level key found")
    else:
        items = data[list_key]
        parts.append(f"items at key '{list_key}': {len(items)}")
        if items:
            first = items[0]
            if isinstance(first, dict):
                parts.append(f"first item keys: {sorted(first.keys())}")
            else:
                parts.append(f"first item type: {type(first).__name__}")
    return "; ".join(parts)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Probe Todoist completed-tasks endpoint.")
    parser.add_argument(
        "--project-id",
        default=None,
        help="Override config.yaml todoist.project_id.",
    )
    parser.add_argument(
        "--days",
        type=int,
        default=DEFAULT_WINDOW_DAYS,
        help=f"Window length in days (default {DEFAULT_WINDOW_DAYS}).",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=50,
        help="Per-page limit (default 50).",
    )
    args = parser.parse_args(argv)

    token = _load_token()
    project_id = args.project_id or _load_project_id_from_config()

    until = datetime.now(timezone.utc)
    since = until - timedelta(days=args.days)
    params = {
        "since": since.isoformat(),
        "until": until.isoformat(),
        "project_id": project_id,
        "limit": args.limit,
    }

    url = f"{API_ROOT}{COMPLETION_PATH}"
    print(f"GET {url}")
    print(f"  project_id = {project_id}")
    print(f"  since      = {params['since']}")
    print(f"  until      = {params['until']}")
    print(f"  limit      = {params['limit']}")
    print()

    resp = requests.get(
        url,
        params=params,
        headers={
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
        },
        timeout=30,
    )

    if resp.status_code != 200:
        sys.stderr.write(
            f"non-200 from Todoist: {resp.status_code}\n"
            f"body: {resp.text[:500]}\n"
        )
        return 1

    try:
        data = resp.json()
    except ValueError as e:
        sys.stderr.write(f"response not JSON: {e}\nbody: {resp.text[:500]}\n")
        return 1

    print("--- raw response (pretty-printed) ---")
    print(json.dumps(data, indent=2, sort_keys=True, default=str))
    print()
    print("--- summary ---")
    print(_summarize(data))
    return 0


if __name__ == "__main__":
    sys.exit(main())
