"""MCP (Model Context Protocol) client for external tool integration.

This module manages connections to MCP servers that provide tools for agents.
It reads server configurations from config/mcp.json, establishes parallel
connections with fault isolation, and retrieves all available tools.

Why this exists:
    MCP servers provide external capabilities (APIs, databases, etc.) as tools
    that agents can use. This module bridges the gap between our agent system
    and external MCP-compatible services.

Functions:
    refresh_access_token: Exchange a refresh token for a fresh access token
    get_mcp_tools: Connect to all MCP servers and retrieve their tools
"""

import asyncio
import base64
import json
import os
import time

import httpx
from langchain_mcp_adapters.client import MultiServerMCPClient

from deep_agent.src.agent.config import agent_config
from deep_agent.src.settings import settings
from deep_agent.utils.pylogger import get_python_logger

logger = get_python_logger(log_level=settings.PYTHON_LOG_LEVEL)

_SSO_TOKEN_URL = ""


def _get_token_endpoint() -> str:
    """Derive the OIDC token endpoint from SSO_ISSUER_URL (cached)."""
    global _SSO_TOKEN_URL  # noqa: PLW0603
    if _SSO_TOKEN_URL:
        return _SSO_TOKEN_URL
    issuer = os.environ.get("SSO_ISSUER_URL", "").rstrip("/")
    if issuer:
        _SSO_TOKEN_URL = f"{issuer}/protocol/openid-connect/token"
    return _SSO_TOKEN_URL


def _jwt_exp(token: str) -> float:
    """Extract ``exp`` from a JWT payload without cryptographic validation."""
    try:
        payload = token.split(".")[1]
        payload += "=" * (4 - len(payload) % 4)
        data = json.loads(base64.urlsafe_b64decode(payload))
        return float(data.get("exp", 0))
    except Exception:
        return 0.0


async def refresh_access_token(
    access_token: str,
    refresh_token: str | None,
) -> str:
    """Return a fresh access token, using the refresh_token grant if needed.

    If the current ``access_token`` has more than 30 seconds of remaining
    lifetime it is returned as-is.  Otherwise, if a ``refresh_token`` and
    the OIDC token endpoint are available, the token is refreshed via the
    standard ``refresh_token`` grant.

    This should be called **once in the graph factory**, before passing
    the token to ``get_mcp_tools()``, so the MCP client always receives
    a token that will survive both tool discovery and tool execution.

    Args:
        access_token: Current JWT access token (may be expired).
        refresh_token: OIDC refresh token (may be ``None`` or ``""``).

    Returns:
        A valid access token (refreshed if necessary, original if refresh
        is unavailable or fails).
    """
    remaining = _jwt_exp(access_token) - time.time()
    if remaining > 30:
        logger.debug("Access token still valid (%.0fs remaining)", remaining)
        return access_token

    if not refresh_token:
        logger.warning(
            "Access token near expiry (%.0fs) but no refresh_token available", remaining
        )
        return access_token

    token_url = _get_token_endpoint()
    client_id = os.environ.get("SSO_CLIENT_ID", "")
    if not token_url or not client_id:
        logger.warning("Cannot refresh token — SSO_ISSUER_URL or SSO_CLIENT_ID not set")
        return access_token

    logger.info("Refreshing SSO access token (%.0fs remaining)", remaining)
    try:
        async with httpx.AsyncClient() as client:
            resp = await client.post(
                token_url,
                data={
                    "grant_type": "refresh_token",
                    "client_id": client_id,
                    "refresh_token": refresh_token,
                },
            )
            resp.raise_for_status()
            new_token = resp.json()["access_token"]
            new_remaining = _jwt_exp(new_token) - time.time()
            logger.info("SSO token refreshed (%.0fs lifetime)", new_remaining)
            return new_token
    except Exception:
        logger.error("Token refresh failed — using original token", exc_info=True)
        return access_token


def _get_server_configs() -> dict[str, dict]:
    """Get pre-loaded MCP server configurations.

    Returns:
        ``{server_name: {url, transport, enabled, auth, ssl_verify, timeout}}``
    """
    return agent_config.get_mcp_servers()


