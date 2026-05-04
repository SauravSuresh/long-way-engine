import re
from datetime import date, datetime
from unittest.mock import MagicMock

import pytest
import requests
from zoneinfo import ZoneInfo

from src.clock import FrozenClock
from src.templates import ResolvedTemplate
from src.todoist import (
    MARKER_RE,
    TodoistAdminClient,
    TodoistAuthError,
    TodoistClient,
    TodoistError,
    append_marker,
    content_marker,
)

IST = ZoneInfo("Asia/Kolkata")


def make_template() -> ResolvedTemplate:
    return ResolvedTemplate(
        id="daily-anki",
        title="Anki review",
        description="10-15 min.",
        due="today at 08:30",
        labels=["daily-ritual"],
        cadence="daily",
        skip_if="sunday",
    )


def make_response(status_code: int = 200, json_body: dict | None = None) -> MagicMock:
    resp = MagicMock(spec=requests.Response)
    resp.status_code = status_code
    resp.ok = 200 <= status_code < 300
    resp.text = ""
    resp.json.return_value = json_body or {"id": "8901234567"}
    return resp


def make_client(session: MagicMock, dry_run: bool = False) -> TodoistClient:
    clock = FrozenClock(datetime(2026, 5, 4, 5, 30, tzinfo=IST), IST)
    return TodoistClient(
        token="t-xyz",
        project_id="p123",
        session=session,
        clock=clock,
        dry_run=dry_run,
    )


def test_marker_format_matches_regex():
    m = content_marker("a3f2b1c4d5e6f7a8")
    assert MARKER_RE.fullmatch(m)


def test_append_marker_to_empty_description():
    assert append_marker("", "a3f2b1c4d5e6f7a8") == "<!--LW:a3f2b1c4d5e6f7a8-->"


def test_append_marker_to_non_empty():
    out = append_marker("hello world", "a3f2b1c4d5e6f7a8")
    assert out.endswith("<!--LW:a3f2b1c4d5e6f7a8-->")
    assert "hello world" in out


def test_cache_hit_makes_zero_api_calls():
    session = MagicMock()
    client = make_client(session)
    cache = {
        "a3f2b1c4d5e6f7a8": {
            "todoist_task_id": "999",
            "created_at": "2026-05-04T03:00:00+00:00",
            "template_id": "daily-anki",
            "due_date": "2026-05-04",
        }
    }
    result = client.create_task_idempotent(
        make_template(), date(2026, 5, 4), "a3f2b1c4d5e6f7a8", cache
    )
    assert result.skipped is True
    assert result.todoist_task_id == "999"
    session.post.assert_not_called()


def test_cache_miss_posts_once_with_marker_in_description():
    session = MagicMock()
    session.post.return_value = make_response(200, {"id": "777"})
    client = make_client(session)

    result = client.create_task_idempotent(
        make_template(), date(2026, 5, 4), "a3f2b1c4d5e6f7a8", cache={}
    )

    assert session.post.call_count == 1
    _, kwargs = session.post.call_args
    body = kwargs["json"]
    assert body["project_id"] == "p123"
    assert body["content"] == "Anki review"
    assert "<!--LW:a3f2b1c4d5e6f7a8-->" in body["description"]
    assert body["due_string"] == "today at 08:30"
    assert body["labels"] == ["daily-ritual"]
    assert kwargs["headers"]["Authorization"] == "Bearer t-xyz"

    assert result.skipped is False
    assert result.todoist_task_id == "777"


def test_marker_regex_extracts_id_from_description():
    desc = append_marker("anything", "a3f2b1c4d5e6f7a8")
    match = MARKER_RE.search(desc)
    assert match is not None
    assert match.group(1) == "a3f2b1c4d5e6f7a8"


def test_5xx_retries_three_times_then_raises(monkeypatch):
    monkeypatch.setattr("src.todoist.time.sleep", lambda *_: None)
    session = MagicMock()
    session.post.return_value = make_response(503)
    client = make_client(session)

    with pytest.raises(TodoistError, match="5xx"):
        client.create_task_idempotent(
            make_template(), date(2026, 5, 4), "a1234567890abcde", cache={}
        )
    assert session.post.call_count == 3


def test_5xx_then_success_succeeds(monkeypatch):
    monkeypatch.setattr("src.todoist.time.sleep", lambda *_: None)
    session = MagicMock()
    session.post.side_effect = [
        make_response(500),
        make_response(200, {"id": "555"}),
    ]
    client = make_client(session)

    result = client.create_task_idempotent(
        make_template(), date(2026, 5, 4), "a1234567890abcde", cache={}
    )
    assert result.todoist_task_id == "555"
    assert session.post.call_count == 2


