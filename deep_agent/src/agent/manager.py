"""Agent orchestration and streaming coordination.

This module provides the AgentManager class that coordinates agent execution
and manages the streaming response pipeline. It handles message routing,
streaming event processing, observability (Langfuse), and converts agent
outputs into API-friendly streaming formats.

Why this exists:
    Running an agent and streaming its responses involves many moving parts:
    checkpointer management, streaming event handling, deduplication, token
    tracking, and observability. AgentManager orchestrates all of this.

Classes:
    AgentManager: Manages agent execution and streaming pipeline coordination
"""

from collections.abc import AsyncGenerator
from typing import Any
from uuid import uuid4

from langchain_core.messages import HumanMessage
from langchain_core.runnables import RunnableConfig
from langgraph.graph.state import CompiledStateGraph
from langgraph.types import Command

from deep_agent.aegra.telemetry import create_langfuse_handler
from deep_agent.src.agent.factory import get_deep_agent
from deep_agent.src.error_handling import classify_error
from deep_agent.src.schema import StreamRequest
from deep_agent.src.settings import settings
from deep_agent.src.streaming import (
    MessageDeduplicator,
    StreamContext,
    TokenEventHandler,
    ToolCallTracker,
    UpdateEventHandler,
)
from deep_agent.utils.pylogger import get_python_logger

logger = get_python_logger(settings.PYTHON_LOG_LEVEL)


class AgentManager:
    """Manager class for handling agent operations and streaming responses.

    Orchestrates the streaming pipeline using modular components for:
    - Message deduplication across checkpoints
    - Tool call tracking for UI feedback
    - Event handling and formatting
    - Authentication and tracing
    """

    def __init__(
        self,
        redhat_sso_token: str | None = None,
        refresh_token: str | None = None,
    ) -> None:
        """Initialize the AgentManager.

        Args:
            redhat_sso_token: Optional SSO token for MCP authentication.
            refresh_token: Optional refresh token for downstream propagation.
        """
        self.redhat_sso_token = redhat_sso_token
        self.refresh_token = refresh_token

        self.deduplicator = MessageDeduplicator()
        self.tracker = ToolCallTracker()

        self.handlers: dict[str, UpdateEventHandler | TokenEventHandler] = {
            "updates": UpdateEventHandler(self.deduplicator),
            "messages": TokenEventHandler(self.tracker),
        }

    async def stream_response(
        self, request: StreamRequest
    ) -> AsyncGenerator[dict[str, Any], None]:
        """Stream agent response with simplified event structure.

        LangGraph automatically handles state persistence at the end of streaming.

        Args:
            request: The streaming request containing user input and configuration.

        Yields:
            Simplified event dictionaries with 'type' and 'content' fields.
        """
        async with get_deep_agent(self.redhat_sso_token, self.refresh_token) as agent:
            try:
                self.deduplicator.reset()
                self.tracker.reset()

                config, ctx = await self._prepare_stream(request, agent)

                logger.info(
                    f"Streaming response for run_id={ctx.run_id}, thread_id={ctx.thread_id}"
                )

                async for stream_event in agent.astream(
                    **config, stream_mode=["updates", "messages"]
                ):
                    if not isinstance(stream_event, tuple):
                        continue

                    stream_mode, event = stream_event

                    self.tracker.update_from_stream_event(stream_mode, event)

                    handler = self.handlers.get(stream_mode)
                    if not handler:
                        continue

                    formatted_events = handler.handle(event, ctx)
                    for formatted_event in formatted_events:
                        if formatted_event:
                            yield formatted_event

                logger.info(f"Conversation auto-saved for thread {ctx.thread_id}")

            except Exception as e:
                logger.error(f"Error in stream_response: {e}", exc_info=True)
                yield {"type": "error", "content": classify_error(e)}

    async def _prepare_stream(
        self, request: StreamRequest, agent: CompiledStateGraph
    ) -> tuple[dict[str, Any], StreamContext]:
        """Prepare streaming configuration and context.

        Args:
            request: The stream request.
            agent: The compiled agent graph instance.

        Returns:
            Tuple of (config dict for astream, StreamContext).
        """
        run_id: str = uuid4().hex
        trace_id: str = uuid4().hex

        effective_thread_id: str = request.thread_id or uuid4().hex
        effective_session_id: str = request.session_id or uuid4().hex
        effective_user_id: str = request.user_id or "anonymous"

        if not request.thread_id:
            logger.info(f"Auto-generated thread_id: {effective_thread_id}")
        if not request.session_id:
            logger.info(f"Auto-generated session_id: {effective_session_id}")
        if not request.user_id:
            logger.info("No user_id provided, using 'anonymous'")

        callbacks: list[Any] = []

        langfuse_handler = create_langfuse_handler(
            session_id=effective_session_id,
            user_id=effective_user_id,
            tags=["template-agent"],
        )
        if langfuse_handler:
            callbacks.append(langfuse_handler)

        config = RunnableConfig(
            configurable={
                "thread_id": effective_thread_id,
                "user_id": effective_user_id,
                "session_id": effective_session_id,
                "run_id": run_id,
                "trace_id": trace_id,
            },
            run_id=run_id,
            run_name="template-agent",
            callbacks=callbacks,
            metadata={
                "run_id": run_id,
                "trace_id": trace_id,
                "langfuse_user_id": effective_user_id,
                "langfuse_session_id": effective_session_id,
            },
        )

        state = await agent.aget_state(config=config)
        self.deduplicator.populate_from_history(state.values.get("messages", []))

        interrupted_tasks = [
            task
            for task in state.tasks
            if hasattr(task, "interrupts") and task.interrupts
        ]

        user_input: Command | dict[str, Any]
        if interrupted_tasks:
            user_input = Command(resume=request.message)
        else:
            user_input = {"messages": [HumanMessage(content=request.message)]}

        logger.info(
            f"Configured run_id={run_id}, thread_id={effective_thread_id}, session_id={effective_session_id}"
        )

        ctx = StreamContext(
            run_id=run_id,
            trace_id=trace_id,
            thread_id=effective_thread_id,
            session_id=effective_session_id,
            user_id=effective_user_id,
            stream_tokens=request.stream_tokens,
        )

        return {"input": user_input, "config": config}, ctx