def _build_server_config(
    entry: dict,
    sso_token: str | None,
) -> dict:
    """Build MultiServerMCPClient config from server definition.

    The caller is expected to pass a **fresh** ``sso_token`` (see
    ``refresh_access_token``).  This function simply wires it into the
    ``Authorization`` header for the MCP connection.

    Args:
        entry: Server definition with url, auth, ssl_verify, transport.
        sso_token: Optional bearer token (should already be refreshed).

    Returns:
        Config dict for MultiServerMCPClient.
    """
    headers: dict[str, str] = {}
    if entry.get("auth", True) and sso_token:
        headers["Authorization"] = f"Bearer {sso_token}"

    config: dict = {
        "url": entry["url"],
        "transport": entry.get("transport", "streamable_http"),
        "headers": headers,
    }

    if not entry.get("ssl_verify", True):
        config["httpx_client_factory"] = lambda **kw: httpx.AsyncClient(
            verify=False, **kw
        )  # nosec B501

    return config


async def _connect_single_server(
    name: str, config: dict, timeout: int, *, required: bool = False
) -> list:
    """Connect to one MCP server and return its tools.

    Failures are logged and return empty list for fault isolation.

    Args:
        name: Human-readable server identifier used in log messages.
        config: MCP client connection config (url, transport, headers, etc.).
        timeout: Seconds before the connection attempt is cancelled.
        required: If True the server is explicitly enabled in config,
            so connection failures are logged at error level.
            If False (startup probe without auth), failures are warnings.
    """
    try:
        async with asyncio.timeout(timeout):
            client = MultiServerMCPClient({name: config})
            tools = await client.get_tools()
        logger.info(f"[{name}] loaded {len(tools)} tool(s)")
        return tools
    except TimeoutError:
        logger.error(f"[{name}] timeout after {timeout}s ({config.get('url')})")
    except Exception as exc:
        if _is_auth_error(exc):
            logger.info(f"[{name}] requires authentication — tools loaded per-request")
        elif _is_connection_error(exc) and not required:
            logger.warning(f"[{name}] not reachable ({config.get('url')}) — skipped")
        else:
            logger.error(
                f"[{name}] connection failed ({config.get('url')})", exc_info=True
            )
    return []


def _is_auth_error(exc: BaseException) -> bool:
    """Check if an exception is caused by an HTTP 401/403 response."""
    for sub in getattr(exc, "exceptions", [exc]):
        msg = str(sub)
        if "401" in msg or "403" in msg or "Unauthorized" in msg or "Forbidden" in msg:
            return True
        if hasattr(sub, "__cause__") and sub.__cause__:
            if _is_auth_error(sub.__cause__):
                return True
    return False


def _is_connection_error(exc: BaseException) -> bool:
    """Check if an exception is a connection refused / unreachable error."""
    for sub in getattr(exc, "exceptions", [exc]):
        msg = str(sub).lower()
        if (
            "connecterror" in msg
            or "connection attempts failed" in msg
            or "connection refused" in msg
        ):
            return True
        if hasattr(sub, "__cause__") and sub.__cause__:
            if _is_connection_error(sub.__cause__):
                return True
    return False


async def get_mcp_tools(
    sso_token: str | None = None,
) -> list:
    """Connect to MCP server(s) and retrieve available tools.

    Loads server definitions from ``config/mcp.json``, connects to
    each enabled server in parallel, and returns a deduplicated flat list.

    The ``sso_token`` should already be **refreshed** by the caller via
    ``refresh_access_token()`` before calling this function.

    Connection failures are logged but do not raise exceptions, ensuring
    the application continues with an empty tool list.

    Args:
        sso_token: Optional SSO token for authentication (pre-refreshed).

    Returns:
        List of available MCP tools (empty list if all connections fail).
    """
    servers = _get_server_configs()
    enabled = {k: v for k, v in servers.items() if v.get("enabled", False)}

    if not enabled:
        logger.warning("No MCP servers enabled")
        return []

    logger.info(f"Connecting to {len(enabled)} MCP server(s): {', '.join(enabled)}")

    has_auth = bool(sso_token)
    results = await asyncio.gather(
        *[
            _connect_single_server(
                name=name,
                config=_build_server_config(entry, sso_token),
                timeout=entry.get("timeout", 30),
                required=has_auth,
            )
            for name, entry in enabled.items()
        ]
    )

    # Deduplicate tools by name (first occurrence wins)
    seen = set()
    tools = []
    for tool_list in results:
        for tool in tool_list:
            if tool.name not in seen:
                seen.add(tool.name)
                tools.append(tool)
            else:
                logger.warning(f"Duplicate tool '{tool.name}' skipped")

    if not tools:
        if sso_token:
            logger.warning("All MCP servers failed to load tools")
        else:
            logger.info("MCP tools deferred — no auth token at startup")
        return []

    logger.info(f"Loaded {len(tools)} MCP tool(s): {', '.join(seen)}")
    return tools