def test_401_raises_immediately_no_retry(monkeypatch):
    monkeypatch.setattr("src.todoist.time.sleep", lambda *_: None)
    session = MagicMock()
    session.post.return_value = make_response(401)
    client = make_client(session)

    with pytest.raises(TodoistAuthError):
        client.create_task_idempotent(
            make_template(), date(2026, 5, 4), "a1234567890abcde", cache={}
        )
    assert session.post.call_count == 1


def test_4xx_other_raises_without_retry(monkeypatch):
    monkeypatch.setattr("src.todoist.time.sleep", lambda *_: None)
    session = MagicMock()
    session.post.return_value = make_response(400)
    client = make_client(session)

    with pytest.raises(TodoistError):
        client.create_task_idempotent(
            make_template(), date(2026, 5, 4), "a1234567890abcde", cache={}
        )
    assert session.post.call_count == 1


def test_daily_client_has_no_destructive_methods():
    """Daily-run client may read for idempotency; must never PATCH/DELETE/etc."""
    forbidden = {
        "patch",
        "delete",
        "complete",
        "update",
        "delete_task",
        "list_tasks",
        "close_task",
    }
    public = {n for n in dir(TodoistClient) if not n.startswith("_")}
    leaked = public & forbidden
    assert not leaked, f"TodoistClient must stay write-only on task state; leaked {leaked}"


def test_dry_run_makes_zero_api_calls():
    session = MagicMock()
    client = make_client(session, dry_run=True)
    result = client.create_task_idempotent(
        make_template(), date(2026, 5, 4), "a1234567890abcde", cache={}
    )
    session.post.assert_not_called()
    assert result.skipped is False
    assert result.todoist_task_id == "DRY-RUN-a1234567890abcde"


def test_dry_run_logs_would_create(caplog):
    session = MagicMock()
    client = make_client(session, dry_run=True)
    with caplog.at_level("INFO", logger="src.todoist"):
        client.create_task_idempotent(
            make_template(), date(2026, 5, 4), "a1234567890abcde", cache={}
        )
    assert any("DRY RUN" in r.getMessage() for r in caplog.records)


def test_dry_run_still_honors_cache_hit():
    session = MagicMock()
    client = make_client(session, dry_run=True)
    cache = {
        "a1234567890abcde": {
            "todoist_task_id": "real-id-from-prior-run",
            "created_at": "2026-05-04T03:00:00+00:00",
            "template_id": "daily-anki",
            "due_date": "2026-05-04",
        }
    }
    result = client.create_task_idempotent(
        make_template(), date(2026, 5, 4), "a1234567890abcde", cache
    )
    assert result.skipped is True
    assert result.todoist_task_id == "real-id-from-prior-run"
    session.post.assert_not_called()


def test_created_at_uses_injected_clock():
    session = MagicMock()
    session.post.return_value = make_response(200, {"id": "777"})
    client = make_client(session)
    result = client.create_task_idempotent(
        make_template(), date(2026, 5, 4), "a1234567890abcde", cache={}
    )
    # FrozenClock is 2026-05-04 05:30 IST = 2026-05-04 00:00 UTC.
    assert result.created_at.startswith("2026-05-04T00:00:00")


def _list_response(*tasks_with_markers):
    """Build a {results, next_cursor} response with a marker per task."""
    results = []
    for i, ext_id in enumerate(tasks_with_markers):
        results.append(
            {
                "id": f"task-{i}",
                "content": "x",
                "description": f"body\n\n{content_marker(ext_id)}" if ext_id else "no marker",
            }
        )
    return make_response(200, {"results": results, "next_cursor": None})


def test_marker_dedup_skips_create_when_id_in_project():
    """Cache miss but marker exists in project -> rehydrate, no POST."""
    session = MagicMock()
    session.get.return_value = _list_response("a1234567890abcde")
    client = make_client(session)

    result = client.create_task_idempotent(
        make_template(), date(2026, 5, 4), "a1234567890abcde", cache={}
    )
    assert result.skipped is True
    assert result.todoist_task_id == "task-0"
    session.post.assert_not_called()
    assert session.get.call_count == 1


def test_marker_dedup_rehydrates_cache_on_hit():
    """When marker dedup hits, the supplied cache dict gains an entry."""
    session = MagicMock()
    session.get.return_value = _list_response("a1234567890abcde")
    client = make_client(session)
    cache: dict = {}

    client.create_task_idempotent(
        make_template(), date(2026, 5, 4), "a1234567890abcde", cache
    )
    assert "a1234567890abcde" in cache
    assert cache["a1234567890abcde"]["todoist_task_id"] == "task-0"
    assert cache["a1234567890abcde"]["template_id"] == "daily-anki"
    assert cache["a1234567890abcde"]["due_date"] == "2026-05-04"


