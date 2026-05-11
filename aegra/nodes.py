"""Error-handling node wrappers for graph execution.

Provides decorator-style wrappers that add retry logic, error capture,
and structured logging around graph node functions. These are used by
the graph builder to make the agent resilient in production.

The deepagents library handles its own internal node execution. These
wrappers sit at the aegra integration boundary, catching errors that
escape the deepagents graph and recording them in platform metadata.
"""

import asyncio
import logging
import time
from collections.abc import Callable
from functools import wraps
from typing import Any

logger = logging.getLogger(__name__)

MAX_NODE_RETRIES = 2
RETRY_DELAY_SECONDS = 1.0


def with_error_handling(node_name: str) -> Callable[..., Any]:
    """Decorator that adds structured error handling to a graph node.

    Catches exceptions, logs them with the node name for traceability,
    and re-raises after recording the failure. Used during graph
    construction to wrap custom nodes added around the deepagents core.

    Args:
        node_name: Human-readable name for log messages.
    """

    def decorator(fn: Callable[..., Any]) -> Callable[..., Any]:
        @wraps(fn)
        def wrapper(*args: Any, **kwargs: Any) -> Any:
            try:
                return fn(*args, **kwargs)
            except Exception:
                logger.exception("Node '%s' failed", node_name)
                raise

        @wraps(fn)
        async def async_wrapper(*args: Any, **kwargs: Any) -> Any:
            try:
                return await fn(*args, **kwargs)
            except Exception:
                logger.exception("Node '%s' failed", node_name)
                raise

        if asyncio.iscoroutinefunction(fn):
            return async_wrapper
        return wrapper

    return decorator


def with_retry(
    max_retries: int = MAX_NODE_RETRIES,
    delay: float = RETRY_DELAY_SECONDS,
) -> Callable[..., Any]:
    """Decorator that retries a node function on failure.

    Uses simple linear backoff. Intended for nodes that call external
    services (MCP tools, LLM APIs) where transient failures are expected.

    Args:
        max_retries: Maximum number of retry attempts.
        delay: Seconds to wait between retries.
    """

    def decorator(fn: Callable[..., Any]) -> Callable[..., Any]:
        @wraps(fn)
        def wrapper(*args: Any, **kwargs: Any) -> Any:
            last_exc: Exception | None = None
            for attempt in range(1, max_retries + 2):
                try:
                    return fn(*args, **kwargs)
                except Exception as exc:
                    last_exc = exc
                    if attempt <= max_retries:
                        logger.warning(
                            "Retry %d/%d for '%s': %s",
                            attempt,
                            max_retries,
                            fn.__name__,
                            exc,
                        )
                        time.sleep(delay * attempt)
            raise last_exc  # type: ignore[misc]

        return wrapper

    return decorator


def timed_node(fn: Callable[..., Any]) -> Callable[..., Any]:
    """Decorator that logs execution duration of a node function."""

    @wraps(fn)
    def wrapper(*args: Any, **kwargs: Any) -> Any:
        start = time.perf_counter()
        try:
            result = fn(*args, **kwargs)
            elapsed = time.perf_counter() - start
            logger.info("Node '%s' completed in %.2fs", fn.__name__, elapsed)
            return result
        except Exception:
            elapsed = time.perf_counter() - start
            logger.error("Node '%s' failed after %.2fs", fn.__name__, elapsed)
            raise

    return wrapper
