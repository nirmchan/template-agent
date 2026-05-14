"""Graph factory for Aegra deployment.

This module exports an **async graph factory** that Aegra invokes
**per-request**.  The factory extracts the calling user's SSO token
from the ``ServerRuntime`` and passes it to MCP servers, so tool
calls are authenticated end-to-end with the user's own credentials.

``aegra.json`` references this as::

    "graphs": {"agent": "./deep_agent/aegra/graph.py:agent"}

Aegra detects the ``ServerRuntime`` parameter and classifies
``agent`` as a 1-param runtime factory.  On each request:

1. The auth handler validates the JWT and stores ``access_token``
   and ``refresh_token`` on the ``User`` model.
2. Aegra builds a ``ServerRuntime(user=user, …)`` and calls
   ``agent(runtime)`` → coroutine → ``await``-ed → compiled graph.
3. The graph is injected with Aegra's Postgres checkpointer/store
   before being used for the run.

For schema-only calls (LangGraph Studio, assistant listing) the
factory is invoked with ``user=None``; MCP tools are skipped and
the graph is built with only built-in tools.

Aegra automatically provides:

- Postgres-backed checkpointer (conversation persistence)
- Thread/run/assistant management API
- SSE streaming endpoint
- Worker architecture with Redis job queue
"""

import os
import sys
from pathlib import Path
from typing import Any

from langgraph_sdk.runtime import ServerRuntime

from deep_agent.utils.pylogger import get_python_logger

logger = get_python_logger()

_REPO_ROOT = Path(__file__).resolve().parent.parent

if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

os.environ.setdefault("PYTHONPATH", str(_REPO_ROOT))

from deep_agent.aegra.telemetry import setup_langfuse_tracing  # noqa: E402

setup_langfuse_tracing()


async def agent(runtime: ServerRuntime) -> Any:
    """Async graph factory — invoked per-request by Aegra.

    Extracts the user's SSO token from the runtime and forwards it
    to MCP servers so external tool calls carry the user's identity.

    When ``runtime.user`` is ``None`` (schema-extraction calls), MCP
    tools are skipped and the graph is built with built-in tools only.

    Args:
        runtime: Aegra ``ServerRuntime`` containing the authenticated
            ``User`` with ``access_token`` / ``refresh_token`` extras.

    Returns:
        A compiled deep-agent graph (``CompiledStateGraph``).
    """
    from deepagents import create_deep_agent

    from deep_agent.src.agent.config import agent_config
    from deep_agent.src.cache.model_cache import get_or_create_model
    from deep_agent.src.infrastructure.backend import get_backend
    from deep_agent.src.infrastructure.mcp import get_mcp_tools, refresh_access_token
    from deep_agent.src.infrastructure.subagents import load_subagents

    user = getattr(runtime, "user", None)
    sso_token = getattr(user, "access_token", None) if user else None
    refresh_token = getattr(user, "refresh_token", None) if user else None

    if sso_token:
        sso_token = await refresh_access_token(sso_token, refresh_token)

    orchestrator_cfg = agent_config.get_orchestrator_config()
    agent_name = orchestrator_cfg.get("name", "orchestrator")
    model_name = orchestrator_cfg.get("model", "gemini-3.1-pro-preview")
    system_prompt = orchestrator_cfg.get("body", "")
    skill_paths = orchestrator_cfg.get("skill_paths", [])
    tool_names = orchestrator_cfg.get("tools", [])

    user_identity = getattr(user, "identity", None) if user else None
    if user_identity:
        try:
            from deep_agent.src.cache.personalization_cache import (
                get_personalization,
                set_personalization,
            )
            from deep_agent.src.memory.config import memory_settings
            from deep_agent.src.personalization.injector import inject_personalization
            from deep_agent.src.personalization.repository import (
                PersonalizationRepository,
            )
            from deep_agent.src.settings import settings as app_settings

            cached = await get_personalization(user_identity)
            if cached is not None:
                mem_contents = [m["content"] for m in cached[0]]
                rule_contents = [r["content"] for r in cached[1]]
            else:
                repo = PersonalizationRepository(app_settings.database_uri)
                max_inject = memory_settings.MEMORY_MAX_INJECT
                memories = await repo.list_top_memories(user_identity, limit=max_inject)
                rules = await repo.list_rules(user_identity, active_only=True)
                mem_contents = [m.content for m in memories]
                rule_contents = [r.content for r in rules]
                await set_personalization(
                    user_identity,
                    [{"content": m.content} for m in memories],
                    [{"content": r.content} for r in rules],
                )

            system_prompt = inject_personalization(
                system_prompt,
                mem_contents,
                rule_contents,
            )
            if mem_contents or rule_contents:
                logger.info(
                    "Personalization injected: %d memories, %d rules",
                    len(mem_contents),
                    len(rule_contents),
                )
        except Exception:
            logger.debug(
                "Personalization unavailable, continuing without", exc_info=True
            )

    logger.info(
        "Building agent '%s' (model=%s, mcp_auth=%s)",
        agent_name,
        model_name,
        bool(sso_token),
    )

    model = get_or_create_model(model_name=model_name)
    mcp_tools = await get_mcp_tools(sso_token=sso_token)
    tools = agent_config.resolve_tools(tool_names, mcp_tools, agent_name=agent_name)
    subagents = load_subagents(tools=mcp_tools)
    backend = get_backend()

    compiled = create_deep_agent(
        name=agent_name,
        model=model,
        system_prompt=system_prompt,
        skills=skill_paths,
        tools=tools,
        subagents=subagents,
        backend=backend,
    )

    tool_count = len(tools)
    sub_count = len(subagents) if subagents else 0
    logger.info(
        "Agent ready: %d tool(s), %d subagent(s), mcp_auth=%s",
        tool_count,
        sub_count,
        bool(sso_token),
    )

    return compiled
