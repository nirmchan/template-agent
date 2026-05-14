"""Unit tests for aegra telemetry module."""

import os
from unittest.mock import patch

import pytest

from deep_agent.aegra.telemetry import (
    LangfuseObservabilityProvider,
    _langfuse_configured,
    create_langfuse_handler,
    record_metric,
    trace_span,
)


class TestLangfuseConfigured:
    def test_false_when_no_keys(self):
        with patch.dict(os.environ, {}, clear=True):
            assert _langfuse_configured() is False

    def test_false_when_partial_keys(self):
        with patch.dict(os.environ, {"LANGFUSE_PUBLIC_KEY": "pk"}, clear=True):
            assert _langfuse_configured() is False

    def test_true_when_both_keys_present(self):
        with patch.dict(
            os.environ,
            {"LANGFUSE_PUBLIC_KEY": "pk", "LANGFUSE_SECRET_KEY": "sk"},
            clear=True,
        ):
            assert _langfuse_configured() is True


class TestCreateLangfuseHandler:
    def test_returns_none_when_unconfigured(self):
        with patch.dict(os.environ, {}, clear=True):
            result = create_langfuse_handler(session_id="s1", user_id="u1")
            assert result is None


class TestTraceSpan:
    def test_context_yields_dict(self):
        with trace_span("test.op") as ctx:
            assert "start_time" in ctx
            ctx["custom_key"] = "value"
        assert ctx["custom_key"] == "value"

    def test_context_on_exception(self):
        with pytest.raises(ValueError, match="boom"):
            with trace_span("test.fail") as ctx:
                raise ValueError("boom")


class TestRecordMetric:
    def test_does_not_raise(self):
        record_metric("test.counter", 1.0, {"env": "test"})

    def test_without_tags(self):
        record_metric("test.counter", 42.0)


class TestLangfuseObservabilityProvider:
    def test_get_callbacks_empty(self):
        provider = LangfuseObservabilityProvider()
        assert provider.get_callbacks() == []

    def test_get_metadata_with_identity(self):
        provider = LangfuseObservabilityProvider()
        meta = provider.get_metadata("run1", "thread1", user_identity="alice")
        assert meta["langfuse_user_id"] == "alice"
        assert meta["langfuse_session_id"] == "thread1"

    def test_get_metadata_without_identity(self):
        provider = LangfuseObservabilityProvider()
        meta = provider.get_metadata("run1", "thread1")
        assert "langfuse_user_id" not in meta
        assert meta["langfuse_session_id"] == "thread1"

    def test_is_enabled_follows_config(self):
        provider = LangfuseObservabilityProvider()
        with patch.dict(os.environ, {}, clear=True):
            assert provider.is_enabled() is False
