"""Agent factory for creating configured deep agent instances.

This module provides the factory function for creating fully-configured deep agents
with MCP tools, skills, subagents, backend, and checkpointer. It coordinates all
the pieces needed for agent initialization and returns a ready-to-use agent instance.

Functions:
    get_deep_agent: Create and configure a deep agent (async context manager)
"""

from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager
from typing import Any

from deepagents import create_deep_agent
from deepagents.backends import LocalShellBackend
from langgraph.graph.state import CompiledStateGraph

from deep_agent.src.agent.config import agent_config
from deep_agent.src.agent.llm import create_model
from deep_agent.src.exceptions import ConfigurationError
from deep_agent.src.infrastructure.backend import get_backend
from deep_agent.src.infrastructure.checkpointer import get_checkpointer
from deep_agent.src.infrastructure.mcp import get_mcp_tools
from deep_agent.src.infrastructure.subagents import load_subagents
from deep_agent.src.settings import settings
from deep_agent.utils.pylogger import get_python_logger

logger = get_python_logger(log_level=settings.PYTHON_LOG_LEVEL)


@asynccontextmanager
async def get_deep_agent(
    sso_token: str | None = None,
    refresh_token: str | None = None,
) -> AsyncGenerator[CompiledStateGraph, None]:
    """Get a fully initialized deep agent with MCP tools, skills, subagents, and memory.

    This function creates and configures a deep agent using the deepagents library
    with the necessary tools from MCP, skills, subagents, and memory. It uses an
    async context manager to ensure proper resource cleanup.

    Args:
        sso_token: Optional access token for authentication. If provided,
            it will be used for authorization headers in MCP client requests.
        refresh_token: Optional refresh token for downstream propagation.

    Yields:
        The initialized deep agent instance.

    Raises:
        ConfigurationError: If agent configuration is invalid.
        LLMError: If model creation fails.
        MCPError: If MCP tool loading fails critically.
    """
    try:
        orchestrator_cfg: dict[str, Any] = agent_config.get_orchestrator_config()
    except Exception as e:
        raise ConfigurationError(f"Failed to load orchestrator config: {e}") from e

    agent_name: str = orchestrator_cfg.get("name", "orchestrator")
    model_name: str = orchestrator_cfg.get("model", "gemini-3.1-pro-preview")
    system_prompt: str = orchestrator_cfg.get("body", "")
    skill_paths: list[str] = orchestrator_cfg.get("skill_paths", [])
    tool_names: list[str] = orchestrator_cfg.get("tools", [])

    logger.info(
        f"Initializing orchestrator agent '{agent_name}' with model: {model_name}"
    )

    model = create_model(model_name=model_name)

    if sso_token:
        from deep_agent.src.infrastructure.mcp import refresh_access_token

        sso_token = await refresh_access_token(sso_token, refresh_token)

    mcp_tools: list[Any] = await get_mcp_tools(sso_token=sso_token)

    tools: list[Any] = agent_config.resolve_tools(
        tool_names, mcp_tools, agent_name=agent_name
    )

    subagents = load_subagents(tools=mcp_tools)

    backend: LocalShellBackend = get_backend()

    async with get_checkpointer() as checkpointer:
        agent: CompiledStateGraph = create_deep_agent(
            name=agent_name,
            model=model,
            system_prompt=system_prompt,
            skills=skill_paths,
            tools=tools,
            subagents=subagents,
            backend=backend,
            checkpointer=checkpointer,
            store=None,
        )
        logger.info(f"Orchestrator agent '{agent_name}' initialized successfully")
        yield agent
