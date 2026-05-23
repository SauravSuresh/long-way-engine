"""Read-only Todoist client for the state-review phase.

Strictly isolated from `TodoistClient` (write) and `TodoistCompletionClient`
(completion-window read): own session, own retry helper, own headers
method, no shared private methods. The state-review phase only needs
three things from Todoist: a task's sub-tasks (id, content, completion),
the first comment on a task (for counter values), and resolution from
content-marker external_id to live task_id.

CODE REVIEW CHECK: any PR that adds a write method (POST/PATCH/DELETE)
to this client must be rejected. State mutations flow back to the user
through git commits to state.yaml + state_log.yaml, not through Todoist.
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass
from typing import Any

import requests

from src.todoist import (
    API_ROOT,
    DEFAULT_TIMEOUT,
    INITIAL_BACKOFF,
    MARKER_RE,
    MAX_RETRIES,
    TodoistAuthError,
    TodoistError,
)

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class Subtask:
    id: str
    content: str
    is_completed: bool
    comment_count: int
    parent_id: str


class TodoistReviewClient:
    def __init__(
        self,
        token: str,
        project_id: str,
        session: requests.Session | None = None,
        timeout: float = DEFAULT_TIMEOUT,
    ) -> None:
        self._review_token = token
        self._review_project_id = project_id
        self._review_http = session or requests.Session()
        self._review_timeout = timeout

    def get_subtasks(self, parent_task_id: str) -> list[Subtask]:
        """Return all sub-tasks under `parent_task_id`. Uses Todoist's
        `parent_id` filter on the tasks list endpoint, paginated.
        """
        params: dict[str, Any] = {"parent_id": str(parent_task_id)}
        url = f"{API_ROOT}/tasks"
        out: list[Subtask] = []
        while True:
            data = self._review_get_json(url, params=params)
            results = data.get("results") if isinstance(data, dict) else data
            if not results:
                break
            for task in results:
                out.append(
                    Subtask(
                        id=str(task.get("id", "")),
                        content=str(task.get("content", "")),
                        is_completed=bool(task.get("is_completed", task.get("checked", False))),
                        comment_count=int(task.get("comment_count", 0) or 0),
                        parent_id=str(task.get("parent_id", parent_task_id)),
                    )
                )
            cursor = data.get("next_cursor") if isinstance(data, dict) else None
            if not cursor:
                break
            params = {"parent_id": str(parent_task_id), "cursor": cursor}
        return out

    def get_first_comment(self, task_id: str) -> str | None:
        """Return the earliest comment's `content` on `task_id`, or None."""
        data = self._review_get_json(
            f"{API_ROOT}/comments",
            params={"task_id": str(task_id)},
        )
        items = data.get("results") if isinstance(data, dict) else data
        if not items:
            return None
        items_sorted = sorted(items, key=lambda c: str(c.get("posted_at", "")))
        first = items_sorted[0]
        content = first.get("content")
        return str(content) if content is not None else None

    def find_task_by_external_id(self, external_id: str) -> str | None:
        """Scan the project's open tasks for a content marker matching
        `external_id`. Returns the live task_id, or None if not found.

        Reads the same project-scoped task list TodoistClient does, but on
        a separate session.
        """
        url = f"{API_ROOT}/tasks"
        params: dict[str, Any] = {"project_id": self._review_project_id}
        while True:
            data = self._review_get_json(url, params=params)
            results = data.get("results") if isinstance(data, dict) else data
            if not results:
                break
            for task in results:
                desc = task.get("description") or ""
                m = MARKER_RE.search(desc)
                if m and m.group(1) == external_id:
                    return str(task.get("id", ""))
            cursor = data.get("next_cursor") if isinstance(data, dict) else None
            if not cursor:
                break
            params = {"project_id": self._review_project_id, "cursor": cursor}
        return None

    def _review_get_json(self, url: str, params: dict[str, Any]) -> Any:
        backoff = INITIAL_BACKOFF
        for attempt in range(1, MAX_RETRIES + 1):
            try:
                resp = self._review_http.get(
                    url,
                    params=params,
                    headers=self._review_headers(),
                    timeout=self._review_timeout,
                )
            except requests.RequestException as e:
                logger.warning(
                    "todoist review GET attempt %d/%d failed: %s",
                    attempt, MAX_RETRIES, e,
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
                    "todoist review GET attempt %d/%d returned %d",
                    attempt, MAX_RETRIES, resp.status_code,
                )
                if attempt == MAX_RETRIES:
                    raise TodoistError(
                        f"todoist 5xx after {MAX_RETRIES} attempts: {resp.status_code}"
                    )
                time.sleep(backoff)
                backoff *= 2
                continue
            if not resp.ok:
                raise TodoistError(
                    f"todoist review GET {resp.status_code}: {resp.text[:200]}"
                )
            return resp.json()
        raise TodoistError("todoist review retry loop exited without return")

    def _review_headers(self) -> dict[str, str]:
        return {
            "Authorization": f"Bearer {self._review_token}",
            "Content-Type": "application/json",
        }
