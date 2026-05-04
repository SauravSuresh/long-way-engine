"""Todoist REST API v2 client.

PHASE A IS WRITE-ONLY. The client exposes only `create_task_idempotent`.
The read-only completion API (`get_completion_status`) lands in Phase E
and must remain strictly separated from this write path -- no shared
helper that could accidentally issue a POST/PATCH/DELETE from the read
side, no shared retry wrapper that bridges read and write.

CODE REVIEW CHECK: any PR that adds a POST/PATCH/DELETE method to this
module outside `create_task_idempotent` must be rejected.
"""

from __future__ import annotations

import logging
import re
import time
from dataclasses import dataclass
from datetime import date, datetime, timezone
from typing import Any

import requests

from src.templates import ResolvedTemplate

logger = logging.getLogger(__name__)

API_ROOT = "https://api.todoist.com/rest/v2"
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
    ) -> None:
        self._token = token
        self._project_id = project_id
        self._session = session or requests.Session()
        self._timeout = timeout

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

        body: dict[str, Any] = {
            "content": template.title,
            "description": append_marker(template.description, external_id),
            "project_id": self._project_id,
        }
        if template.due:
            body["due_string"] = template.due
        if template.labels:
            body["labels"] = list(template.labels)

        created = self._post_with_retry("/tasks", body)
        created_at = datetime.now(timezone.utc).isoformat()
        return CreateResult(
            external_id=external_id,
            todoist_task_id=str(created["id"]),
            template_id=template.id,
            due_date=due_date,
            created_at=created_at,
            skipped=False,
        )

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
