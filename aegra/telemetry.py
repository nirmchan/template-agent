"""OpenTelemetry and Langfuse integration for aegra deployment (MR-23, MR-24).

Provides:
- OTEL span creation and context propagation for graph execution
- Langfuse callback handler factory for LangChain tracing
- Structured metric recording for agent performance

Environment variables:
    OTEL_ENABLED: Enable OpenTelemetry (default: false)
    OTEL_SERVICE_NAME: Service name for traces (default: template-agent-aegra)
    OTEL_EXPORTER_OTLP_ENDPOINT: OTLP collector URL
    LANGFUSE_PUBLIC_KEY: Langfuse public key
    LANGFUSE_SECRET_KEY: Langfuse secret key
    LANGFUSE_BASE_URL: Langfuse server URL
"""

import logging
import os
import time
from collections.abc import Generator
from contextlib import contextmanager
from typing import Any

logger = logging.getLogger(__name__)

OTEL_ENABLED = os.environ.get("OTEL_ENABLED", "false").lower() == "true"
OTEL_SERVICE_NAME = os.environ.get("OTEL_SERVICE_NAME", "template-agent-aegra")
OTEL_EXPORTER_ENDPOINT = os.environ.get("OTEL_EXPORTER_OTLP_ENDPOINT", "")

_tracer = None


def _get_tracer():
    """Lazy-initialize the OTEL tracer. Returns None if OTEL is disabled."""
    global _tracer
    if _tracer is not None:
        return _tracer
    if not OTEL_ENABLED:
        return None

    try:
        from opentelemetry import trace
        from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import (
            OTLPSpanExporter,
        )
        from opentelemetry.sdk.resources import Resource
        from opentelemetry.sdk.trace import TracerProvider
        from opentelemetry.sdk.trace.export import BatchSpanProcessor

        resource = Resource.create({"service.name": OTEL_SERVICE_NAME})
        provider = TracerProvider(resource=resource)

        if OTEL_EXPORTER_ENDPOINT:
            exporter = OTLPSpanExporter(endpoint=OTEL_EXPORTER_ENDPOINT)
            provider.add_span_processor(BatchSpanProcessor(exporter))

        trace.set_tracer_provider(provider)
        _tracer = trace.get_tracer(OTEL_SERVICE_NAME)
        logger.info("OpenTelemetry initialized: service=%s", OTEL_SERVICE_NAME)
        return _tracer
    except ImportError:
        logger.warning("opentelemetry packages not installed — tracing disabled")
        return None
    except Exception:
        logger.warning("Failed to initialize OpenTelemetry", exc_info=True)
        return None


@contextmanager
def trace_span(
    name: str,
    attributes: dict[str, Any] | None = None,
) -> Generator[dict[str, Any], None, None]:
    """Context manager that creates an OTEL span or a timing-only fallback.

    Always yields a ``context`` dict that callers can enrich with
    ``set_attribute``-style key/value pairs. When OTEL is disabled the
    context still collects timing for structured logging.

    Usage::

        with trace_span("graph.invoke", {"thread_id": tid}) as ctx:
            result = agent.invoke(input)
            ctx["tokens"] = count_tokens(result)
    """
    tracer = _get_tracer()
    ctx: dict[str, Any] = {"start_time": time.perf_counter()}

    if tracer is not None:
        with tracer.start_as_current_span(name, attributes=attributes or {}) as span:
            try:
                yield ctx
                for k, v in ctx.items():
                    if k != "start_time":
                        span.set_attribute(f"aegra.{k}", str(v))
                span.set_attribute("aegra.duration_ms", _elapsed_ms(ctx))
            except Exception as exc:
                span.set_attribute("aegra.error", str(exc))
                span.set_attribute("aegra.duration_ms", _elapsed_ms(ctx))
                raise
    else:
        try:
            yield ctx
        finally:
            elapsed = _elapsed_ms(ctx)
            logger.info("span=%s duration_ms=%.1f attrs=%s", name, elapsed, ctx)


def create_langfuse_handler(
    *,
    trace_name: str = "aegra-agent",
    session_id: str | None = None,
    user_id: str | None = None,
    metadata: dict[str, Any] | None = None,
):
    """Create a Langfuse callback handler for LangChain tracing.

    Returns None if Langfuse credentials are not configured, allowing
    callers to skip tracing gracefully.
    """
    public_key = os.environ.get("LANGFUSE_PUBLIC_KEY")
    secret_key = os.environ.get("LANGFUSE_SECRET_KEY")
    base_url = os.environ.get("LANGFUSE_BASE_URL")

    if not public_key or not secret_key:
        return None

    try:
        from langfuse.langchain import CallbackHandler

        return CallbackHandler(
            public_key=public_key,
            secret_key=secret_key,
            host=base_url,
            trace_name=trace_name,
            session_id=session_id,
            user_id=user_id,
            metadata=metadata or {},
        )
    except ImportError:
        logger.warning("langfuse package not installed — Langfuse tracing disabled")
        return None
    except Exception:
        logger.warning("Failed to create Langfuse handler", exc_info=True)
        return None


def record_metric(name: str, value: float, tags: dict[str, str] | None = None) -> None:
    """Record a numeric metric. Logs to structured logger; sends to OTEL if available."""
    logger.info("metric=%s value=%.4f tags=%s", name, value, tags or {})

    tracer = _get_tracer()
    if tracer is not None:
        try:
            from opentelemetry import metrics

            meter = metrics.get_meter(OTEL_SERVICE_NAME)
            counter = meter.create_counter(name)
            counter.add(value, tags or {})
        except Exception:
            pass


def _elapsed_ms(ctx: dict[str, Any]) -> float:
    return (time.perf_counter() - ctx.get("start_time", time.perf_counter())) * 1000
