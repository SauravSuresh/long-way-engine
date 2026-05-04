import re
from datetime import date
from unittest.mock import MagicMock

import pytest
import requests

from src.templates import ResolvedTemplate
from src.todoist import (
    MARKER_RE,
    TodoistAuthError,
    TodoistClient,
    TodoistError,
    append_marker,
    content_marker,
)


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


def make_client(session: MagicMock) -> TodoistClient:
    return TodoistClient(token="t-xyz", project_id="p123", session=session)


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
            make_template(), date(2026, 5, 4), "id1234567890abcd", cache={}
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
        make_template(), date(2026, 5, 4), "id1234567890abcd", cache={}
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
            make_template(), date(2026, 5, 4), "id1234567890abcd", cache={}
        )
    assert session.post.call_count == 1


def test_4xx_other_raises_without_retry(monkeypatch):
    monkeypatch.setattr("src.todoist.time.sleep", lambda *_: None)
    session = MagicMock()
    session.post.return_value = make_response(400)
    client = make_client(session)

    with pytest.raises(TodoistError):
        client.create_task_idempotent(
            make_template(), date(2026, 5, 4), "id1234567890abcd", cache={}
        )
    assert session.post.call_count == 1


def test_client_has_no_get_patch_or_delete_methods():
    """Phase A constraint: write-only. Read API arrives in Phase E."""
    forbidden = {"get", "patch", "delete", "complete", "update"}
    public = {n for n in dir(TodoistClient) if not n.startswith("_")}
    leaked = public & forbidden
    assert not leaked, f"TodoistClient must remain write-only; leaked {leaked}"


def test_token_never_appears_in_logs(caplog, monkeypatch):
    monkeypatch.setattr("src.todoist.time.sleep", lambda *_: None)
    session = MagicMock()
    session.post.side_effect = requests.ConnectionError("boom")
    client = make_client(session)
    with caplog.at_level("WARNING"):
        with pytest.raises(TodoistError):
            client.create_task_idempotent(
                make_template(), date(2026, 5, 4), "id1234567890abcd", cache={}
            )
    for record in caplog.records:
        assert "t-xyz" not in record.getMessage()
