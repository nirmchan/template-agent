"""Agent creation and orchestration.

This package provides functionality for creating and managing deep agents.
It includes the factory for creating configured agents and the manager for
orchestrating agent execution and streaming.

Modules:
    factory: Agent creation with full configuration
    manager: Agent execution orchestration and streaming
    llm: LLM instance creation
    config: Configuration loading and management

Main exports:
    get_deep_agent: Create a fully configured deep agent
    AgentManager: Agent orchestration and streaming coordinator
"""

# Use lazy imports to avoid circular dependency with infrastructure
__all__ = ["get_deep_agent", "AgentManager"]


def __getattr__(name):
    """Lazy import to avoid circular dependencies."""
    if name == "get_deep_agent":
        from .factory import get_deep_agent

        return get_deep_agent
    elif name == "AgentManager":
        from .manager import AgentManager

        return AgentManager
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
