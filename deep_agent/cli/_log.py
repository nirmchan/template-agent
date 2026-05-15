"""CLI-local logger that works with or without the full agent installed."""

from __future__ import annotations

import logging
from typing import Any


def get_logger() -> Any:
    """Return structlog logger if available, else stdlib logging."""
    try:
        from deep_agent.utils.pylogger import get_python_logger

        return get_python_logger()
    except ImportError:
        return logging.getLogger("deep_agent.cli")
