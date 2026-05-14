"""Unit tests for checkpointer module."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from deep_agent.src.exceptions import AppException


class TestInitializeCheckpointer:
    @pytest.mark.asyncio
    async def test_success(self):
        mock_saver = AsyncMock()
        mock_saver.setup = AsyncMock()
        mock_saver.__aenter__ = AsyncMock(return_value=mock_saver)
        mock_saver.__aexit__ = AsyncMock(return_value=False)

        with patch(
            "deep_agent.src.infrastructure.checkpointer.AsyncPostgresSaver"
        ) as mock_cls:
            mock_cls.from_conn_string.return_value = mock_saver
            from deep_agent.src.infrastructure.checkpointer import (
                initialize_checkpointer,
            )

            await initialize_checkpointer()
            mock_saver.setup.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_failure_raises_app_exception(self):
        with patch(
            "deep_agent.src.infrastructure.checkpointer.AsyncPostgresSaver"
        ) as mock_cls:
            mock_cls.from_conn_string.side_effect = ConnectionError("no db")
            from deep_agent.src.infrastructure.checkpointer import (
                initialize_checkpointer,
            )

            with pytest.raises(AppException, match="Database initialization failed"):
                await initialize_checkpointer()


class TestGetCheckpointer:
    @pytest.mark.asyncio
    async def test_yields_checkpointer(self):
        mock_saver = AsyncMock()
        mock_saver.__aenter__ = AsyncMock(return_value=mock_saver)
        mock_saver.__aexit__ = AsyncMock(return_value=False)

        with patch(
            "deep_agent.src.infrastructure.checkpointer.AsyncPostgresSaver"
        ) as mock_cls:
            mock_cls.from_conn_string.return_value = mock_saver
            from deep_agent.src.infrastructure.checkpointer import get_checkpointer

            async with get_checkpointer() as cp:
                assert cp is mock_saver
