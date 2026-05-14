"""OpenTelemetry and Langfuse integration for aegra deployment.

Provides:
- Langfuse callback handler factory for LangChain tracing (v4 SDK)
- Langfuse client accessor via ``get_langfuse_client()``
- OTEL span creation and context propagation for graph execution
- Structured metric recording for agent performance

Environment variables (Langfuse — auto-read by v4 SDK):
    LANGFUSE_PUBLIC_KEY: Langfuse public key
    LANGFUSE_SECRET_KEY: Langfuse secret key
    LANGFUSE_BASE_URL: Langfuse server URL
    LANGFUSE_TRACING_ENVIRONMENT: Environment tag (e.g. development, production)

Environment variables (OpenTelemetry):
    OTEL_ENABLED: Enable OpenTelemetry (default: false)
    OTEL_SERVICE_NAME: Service name for traces (default: template-agent-aegra)
    OTEL_EXPORTER_OTLP_ENDPOINT: OTLP collector URL
"""

import os
import time
from collections.abc import Generator
from contextlib import contextmanager
from typing import Any

from deep_agent.utils.pylogger import get_python_logger

logger = get_python_logger()

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


# ---------------------------------------------------------------------------
# Langfuse v4 integration
# ---------------------------------------------------------------------------

_langfuse_tracing_initialized = False

LANGFUSE_TRACE_NAME = os.environ.get("LANGFUSE_TRACE_NAME", "template-agent")


def _langfuse_configured() -> bool:
    """Return True if the minimum Langfuse credentials are present."""
    return bool(
        os.environ.get("LANGFUSE_PUBLIC_KEY") and os.environ.get("LANGFUSE_SECRET_KEY")
    )


def setup_langfuse_tracing() -> None:
    """Register Langfuse as a global LangChain callback and Aegra observability provider.

    Two mechanisms work together:

    1. ``register_configure_hook`` — the same mechanism LangSmith uses to
       auto-inject its tracer. Creates a fresh ``CallbackHandler()`` per run.
    2. ``LangfuseObservabilityProvider`` — plugs into Aegra's
       ``ObservabilityManager`` so that ``create_run_config`` injects
       ``langfuse_user_id``, ``langfuse_session_id``, and
       ``langfuse_trace_name`` into ``RunnableConfig.metadata``.
       The CallbackHandler reads these automatically.

    Must be called **once** at process startup. Subsequent calls are no-ops.
    """
    global _langfuse_tracing_initialized
    if _langfuse_tracing_initialized:
        return
    _langfuse_tracing_initialized = True

    if not _langfuse_configured():
        logger.info("Langfuse credentials not set — auto-tracing disabled")
        return

    # --- 1. Register LangChain callback hook ---
    try:
        import contextvars

        from langchain_core.tracers.context import register_configure_hook
        from langfuse.langchain import CallbackHandler

        _langfuse_ctx_var: contextvars.ContextVar = contextvars.ContextVar(
            "langfuse_handler", default=None
        )

        register_configure_hook(
            _langfuse_ctx_var,
            True,
            CallbackHandler,
            env_var="LANGFUSE_PUBLIC_KEY",
        )
        logger.info("Langfuse auto-tracing registered for all LangChain runs")
    except ImportError:
        logger.warning(
            "langfuse or langchain_core not available — auto-tracing disabled"
        )
        return
    except Exception:
        logger.warning("Failed to register Langfuse tracing hook", exc_info=True)
        return

    # --- 2. Register Aegra observability provider for metadata injection ---
    try:
        from aegra_api.observability.base import get_observability_manager

        manager = get_observability_manager()
        manager.register_provider(LangfuseObservabilityProvider())
        logger.info("Langfuse observability provider registered with Aegra")
    except ImportError:
        logger.debug("aegra_api not available — skipping provider registration")
    except Exception:
        logger.warning(
            "Failed to register Langfuse observability provider", exc_info=True
        )


class LangfuseObservabilityProvider:
    """Aegra ObservabilityProvider that injects Langfuse metadata into RunnableConfig.

    The Langfuse v4 ``CallbackHandler`` auto-reads these keys from
    ``RunnableConfig.metadata``:

    - ``langfuse_user_id`` — who triggered the run
    - ``langfuse_session_id`` — groups traces by conversation (thread)
    - ``langfuse_trace_name`` — human-readable trace name in the UI
    """

    def get_callbacks(self) -> list[Any]:
        """Return empty list — callbacks are handled by register_configure_hook."""
        return []

    def get_metadata(
        self, run_id: str, thread_id: str, user_identity: str | None = None
    ) -> dict[str, Any]:
        """Return Langfuse metadata keys for RunnableConfig injection."""
        metadata: dict[str, Any] = {
            "langfuse_trace_name": LANGFUSE_TRACE_NAME,
        }
        if user_identity:
            metadata["langfuse_user_id"] = user_identity
        if thread_id:
            metadata["langfuse_session_id"] = thread_id
        return metadata

    def is_enabled(self) -> bool:
        """Return True if Langfuse credentials are configured."""
        return _langfuse_configured()


def get_langfuse_client():
    """Return the Langfuse singleton client (v4), or None if unconfigured.

    Uses ``get_client()`` which auto-reads ``LANGFUSE_PUBLIC_KEY``,
    ``LANGFUSE_SECRET_KEY``, and ``LANGFUSE_BASE_URL`` from the environment.
    """
    if not _langfuse_configured():
        return None

    try:
        from langfuse import get_client

        return get_client()
    except ImportError:
        logger.warning("langfuse package not installed — Langfuse tracing disabled")
        return None
    except Exception:
        logger.warning("Failed to initialize Langfuse client", exc_info=True)
        return None


def create_langfuse_handler(
    *,
    session_id: str | None = None,
    user_id: str | None = None,
    tags: list[str] | None = None,
):
    """Create a Langfuse CallbackHandler for LangChain/LangGraph tracing.

    In v4 the handler auto-reads credentials from environment variables
    (``LANGFUSE_PUBLIC_KEY``, ``LANGFUSE_SECRET_KEY``, ``LANGFUSE_BASE_URL``).
    Per-request attributes like ``user_id`` and ``session_id`` can also be
    passed via metadata fields in the invoke config::

        config={"metadata": {"langfuse_user_id": "...", "langfuse_session_id": "..."}}

    Returns None if Langfuse credentials are not configured, allowing
    callers to skip tracing gracefully.
    """
    if not _langfuse_configured():
        return None

    try:
        from langfuse.langchain import CallbackHandler

        handler = CallbackHandler()

        if session_id is not None:
            handler.session_id = session_id
        if user_id is not None:
            handler.user_id = user_id
        if tags:
            handler.tags = tags

        return handler
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