def test_marker_dedup_creates_when_id_not_in_project():
    """Cache miss + marker absent -> normal POST."""
    session = MagicMock()
    session.get.return_value = _list_response("b234567890abcdef")
    session.post.return_value = make_response(200, {"id": "new-1"})
    client = make_client(session)

    result = client.create_task_idempotent(
        make_template(), date(2026, 5, 4), "a1234567890abcde", cache={}
    )
    assert result.skipped is False
    assert result.todoist_task_id == "new-1"
    assert session.get.call_count == 1
    assert session.post.call_count == 1


def test_marker_dedup_lazy_one_get_for_five_cache_misses():
    """5 templates, all cache-miss -> exactly 1 GET (memoization)."""
    session = MagicMock()
    session.get.return_value = _list_response()  # empty project
    session.post.return_value = make_response(200, {"id": "new"})
    client = make_client(session)

    for i in range(5):
        ext_id = f"{i:016x}"
        tpl = ResolvedTemplate(
            id=f"t-{i}",
            title=f"Title {i}",
            description="",
            due="",
            labels=[],
            cadence="daily",
            skip_if=None,
        )
        client.create_task_idempotent(tpl, date(2026, 5, 4), ext_id, cache={})

    assert session.get.call_count == 1, "marker fetch should be memoized"
    assert session.post.call_count == 5


def test_marker_dedup_handles_pagination():
    """Two pages of marker results both contribute to the dedup set."""
    session = MagicMock()
    page1 = make_response(
        200,
        {
            "results": [
                {"id": "t-0", "content": "x", "description": content_marker("aaaaaaaaaaaaaaaa")}
            ],
            "next_cursor": "cursor-2",
        },
    )
    page2 = make_response(
        200,
        {
            "results": [
                {"id": "t-1", "content": "x", "description": content_marker("bbbbbbbbbbbbbbbb")}
            ],
            "next_cursor": None,
        },
    )
    session.get.side_effect = [page1, page2]
    client = make_client(session)

    result = client.create_task_idempotent(
        make_template(), date(2026, 5, 4), "bbbbbbbbbbbbbbbb", cache={}
    )
    assert result.skipped is True
    assert result.todoist_task_id == "t-1"
    assert session.get.call_count == 2  # two pages, still one logical fetch
    session.post.assert_not_called()


def test_marker_dedup_skipped_when_cache_hits():
    """Cache hit -> never even fire the marker GET."""
    session = MagicMock()
    cache = {
        "a1234567890abcde": {
            "todoist_task_id": "999",
            "created_at": "2026-05-04T03:00:00+00:00",
            "template_id": "daily-anki",
            "due_date": "2026-05-04",
        }
    }
    client = make_client(session)
    result = client.create_task_idempotent(
        make_template(), date(2026, 5, 4), "a1234567890abcde", cache
    )
    assert result.skipped is True
    session.get.assert_not_called()
    session.post.assert_not_called()


# --- TodoistAdminClient -----------------------------------------------------


def test_admin_list_tasks_handles_paginated_response():
    session = MagicMock()
    page1 = make_response(
        200,
        {"results": [{"id": "1"}, {"id": "2"}], "next_cursor": "c2"},
    )
    page2 = make_response(200, {"results": [{"id": "3"}], "next_cursor": None})
    session.get.side_effect = [page1, page2]
    admin = TodoistAdminClient(token="t", session=session)
    out = admin.list_tasks("p123")
    assert [t["id"] for t in out] == ["1", "2", "3"]
    assert session.get.call_count == 2


def test_admin_delete_task_calls_delete_endpoint():
    session = MagicMock()
    resp = MagicMock(spec=requests.Response)
    resp.status_code = 204
    resp.ok = True
    resp.text = ""
    session.delete.return_value = resp
    admin = TodoistAdminClient(token="t", session=session)
    admin.delete_task("abc")
    assert session.delete.call_count == 1
    called_url = session.delete.call_args[0][0]
    assert called_url.endswith("/tasks/abc")


def test_admin_delete_raises_on_401():
    session = MagicMock()
    session.delete.return_value = make_response(401)
    admin = TodoistAdminClient(token="t", session=session)
    with pytest.raises(TodoistAuthError):
        admin.delete_task("abc")


def test_token_never_appears_in_logs(caplog, monkeypatch):
    monkeypatch.setattr("src.todoist.time.sleep", lambda *_: None)
    session = MagicMock()
    session.post.side_effect = requests.ConnectionError("boom")
    client = make_client(session)
    with caplog.at_level("WARNING"):
        with pytest.raises(TodoistError):
            client.create_task_idempotent(
                make_template(), date(2026, 5, 4), "a1234567890abcde", cache={}
            )
    for record in caplog.records:
        assert "t-xyz" not in record.getMessage()
