"""Todoist API client.

DESIGN CONSTRAINT (amended 2026-05-04 from the original "write-only"):
The daily-run client (`TodoistClient`) is write-only on TASK STATE.
Idempotency reads are permitted: a single GET to list project tasks and
parse content markers, used as the second dedup layer when the local
cache misses. No PATCH, no DELETE, no POST outside `create_task_idempotent`.
The read-only completion API (`get_completion_status`) lands in Phase E
and must still be kept strictly separated from create_task_idempotent.

Destructive operations (DELETE) live on `TodoistAdminClient`, a separate
class invoked only by the explicit `--cleanup-project` CLI subcommand.
The daily-run code path never references it.

CODE REVIEW CHECK: any PR that adds a POST/PATCH/DELETE method to
`TodoistClient` outside `create_task_idempotent` must be rejected.
"""

from __future__ import annotations

import logging
import re
import time
from dataclasses import dataclass
from datetime import date, timezone
from typing import Any
from zoneinfo import ZoneInfo

import requests

from src.clock import Clock
from src.templates import ResolvedTemplate

logger = logging.getLogger(__name__)

API_ROOT = "https://api.todoist.com/api/v1"
MARKER_PREFIX = "<!--LW:"
MARKER_SUFFIX = "-->"
MARKER_RE = re.compile(r"<!--LW:([0-9a-f]{16})-->")

DEFAULT_TIMEOUT = 30
MAX_RETRIES = 3
INITIAL_BACKOFF = 1.0


def content_marker(external_id: str) -> str:
    return f"{MARKER_PREFIX}{external_id}{MARKER_SUFFIX}"


def append_marker(description: str, external_id: str) -> str:
    """Append the content marker to a description on its own line."""
    marker = content_marker(external_id)
    if description:
        return f"{description.rstrip()}\n\n{marker}"
    return marker


@dataclass
class CreateResult:
    external_id: str
    todoist_task_id: str
    template_id: str
    due_date: date
    created_at: str
    skipped: bool = False


class TodoistError(RuntimeError):
    pass


class TodoistAuthError(TodoistError):
    pass


