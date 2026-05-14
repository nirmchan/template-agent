"""Unit tests for agent factory (get_deep_agent)."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from deep_agent.src.exceptions import ConfigurationError


class TestGetDeepAgent:
    @pytest.fixture
    def mock_orch_config(self):
        return {
            "name": "test-agent",
            "model": "gpt-4o",
            "body": "You are a test agent.",
            "skill_paths": ["/tmp/skills"],
            "tools": ["tool_a"],
        }

    @pytest.fixture
    def factory_patches(self, mock_orch_config):
        """Patch all external deps of get_deep_agent."""
        mock_model = MagicMock()
        mock_tools = [MagicMock()]
        mock_subagents = [MagicMock()]
        mock_backend = MagicMock()
        mock_agent = MagicMock()

        mock_checkpointer_ctx = AsyncMock()
        mock_checkpointer_ctx.__aenter__ = AsyncMock(return_value=MagicMock())
        mock_checkpointer_ctx.__aexit__ = AsyncMock(return_value=False)

        patches = {
            "config": patch(
                "deep_agent.src.agent.factory.agent_config",
                **{
                    "get_orchestrator_config.return_value": mock_orch_config,
                    "resolve_tools.return_value": mock_tools,
                },
            ),
            "model": patch(
                "deep_agent.src.agent.factory.get_or_create_model",
                return_value=mock_model,
            ),
            "mcp": patch(
                "deep_agent.src.agent.factory.get_mcp_tools",
                new_callable=AsyncMock,
                return_value=mock_tools,
            ),
            "subagents": patch(
                "deep_agent.src.agent.factory.load_subagents",
                return_value=mock_subagents,
            ),
            "backend": patch(
                "deep_agent.src.agent.factory.get_backend",
                return_value=mock_backend,
            ),
            "checkpointer": patch(
                "deep_agent.src.agent.factory.get_checkpointer",
                return_value=mock_checkpointer_ctx,
            ),
            "create": patch(
                "deep_agent.src.agent.factory.create_deep_agent",
                return_value=mock_agent,
            ),
        }
        return patches

    async def test_yields_agent(self, factory_patches):
        from deep_agent.src.agent.factory import get_deep_agent

        mocks = {k: p.start() for k, p in factory_patches.items()}
        try:
            async with get_deep_agent() as agent:
                assert agent is not None
                mocks["model"].assert_called_once()
                mocks["mcp"].assert_awaited_once()
                mocks["create"].assert_called_once()
        finally:
            for p in factory_patches.values():
                p.stop()

    async def test_sso_token_triggers_refresh(self, factory_patches):
        from deep_agent.src.agent.factory import get_deep_agent

        mocks = {k: p.start() for k, p in factory_patches.items()}
        with patch(
            "deep_agent.src.infrastructure.mcp.refresh_access_token",
            new_callable=AsyncMock,
            return_value="refreshed-token",
        ) as mock_refresh:
            try:
                async with get_deep_agent(
                    sso_token="old-token", refresh_token="ref-tok"
                ) as agent:
                    assert agent is not None
                    mock_refresh.assert_awaited_once_with("old-token", "ref-tok")
            finally:
                for p in factory_patches.values():
                    p.stop()

    async def test_config_error_raises(self):
        from deep_agent.src.agent.factory import get_deep_agent

        with patch(
            "deep_agent.src.agent.factory.agent_config",
            **{"get_orchestrator_config.side_effect": ValueError("bad config")},
        ):
            with pytest.raises(ConfigurationError, match="Failed to load"):
                async with get_deep_agent():
                    pass
