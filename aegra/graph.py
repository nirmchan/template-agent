"""Graph entry point for LangGraph Platform (aegra) deployment.

This module builds and exports the compiled agent graph that
``langgraph.json`` references. When served via ``langgraph dev`` or
``langgraph up``, the LangGraph Platform imports ``agent`` from this
module and exposes it through the standard LangGraph API.

The exported graph is fully compatible with deep-agents-ui.

Usage via CLI::

    langgraph dev          # local dev server (no Docker)
    langgraph up           # Docker-based server

The platform automatically provides:
- Postgres-backed checkpointer (conversation persistence)
- Thread/run/assistant management API
- SSE streaming endpoint
- Studio UI integration
"""

import asyncio
import logging
import os
import sys
from pathlib import Path

logger = logging.getLogger(__name__)

_REPO_ROOT = Path(__file__).resolve().parent.parent

# Ensure repo root is on sys.path so deep_agent can be imported
# when langgraph loads this module outside the normal app context.
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

os.environ.setdefault("PYTHONPATH", str(_REPO_ROOT))


def _load_mcp_tools_sync() -> list:
    """Load MCP tools synchronously for module-level graph construction.

    Falls back to an empty list if MCP servers are unreachable, allowing
    the agent to start in degraded mode (no external tool access).
    """
    from deep_agent.src.infrastructure.mcp import get_mcp_tools

    try:
        return asyncio.run(get_mcp_tools())
    except RuntimeError:
        logger.warning("Event loop already running; skipping MCP tool loading")
        return []
    except Exception:
        logger.warning(
            "MCP tools unavailable — agent starts without external tools", exc_info=True
        )
        return []


def build_agent():
    """Build the deep agent graph for LangGraph Platform deployment.

    Loads the orchestrator configuration from ``config/agent/PROMPT.md``,
    creates the LLM, resolves MCP tools and subagents, then compiles
    everything into a single LangGraph ``CompiledStateGraph``.

    The checkpointer is intentionally omitted — LangGraph Platform
    provides its own Postgres-backed checkpointer.

    Returns:
        A compiled deep agent graph ready for LangGraph Platform serving.
    """
    from deepagents import create_deep_agent

    from deep_agent.src.agent.config import agent_config
    from deep_agent.src.agent.llm import create_model
    from deep_agent.src.infrastructure.backend import get_backend
    from deep_agent.src.infrastructure.subagents import load_subagents

    orchestrator_cfg = agent_config.get_orchestrator_config()

    agent_name = orchestrator_cfg.get("name", "orchestrator")
    model_name = orchestrator_cfg.get("model", "gemini-3.1-pro-preview")
    system_prompt = orchestrator_cfg.get("body", "")
    skill_paths = orchestrator_cfg.get("skill_paths", [])
    tool_names = orchestrator_cfg.get("tools", [])

    logger.info("Building aegra agent '%s' with model '%s'", agent_name, model_name)

    model = create_model(model_name=model_name)
    mcp_tools = _load_mcp_tools_sync()
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
        "Aegra agent ready: %d tool(s), %d subagent(s), skills=%s",
        tool_count,
        sub_count,
        skill_paths,
    )

    return compiled


# -----------------------------------------------------------------
# Exported graph — referenced by langgraph.json as "aegra/graph.py:agent"
# -----------------------------------------------------------------
agent = build_agent()
