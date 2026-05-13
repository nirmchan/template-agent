"""Subagent loading from configuration files.

This module builds SubAgent instances from the markdown configuration files in
config/subagents/. It reads each subagent's config, resolves their tools
and skills, creates appropriate LLM instances, and returns ready-to-use SubAgent
objects for the orchestrator.

Why this exists:
    Subagents are specialized agents that handle specific tasks (e.g., analyst,
    publisher). This module transforms their declarative configs into executable
    SubAgent instances that the orchestrator can delegate work to.

Functions:
    load_subagents: Build all subagents from config/subagents/*.md
"""

from typing import Any

from deepagents import SubAgent

from deep_agent.src.agent.config import agent_config
from deep_agent.src.agent.llm import create_model
from deep_agent.src.exceptions import LLMError, SubAgentError
from deep_agent.src.settings import settings
from deep_agent.utils.pylogger import get_python_logger

logger = get_python_logger(log_level=settings.PYTHON_LOG_LEVEL)


def load_subagents(
    tools: list[Any],
) -> list[SubAgent] | None:
    """Build subagents from pre-loaded configurations.

    Args:
        tools: List of available MCP tools.

    Returns:
        List of configured SubAgent instances, or None if no subagents configured.

    Raises:
        SubAgentError: If a subagent fails to build (missing model, bad config).
    """
    all_subagent_configs: dict[str, dict[str, Any]] = (
        agent_config.get_all_subagent_configs()
    )

    if not all_subagent_configs:
        logger.warning("No subagent configurations found")
        return None

    logger.info(f"Building {len(all_subagent_configs)} subagent(s)")

    subagents_list: list[SubAgent] = []

    for name, agent_cfg in all_subagent_configs.items():
        try:
            sa = _build_single_subagent(name, agent_cfg, tools)
            subagents_list.append(sa)
        except (ValueError, LLMError) as e:
            raise SubAgentError(f"Failed to build subagent '{name}': {e}") from e
        except Exception as e:
            raise SubAgentError(
                f"Unexpected error building subagent '{name}': {e}"
            ) from e

    logger.info(f"Built {len(subagents_list)} subagent(s) successfully")
    return subagents_list


def _build_single_subagent(
    name: str,
    agent_cfg: dict[str, Any],
    tools: list[Any],
) -> SubAgent:
    """Build a single SubAgent from its configuration.

    Args:
        name: Subagent name (from config filename).
        agent_cfg: Parsed frontmatter config for this subagent.
        tools: Available MCP tools for tool resolution.

    Returns:
        Configured SubAgent instance.

    Raises:
        ValueError: If required fields are missing in config.
        LLMError: If model creation fails.
    """
    model_name: str | None = agent_cfg.get("model")
    if not model_name:
        raise ValueError(
            f"Subagent '{name}' is missing required 'model' field in frontmatter"
        )

    logger.info(f"Subagent '{name}' using model: {model_name}")

    tool_names: list[str] = agent_cfg.get("tools", [])
    resolved_tools: list[Any] = (
        agent_config.resolve_tools(tool_names, tools, agent_name=name)
        if tool_names
        else []
    )

    skill_paths: list[str] = agent_cfg.get("skill_paths", [])

    subagent_params: dict[str, Any] = {
        "name": name,
        "model": create_model(model_name=model_name),
        "description": agent_cfg.get("description", ""),
        "system_prompt": agent_cfg.get("body", ""),
    }

    if resolved_tools:
        subagent_params["tools"] = resolved_tools
    if skill_paths:
        subagent_params["skills"] = skill_paths

    return SubAgent(**subagent_params)
