"""Unit tests for agent package lazy imports."""

import pytest


class TestAgentLazyImports:
    def test_import_agent_manager(self):
        from deep_agent.src.agent import AgentManager

        assert AgentManager is not None
        assert AgentManager.__name__ == "AgentManager"

    def test_import_get_deep_agent(self):
        from deep_agent.src.agent import get_deep_agent

        assert get_deep_agent is not None
        assert callable(get_deep_agent)

    def test_unknown_attribute_raises(self):
        import deep_agent.src.agent as agent_pkg

        with pytest.raises(AttributeError, match="has no attribute"):
            agent_pkg.__getattr__("nonexistent_thing")
