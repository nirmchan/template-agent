"""CLI chat client for the agent."""

from __future__ import annotations

import typing

__all__ = ["app"]


def __getattr__(name: str) -> typing.Any:
    if name == "app":
        try:
            from deep_agent.cli.main import app as typer_app

            return typer_app
        except ImportError as exc:
            from deep_agent.cli.constants import CLI_INSTALL_HINT

            raise SystemExit(CLI_INSTALL_HINT) from exc
    msg = f"module {__name__!r} has no attribute {name!r}"
    raise AttributeError(msg)
