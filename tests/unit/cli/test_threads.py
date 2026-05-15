"""Unit tests for CLI thread HTTP helpers."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import httpx
import pytest

from deep_agent.cli import threads as threads_mod


def test_list_threads_parses_json_list() -> None:
    mock_resp = MagicMock()
    mock_resp.json.return_value = [
        {
            "thread_id": "t1",
            "created_at": "2025-01-01T00:00:00Z",
            "updated_at": "2025-01-01T01:00:00Z",
            "metadata": {},
        }
    ]
    mock_resp.raise_for_status = MagicMock()

    with patch.object(threads_mod.httpx, "get", return_value=mock_resp) as get_mock:
        out = threads_mod.list_threads("http://agent.test", {}, limit=5)

    get_mock.assert_called_once()
    call_kw = get_mock.call_args.kwargs
    assert call_kw["params"] == {"limit": 5}
    assert len(out) == 1
    assert out[0]["thread_id"] == "t1"


def test_list_threads_parses_wrapped_items() -> None:
    mock_resp = MagicMock()
    mock_resp.json.return_value = {
        "items": [{"thread_id": "a", "created_at": None}],
    }
    mock_resp.raise_for_status = MagicMock()

    with patch.object(threads_mod.httpx, "get", return_value=mock_resp):
        out = threads_mod.list_threads("http://agent.test", {})

    assert out == [{"thread_id": "a", "created_at": None}]


def test_get_thread_state_returns_dict() -> None:
    body = {"values": {"messages": []}, "tasks": []}
    mock_resp = MagicMock()
    mock_resp.json.return_value = body
    mock_resp.raise_for_status = MagicMock()

    with patch.object(threads_mod.httpx, "get", return_value=mock_resp) as get_mock:
        state = threads_mod.get_thread_state("http://agent.test", {}, "tid-1")

    get_mock.assert_called_once()
    assert get_mock.call_args.args[0] == "http://agent.test/threads/tid-1/state"
    assert state == body


def test_get_thread_state_non_object_raises() -> None:
    mock_resp = MagicMock()
    mock_resp.json.return_value = ["not", "a", "dict"]
    mock_resp.raise_for_status = MagicMock()

    with patch.object(threads_mod.httpx, "get", return_value=mock_resp):
        with pytest.raises(ValueError, match="JSON object"):
            threads_mod.get_thread_state("http://agent.test", {}, "x")


def test_delete_thread_success() -> None:
    mock_resp = MagicMock()
    mock_resp.raise_for_status = MagicMock()

    with patch.object(threads_mod.httpx, "delete", return_value=mock_resp) as del_mock:
        threads_mod.delete_thread("http://agent.test", {}, "to-delete")

    assert del_mock.call_args.args[0] == "http://agent.test/threads/to-delete"


def test_delete_thread_http_error() -> None:
    req = httpx.Request("DELETE", "http://agent.test/threads/x")
    err_resp = httpx.Response(404, request=req)
    mock_resp = MagicMock()
    mock_resp.raise_for_status.side_effect = httpx.HTTPStatusError(
        "not found", request=req, response=err_resp
    )

    with patch.object(threads_mod.httpx, "delete", return_value=mock_resp):
        with pytest.raises(httpx.HTTPStatusError):
            threads_mod.delete_thread("http://agent.test", {}, "x")
