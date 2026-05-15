"""User feedback HTTP endpoint for Langfuse scores (B-1).

Registers ``POST /feedback`` on the Aegra custom FastAPI app (see
``http.app`` in ``aegra.json``). Aegra loads this app as the base
application and merges core LangGraph Platform routes onto it.

When Langfuse credentials are absent, submissions are logged and accepted
without contacting Langfuse.

When ``thread_id`` and ``message_id`` are present, feedback is also
persisted to Postgres for cross-session history.
"""

from __future__ import annotations

import json
import os
import time
from typing import Any, Literal

from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse, JSONResponse
from pydantic import ValidationError

from deep_agent.aegra.auth import (
    ENABLE_AUTH,
    SSO_CLIENT_ID,
    SSO_CLIENT_SECRET,
    SSO_ISSUER_URL,
)
from deep_agent.aegra.middleware import AUTH_TYPE
from deep_agent.aegra.telemetry import get_langfuse_client
from deep_agent.src.feedback.repository import FeedbackRepository
from deep_agent.src.schema import FeedbackRequest, FeedbackResponse
from deep_agent.src.settings import settings
from deep_agent.utils.pylogger import get_python_logger

logger = get_python_logger()

app = FastAPI(title="template-agent-custom", docs_url=None, redoc_url=None)

_cli_auth_codes: dict[str, dict[str, Any]] = {}
_CLI_CODE_TTL = 300


def _agent_base_url() -> str:
    host = os.environ.get("AGENT_HOST", "0.0.0.0")
    port = os.environ.get("AGENT_PORT", "5002")
    display_host = "localhost" if host == "0.0.0.0" else host
    return f"http://{display_host}:{port}"


@app.get("/auth/discover")
async def auth_discover() -> dict[str, Any]:
    """Expose auth mode and OIDC endpoints for CLI clients."""
    auth_type = "sso" if ENABLE_AUTH else "none"
    if AUTH_TYPE == "api_key":
        auth_type = "api_key"
    issuer = SSO_ISSUER_URL.rstrip("/") if SSO_ISSUER_URL else ""
    auth_path = "/protocol/openid-connect/auth"
    token_path = "/protocol/openid-connect/token"
    base = _agent_base_url()
    return {
        "auth_type": auth_type,
        "authorization_endpoint": f"{issuer}{auth_path}" if issuer else "",
        "token_endpoint": f"{issuer}{token_path}" if issuer else "",
        "client_id": SSO_CLIENT_ID,
        "client_secret": SSO_CLIENT_SECRET or "",
        "scopes": ["openid"],
        "cli_callback_url": f"{base}/auth/cli/callback",
    }


@app.get("/auth/cli/callback")
async def cli_oauth_callback(
    code: str = "",
    state: str = "",
    error: str = "",
    error_description: str = "",
) -> HTMLResponse:
    """Receive OAuth callback from Keycloak, store code for CLI to poll."""
    if error:
        msg = error_description or error
        logger.warning("cli_oauth_callback_error", error=error, desc=error_description)
        return HTMLResponse(
            f"<html><body><h2>Login failed</h2><p>{msg}</p>"
            "<p>You may close this window.</p></body></html>",
            status_code=400,
        )
    if not code or not state:
        return HTMLResponse(
            "<html><body><h2>Missing code or state</h2>"
            "<p>You may close this window.</p></body></html>",
            status_code=400,
        )
    _cli_auth_codes[state] = {"code": code, "ts": time.time()}
    logger.info("cli_oauth_code_stored", state=state)
    return HTMLResponse(
        "<html><body><h2>Login complete</h2>"
        "<p>You can close this window and return to the terminal.</p></body></html>"
    )


@app.get("/auth/cli/poll")
async def cli_poll_code(state: str = "") -> JSONResponse:
    """CLI polls this endpoint to retrieve the authorization code."""
    if not state:
        return JSONResponse({"status": "waiting"}, status_code=200)
    entry = _cli_auth_codes.get(state)
    if not entry:
        return JSONResponse({"status": "waiting"}, status_code=200)
    if time.time() - entry["ts"] > _CLI_CODE_TTL:
        _cli_auth_codes.pop(state, None)
        return JSONResponse({"status": "expired"}, status_code=410)
    _cli_auth_codes.pop(state, None)
    return JSONResponse({"status": "ready", "code": entry["code"]}, status_code=200)


def _score_to_feedback_polarity(req: FeedbackRequest) -> Literal["up", "down"]:
    """Map request name/value to stored feedback polarity."""
    name_lower = (req.name or "").lower()
    if "down" in name_lower or "negative" in name_lower:
        return "down"
    if "up" in name_lower or "positive" in name_lower:
        return "up"
    return "up" if req.value >= 0.5 else "down"


async def _persist_feedback_to_postgres(req: FeedbackRequest) -> None:
    if not req.thread_id or not req.message_id:
        return
    if not settings.database_uri:
        logger.warning(
            "feedback_postgres_skipped_no_database_uri",
            thread_id=req.thread_id,
            message_id=req.message_id,
        )
        return
    polarity = _score_to_feedback_polarity(req)
    user_id = req.user_id if req.user_id else "anonymous"
    repo = FeedbackRepository(settings.database_uri)
    await repo.upsert_feedback(
        req.thread_id,
        req.message_id,
        user_id,
        polarity,
        req.trace_id,
    )
    logger.info(
        "feedback_recorded_postgres",
        thread_id=req.thread_id,
        message_id=req.message_id,
        user_id=user_id,
        feedback=polarity,
    )


async def record_feedback(request_data: dict[str, Any]) -> FeedbackResponse:
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
        await _persist_feedback_to_postgres(req)
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
    await _persist_feedback_to_postgres(req)
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
        resp = await record_feedback(payload)
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


@app.get("/feedback/{thread_id}")
async def get_thread_feedback(
    thread_id: str, user_id: str = "anonymous"
) -> dict[str, Any]:
    """Return all feedback for a thread."""
    if not settings.database_uri:
        return {"feedback": []}
    repo = FeedbackRepository(settings.database_uri)
    items = await repo.list_feedback(thread_id, user_id)
    return {"feedback": items}


app.add_api_route("/feedback", feedback_handler, methods=["POST"])
