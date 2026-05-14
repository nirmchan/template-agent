"""User feedback HTTP endpoint for Langfuse scores (B-1).

Registers ``POST /feedback`` on the Aegra custom FastAPI app (see
``http.app`` in ``aegra.json``). Aegra loads this app as the base
application and merges core LangGraph Platform routes onto it.

When Langfuse credentials are absent, submissions are logged and accepted
without contacting Langfuse.
"""

from __future__ import annotations

import json
from typing import Any

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from pydantic import ValidationError

from deep_agent.aegra.telemetry import get_langfuse_client
from deep_agent.src.schema import FeedbackRequest, FeedbackResponse
from deep_agent.utils.pylogger import get_python_logger

logger = get_python_logger()

app = FastAPI(title="template-agent-custom", docs_url=None, redoc_url=None)


def record_feedback(request_data: dict[str, Any]) -> FeedbackResponse:
    """Validate feedback input, optionally record a Langfuse score, return success.

    Args:
        request_data: Raw JSON object (mapping) from the client.

    Returns:
        ``FeedbackResponse`` with status ``success``.

    Raises:
        ValidationError: If the payload does not satisfy ``FeedbackRequest``.
        RuntimeError: If Langfuse is configured but score submission fails.
    """
    req = FeedbackRequest.model_validate(request_data)

    logger.info(
        "feedback_received",
        trace_id=req.trace_id,
        name=req.name,
        value=req.value,
        kwargs_keys=sorted(req.kwargs.keys()) if req.kwargs else [],
    )

    langfuse_client = get_langfuse_client()
    if langfuse_client is None:
        logger.info(
            "feedback_skipped_langfuse_unconfigured",
            trace_id=req.trace_id,
            name=req.name,
        )
        return FeedbackResponse()

    try:
        langfuse_client.score(
            trace_id=req.trace_id,
            name=req.name,
            value=req.value,
            **req.kwargs,
        )
    except Exception as exc:
        logger.exception(
            "feedback_langfuse_score_failed",
            trace_id=req.trace_id,
            name=req.name,
            error=str(exc),
        )
        raise RuntimeError("Langfuse score submission failed") from exc

    logger.info(
        "feedback_recorded_langfuse",
        trace_id=req.trace_id,
        name=req.name,
    )
    return FeedbackResponse()


async def feedback_handler(request: Request) -> JSONResponse:
    """ASGI/Starlette handler: read JSON, validate, record feedback."""
    try:
        body_bytes = await request.body()
        if not body_bytes.strip():
            return JSONResponse(
                status_code=422,
                content={"detail": [{"msg": "Empty body", "type": "value_error"}]},
            )
        payload = json.loads(body_bytes.decode("utf-8"))
    except json.JSONDecodeError:
        return JSONResponse(
            status_code=422,
            content={
                "detail": [{"msg": "Invalid JSON body", "type": "json_invalid"}],
            },
        )

    if not isinstance(payload, dict):
        return JSONResponse(
            status_code=422,
            content={
                "detail": [
                    {
                        "msg": "JSON body must be an object",
                        "type": "type_error",
                    },
                ],
            },
        )

    try:
        resp = record_feedback(payload)
    except ValidationError as exc:
        return JSONResponse(
            status_code=422,
            content={"detail": exc.errors(include_url=False)},
        )
    except Exception:
        logger.exception("feedback_handler_error")
        return JSONResponse(
            status_code=500,
            content={"detail": "Internal server error"},
        )

    return JSONResponse(
        status_code=200,
        content=resp.model_dump(),
    )


app.add_api_route("/feedback", feedback_handler, methods=["POST"])
