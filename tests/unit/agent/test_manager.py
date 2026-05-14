"""Unit tests for AgentManager."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from deep_agent.src.agent.manager import AgentManager
from deep_agent.src.streaming import MessageDeduplicator, ToolCallTracker


@pytest.fixture
def agent_manager() -> AgentManager:
    """Fixture providing a fresh AgentManager instance."""
    return AgentManager()


class TestAgentManager:
    """Unit tests for AgentManager."""

    def test_manager_initialization(self, agent_manager: AgentManager):
        assert agent_manager.deduplicator is not None
        assert agent_manager.tracker is not None
        assert isinstance(agent_manager.deduplicator, MessageDeduplicator)
        assert isinstance(agent_manager.tracker, ToolCallTracker)

    def test_manager_has_all_handlers(self, agent_manager: AgentManager):
        assert "updates" in agent_manager.handlers
        assert "messages" in agent_manager.handlers

    def test_manager_with_sso_token(self):
        manager = AgentManager(redhat_sso_token="test_token_123")
        assert manager.redhat_sso_token == "test_token_123"

    def test_manager_with_refresh_token(self):
        manager = AgentManager(refresh_token="refresh_abc")
        assert manager.refresh_token == "refresh_abc"

    def test_manager_components_are_independent(self):
        m1 = AgentManager()
        m2 = AgentManager()
        assert m1.deduplicator is not m2.deduplicator
        assert m1.tracker is not m2.tracker

    def test_manager_handlers_are_configured(self, agent_manager: AgentManager):
        from deep_agent.src.streaming.handlers import (
            TokenEventHandler,
            UpdateEventHandler,
        )

        assert isinstance(agent_manager.handlers["updates"], UpdateEventHandler)
        assert isinstance(agent_manager.handlers["messages"], TokenEventHandler)

        updates_handler = agent_manager.handlers["updates"]
        assert updates_handler.deduplicator is agent_manager.deduplicator

        token_handler = agent_manager.handlers["messages"]
        assert token_handler.tracker is agent_manager.tracker

    def test_manager_without_sso_token(self):
        manager = AgentManager()
        assert manager.redhat_sso_token is None
        assert manager.refresh_token is None


class TestAgentManagerStreamResponse:
    """Tests for stream_response error handling."""

    @pytest.mark.asyncio
    async def test_stream_response_yields_error_on_exception(self):
        manager = AgentManager()

        mock_agent = AsyncMock()

        async def exploding_astream(*_args, **_kwargs):
            raise RuntimeError("agent exploded")
            if False:
                yield None

        mock_agent.astream = exploding_astream
        mock_agent.aget_state = AsyncMock(
            return_value=MagicMock(
                values={"messages": []},
                tasks=[],
            )
        )

        mock_ctx_manager = AsyncMock()
        mock_ctx_manager.__aenter__ = AsyncMock(return_value=mock_agent)
        mock_ctx_manager.__aexit__ = AsyncMock(return_value=False)

        from deep_agent.src.schema import StreamRequest

        request = StreamRequest(message="hello", thread_id="t1")

        with patch(
            "deep_agent.src.agent.manager.get_deep_agent",
            return_value=mock_ctx_manager,
        ):
            with patch(
                "deep_agent.src.agent.manager.create_langfuse_handler",
                return_value=None,
            ):
                events = []
                async for event in manager.stream_response(request):
                    events.append(event)

        assert len(events) == 2
        assert events[0]["type"] == "metadata"
        assert set(events[0]["content"].keys()) >= {"run_id", "trace_id", "thread_id"}
        assert events[1]["type"] == "error"
        assert "recoverable" in events[1]["content"]

    @pytest.mark.asyncio
    async def test_stream_response_yields_metadata_before_stream_events(self):
        manager = AgentManager()

        mock_agent = AsyncMock()

        async def empty_astream(*_args, **_kwargs):
            while False:
                yield None

        mock_agent.astream = empty_astream
        mock_agent.aget_state = AsyncMock(
            return_value=MagicMock(
                values={"messages": []},
                tasks=[],
            )
        )

        mock_ctx_manager = AsyncMock()
        mock_ctx_manager.__aenter__ = AsyncMock(return_value=mock_agent)
        mock_ctx_manager.__aexit__ = AsyncMock(return_value=False)

        from deep_agent.src.schema import StreamRequest

        request = StreamRequest(message="hello", thread_id="t-metadata")

        with patch(
            "deep_agent.src.agent.manager.get_deep_agent",
            return_value=mock_ctx_manager,
        ):
            with patch(
                "deep_agent.src.agent.manager.create_langfuse_handler",
                return_value=None,
            ):
                events = []
                async for event in manager.stream_response(request):
                    events.append(event)

        assert len(events) >= 1
        assert events[0]["type"] == "metadata"
        assert events[0]["content"]["thread_id"] == "t-metadata"
        assert "run_id" in events[0]["content"]
        assert "trace_id" in events[0]["content"]


class TestPrepareStream:
    """Tests for _prepare_stream configuration logic."""

    @pytest.mark.asyncio
    async def test_auto_generates_thread_id(self):
        manager = AgentManager()
        mock_agent = AsyncMock()
        mock_agent.aget_state = AsyncMock(
            return_value=MagicMock(values={"messages": []}, tasks=[])
        )

        from deep_agent.src.schema import StreamRequest

        request = StreamRequest(message="hi")

        with patch(
            "deep_agent.src.agent.manager.create_langfuse_handler",
            return_value=None,
        ):
            config, ctx = await manager._prepare_stream(request, mock_agent)

        assert ctx.thread_id is not None
        assert len(ctx.thread_id) > 0

    @pytest.mark.asyncio
    async def test_uses_provided_thread_id(self):
        manager = AgentManager()
        mock_agent = AsyncMock()
        mock_agent.aget_state = AsyncMock(
            return_value=MagicMock(values={"messages": []}, tasks=[])
        )

        from deep_agent.src.schema import StreamRequest

        request = StreamRequest(message="hi", thread_id="my-thread")

        with patch(
            "deep_agent.src.agent.manager.create_langfuse_handler",
            return_value=None,
        ):
            config, ctx = await manager._prepare_stream(request, mock_agent)

        assert ctx.thread_id == "my-thread"

    @pytest.mark.asyncio
    async def test_resume_on_interrupted_tasks(self):
        manager = AgentManager()
        mock_agent = AsyncMock()

        interrupted_task = MagicMock()
        interrupted_task.interrupts = [MagicMock(value="confirm?")]

        mock_agent.aget_state = AsyncMock(
            return_value=MagicMock(
                values={"messages": []},
                tasks=[interrupted_task],
            )
        )

        from deep_agent.src.schema import StreamRequest

        request = StreamRequest(message="yes", thread_id="t1")

        with patch(
            "deep_agent.src.agent.manager.create_langfuse_handler",
            return_value=None,
        ):
            config, ctx = await manager._prepare_stream(request, mock_agent)

        from langgraph.types import Command

        assert isinstance(config["input"], Command)
        assert config["input"].resume == "yes"