class TodoistClient:
    """Write-only Todoist client. See module docstring."""

    def __init__(
        self,
        token: str,
        project_id: str,
        session: requests.Session | None = None,
        timeout: float = DEFAULT_TIMEOUT,
        clock: Clock | None = None,
        dry_run: bool = False,
    ) -> None:
        self._token = token
        self._project_id = project_id
        self._session = session or requests.Session()
        self._timeout = timeout
        self._clock = clock or Clock(ZoneInfo("UTC"))
        self._dry_run = dry_run
        # Lazy memoization for the marker-dedup read: at most one GET per run.
        self._marker_ids: set[str] | None = None
        self._marker_to_task_id: dict[str, str] = {}

    def create_task_idempotent(
        self,
        template: ResolvedTemplate,
        due_date: date,
        external_id: str,
        cache: dict[str, dict[str, Any]],
    ) -> CreateResult:
        """Create a task, or return a CreateResult marked skipped on cache hit.

        The cache is consulted first as the fast path. The marker is
        appended to every created task's description as a safety net for
        future cache reconstruction.
        """
        cached = cache.get(external_id)
        if cached:
            logger.info(
                "cache hit for %s (template=%s due=%s); skipping create",
                external_id,
                template.id,
                due_date.isoformat(),
            )
            return CreateResult(
                external_id=external_id,
                todoist_task_id=str(cached["todoist_task_id"]),
                template_id=template.id,
                due_date=due_date,
                created_at=str(cached.get("created_at", "")),
                skipped=True,
            )

        # Cache miss: consult the marker dedup layer (lazy single GET).
        if external_id in self._existing_external_ids():
            existing_id = self._marker_to_task_id[external_id]
            logger.info(
                "marker hit for %s (template=%s); rehydrating cache from task %s",
                external_id,
                template.id,
                existing_id,
            )
            return CreateResult(
                external_id=external_id,
                todoist_task_id=existing_id,
                template_id=template.id,
                due_date=due_date,
                created_at=self._clock.now().astimezone(timezone.utc).isoformat(),
                skipped=True,
            )

        body: dict[str, Any] = {
            "content": template.title,
            "description": append_marker(template.description, external_id),
            "project_id": self._project_id,
        }
        if template.due:
            body["due_string"] = template.due
        if template.labels:
            body["labels"] = list(template.labels)

        created_at = self._clock.now().astimezone(timezone.utc).isoformat()

        if self._dry_run:
            logger.info("DRY RUN: would create %s", template.title)
            return CreateResult(
                external_id=external_id,
                todoist_task_id=f"DRY-RUN-{external_id}",
                template_id=template.id,
                due_date=due_date,
                created_at=created_at,
                skipped=False,
            )

        created = self._post_with_retry("/tasks", body)
        return CreateResult(
            external_id=external_id,
            todoist_task_id=str(created["id"]),
            template_id=template.id,
            due_date=due_date,
            created_at=created_at,
            skipped=False,
        )

    def _existing_external_ids(self) -> set[str]:
        """Lazy-load and memoize the set of marker ids already in the project.

        At most one logical fetch per client instance (i.e. per run). May
        issue multiple GETs internally if the project is paginated.
        """
        if self._marker_ids is not None:
            return self._marker_ids
        ids, mapping = self._fetch_marker_ids()
        self._marker_ids = ids
        self._marker_to_task_id = mapping
        logger.info(
            "marker dedup: project %s has %d existing marker(s)",
            self._project_id,
            len(ids),
        )
        return ids

    def _fetch_marker_ids(self) -> tuple[set[str], dict[str, str]]:
        """GET project tasks (paginated), parse markers, return (ids, id->task_id)."""
        ids: set[str] = set()
        mapping: dict[str, str] = {}
        url = f"{API_ROOT}/tasks"
        params: dict[str, str] = {"project_id": self._project_id}
        while True:
            data = self._get_json(url, params=params)
            results = data.get("results") if isinstance(data, dict) else data
            if results is None:
                break
            for task in results:
                desc = task.get("description") or ""
                m = MARKER_RE.search(desc)
                if not m:
                    continue
                ext_id = m.group(1)
                ids.add(ext_id)
                mapping.setdefault(ext_id, str(task.get("id", "")))
            cursor = data.get("next_cursor") if isinstance(data, dict) else None
            if not cursor:
                break
            params = {"project_id": self._project_id, "cursor": cursor}
        return ids, mapping

    def _get_json(self, url: str, params: dict[str, Any]) -> dict[str, Any] | list[Any]:
        resp = self._session.get(
            url, params=params, headers=self._headers(), timeout=self._timeout
        )
        if resp.status_code == 401:
            raise TodoistAuthError("todoist 401 unauthorized; check TODOIST_TOKEN")
        if not resp.ok:
            raise TodoistError(f"todoist GET {resp.status_code}: {resp.text[:200]}")
        return resp.json()

    def _headers(self) -> dict[str, str]:
        return {
            "Authorization": f"Bearer {self._token}",
            "Content-Type": "application/json",
        }

    def _post_with_retry(self, path: str, body: dict[str, Any]) -> dict[str, Any]:
        url = f"{API_ROOT}{path}"
        backoff = INITIAL_BACKOFF
        last_exc: Exception | None = None
        for attempt in range(1, MAX_RETRIES + 1):
            try:
                resp = self._session.post(
                    url,
                    json=body,
                    headers=self._headers(),
                    timeout=self._timeout,
                )
            except requests.RequestException as e:
                last_exc = e
                logger.warning(
                    "todoist POST %s attempt %d/%d failed: %s",
                    path,
                    attempt,
                    MAX_RETRIES,
                    e,
                )
                if attempt == MAX_RETRIES:
                    raise TodoistError(f"network error after {MAX_RETRIES} attempts") from e
                time.sleep(backoff)
                backoff *= 2
                continue

            if resp.status_code == 401:
                raise TodoistAuthError("todoist 401 unauthorized; check TODOIST_TOKEN")
            if 500 <= resp.status_code < 600:
                logger.warning(
                    "todoist POST %s attempt %d/%d returned %d",
                    path,
                    attempt,
                    MAX_RETRIES,
                    resp.status_code,
                )
                if attempt == MAX_RETRIES:
                    raise TodoistError(
                        f"todoist 5xx after {MAX_RETRIES} attempts: {resp.status_code}"
                    )
                time.sleep(backoff)
                backoff *= 2
                continue
            if not resp.ok:
                raise TodoistError(f"todoist {resp.status_code}: {resp.text[:200]}")
            return resp.json()
        # Unreachable: every path above either returns or raises.
        raise TodoistError("todoist retry loop exited without return") from last_exc



class TodoistAdminClient:
    """Destructive operations: list + delete tasks. Used only by --cleanup-project.

    Kept on a separate class from TodoistClient so the daily-run code path
    has no way to issue a DELETE by accident. No retry wrapper is shared
    with TodoistClient.
    """

    def __init__(
        self,
        token: str,
        session: requests.Session | None = None,
        timeout: float = DEFAULT_TIMEOUT,
    ) -> None:
        self._token = token
        self._session = session or requests.Session()
        self._timeout = timeout

    def list_tasks(self, project_id: str) -> list[dict[str, Any]]:
        """Return all tasks in the given project (paginated)."""
        out: list[dict[str, Any]] = []
        params: dict[str, str] = {"project_id": project_id}
        while True:
            resp = self._session.get(
                f"{API_ROOT}/tasks",
                params=params,
                headers=self._headers(),
                timeout=self._timeout,
            )
            if resp.status_code == 401:
                raise TodoistAuthError("todoist 401 unauthorized; check TODOIST_TOKEN")
            if not resp.ok:
                raise TodoistError(f"todoist GET {resp.status_code}: {resp.text[:200]}")
            data = resp.json()
            results = data.get("results") if isinstance(data, dict) else data
            if results:
                out.extend(results)
            cursor = data.get("next_cursor") if isinstance(data, dict) else None
            if not cursor:
                break
            params = {"project_id": project_id, "cursor": cursor}
        return out

    def delete_task(self, task_id: str) -> None:
        resp = self._session.delete(
            f"{API_ROOT}/tasks/{task_id}",
            headers=self._headers(),
            timeout=self._timeout,
        )
        if resp.status_code == 401:
            raise TodoistAuthError("todoist 401 unauthorized; check TODOIST_TOKEN")
        if resp.status_code not in (200, 204):
            raise TodoistError(
                f"todoist DELETE /tasks/{task_id} {resp.status_code}: {resp.text[:200]}"
            )

    def _headers(self) -> dict[str, str]:
        return {
            "Authorization": f"Bearer {self._token}",
            "Content-Type": "application/json",
        }
