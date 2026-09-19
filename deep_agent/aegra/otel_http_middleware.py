"""HTTP-level OTEL metrics middleware for Aegra-owned endpoints.

Aegra manages thread creation and SSE streaming internally. These
middleware classes intercept HTTP requests to record OTEL metrics
that the template-agent otel.py helpers expect but cannot wire
at the LangChain middleware level.
"""

from __future__ import annotations

from typing import Any

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request

from deep_agent.aegra.otel import (
    record_stream_completed,
    record_stream_error,
    record_stream_started,
    record_thread_created,
)


class StreamMetricsMiddleware(BaseHTTPMiddleware):
    """Record OTEL metrics for SSE streaming responses."""

    async def dispatch(self, request: Request, call_next: Any) -> Any:
        """Intercept /runs/stream and /runs/wait to record streaming metrics."""
        if "/runs/" not in request.url.path:
            return await call_next(request)

        is_stream = request.url.path.endswith(("/stream", "/wait"))
        if not is_stream:
            return await call_next(request)

        stream_start = record_stream_started()
        try:
            response = await call_next(request)
        except Exception as exc:
            record_stream_error(error_type=type(exc).__name__)
            raise

        if 200 <= response.status_code < 400:
            record_stream_completed(stream_start, token_count=0)
        else:
            record_stream_error(error_type=f"http_{response.status_code}")

        return response


class ThreadMetricsMiddleware(BaseHTTPMiddleware):
    """Record OTEL metrics for thread creation on Aegra-owned endpoints."""

    async def dispatch(self, request: Request, call_next: Any) -> Any:
        """Record thread creation on successful POST /threads."""
        response = await call_next(request)

        if (
            request.method == "POST"
            and request.url.path.rstrip("/").endswith("/threads")
            and 200 <= response.status_code < 300
        ):
            record_thread_created()

        return response


# thread_messages_count (record_thread_messages) requires the final
# message count at thread finalization, which is not available at the
# HTTP level. Wiring this metric needs Aegra-side support (e.g. a
# post-run hook that exposes the conversation turn count).
