"""LangChain middleware for OTEL conversation lifecycle metrics."""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from typing import Any

from langchain.agents.middleware.types import (
    AgentMiddleware,
    ModelRequest,
    ModelResponse,
)

from deep_agent.aegra.otel import (
    record_conversation_completed,
    record_conversation_started,
    record_message_sent,
)


class OtelMiddleware(AgentMiddleware):
    """Record OTEL metrics for LLM model call lifecycle."""

    def _record_call(
        self,
        start_mono: float,
        *,
        status: str = "completed",
    ) -> None:
        record_message_sent(direction="received", message_type="human")
        record_conversation_completed(start_mono, status=status)
        record_message_sent(direction="sent", message_type="ai")

    def wrap_model_call(
        self,
        request: ModelRequest[Any],
        handler: Callable[[ModelRequest[Any]], ModelResponse[Any]],
    ) -> ModelResponse[Any]:
        """Sync model call wrapper for conversation metrics."""
        start_mono = record_conversation_started()
        try:
            response = handler(request)
        except Exception:
            record_conversation_completed(start_mono, status="error")
            raise
        self._record_call(start_mono)
        return response

    async def awrap_model_call(
        self,
        request: ModelRequest[Any],
        handler: Callable[[ModelRequest[Any]], Awaitable[ModelResponse[Any]]],
    ) -> ModelResponse[Any]:
        """Async model call wrapper for conversation metrics."""
        start_mono = record_conversation_started()
        try:
            response = await handler(request)
        except Exception:
            record_conversation_completed(start_mono, status="error")
            raise
        self._record_call(start_mono)
        return response
