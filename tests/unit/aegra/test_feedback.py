"""Unit tests for Langfuse feedback recording and HTTP handler."""

from unittest.mock import MagicMock, patch

import pytest
from pydantic import ValidationError
from starlette.requests import Request
from starlette.testclient import TestClient

from deep_agent.aegra.feedback import app, feedback_handler, record_feedback


class TestRecordFeedback:
    def test_records_score_when_langfuse_configured(self):
        mock_client = MagicMock()
        payload = {
            "trace_id": "abcd1234" * 4,
            "name": "user-rating",
            "value": 1.0,
            "kwargs": {"comment": "great"},
        }

        with patch(
            "deep_agent.aegra.feedback.get_langfuse_client",
            return_value=mock_client,
        ):
            result = record_feedback(payload)

        assert result.status == "success"
        mock_client.score.assert_called_once_with(
            trace_id=payload["trace_id"],
            name="user-rating",
            value=1.0,
            comment="great",
        )

    def test_graceful_degradation_when_langfuse_unconfigured(self):
        payload = {
            "trace_id": "abcd1234" * 4,
            "name": "thumbs-up",
            "value": 1.0,
        }

        with patch(
            "deep_agent.aegra.feedback.get_langfuse_client",
            return_value=None,
        ):
            result = record_feedback(payload)

        assert result.status == "success"

    def test_validation_error_on_missing_fields(self):
        with pytest.raises(ValidationError):
            record_feedback({})

    def test_raises_runtime_error_when_score_fails(self):
        mock_client = MagicMock()
        mock_client.score.side_effect = RuntimeError("network")

        payload = {
            "trace_id": "abcd1234" * 4,
            "name": "user-rating",
            "value": 0.5,
        }

        with patch(
            "deep_agent.aegra.feedback.get_langfuse_client",
            return_value=mock_client,
        ):
            with pytest.raises(RuntimeError, match="Langfuse score submission failed"):
                record_feedback(payload)


class TestFeedbackHandler:
    @pytest.mark.asyncio
    async def test_validation_error_response_shape(self):
        scope = {
            "type": "http",
            "asgi": {"spec_version": "2.0", "version": "3.0"},
            "http_version": "1.1",
            "method": "POST",
            "scheme": "http",
            "path": "/feedback",
            "raw_path": b"/feedback",
            "root_path": "",
            "headers": [],
            "client": ("127.0.0.1", 12345),
            "server": ("127.0.0.1", 80),
        }

        async def receive():
            return {"type": "http.request", "body": b"{}", "more_body": False}

        request = Request(scope, receive)
        response = await feedback_handler(request)
        assert response.status_code == 422

    def test_post_feedback_via_test_client(self):
        client = TestClient(app)
        payload = {
            "trace_id": "a" * 32,
            "name": "user-rating",
            "value": 1.0,
        }
        with patch(
            "deep_agent.aegra.feedback.get_langfuse_client",
            return_value=None,
        ):
            res = client.post("/feedback", json=payload)
        assert res.status_code == 200
        assert res.json() == {"status": "success"}
