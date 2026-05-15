"""HTTP auth discovery, OAuth browser login, API key prompt, token refresh."""

from __future__ import annotations

import base64
import hashlib
import secrets
import time
import urllib.parse
import webbrowser
from typing import Any

import httpx
import jwt
from rich.prompt import Prompt

from deep_agent.cli._log import get_logger
from deep_agent.cli.constants import CLI_NAME, LOGIN_REQUIRED_MSG

logger = get_logger()

_DEFAULT_DISCOVER_TIMEOUT = 15.0


def discover_auth(agent_url: str) -> dict[str, Any]:
    """GET ``{agent_url}/auth/discover`` or return ``auth_type: none``."""
    base = agent_url.rstrip("/")
    url = f"{base}/auth/discover"
    try:
        resp = httpx.get(url, timeout=_DEFAULT_DISCOVER_TIMEOUT)
        if resp.status_code == 404:
            return {"auth_type": "none"}
        resp.raise_for_status()
        data = resp.json()
    except (httpx.HTTPError, ValueError, TypeError) as exc:
        logger.warning(
            "cli_auth_discover_failed",
            url=url,
            error=str(exc),
        )
        return {"auth_type": "none"}

    if not isinstance(data, dict):
        return {"auth_type": "none"}
    auth_type = data.get("auth_type", "none")
    if auth_type not in ("sso", "api_key", "none"):
        auth_type = "none"
    out: dict[str, Any] = {
        "auth_type": auth_type,
        "authorization_endpoint": str(data.get("authorization_endpoint", "") or ""),
        "token_endpoint": str(data.get("token_endpoint", "") or ""),
        "client_id": str(data.get("client_id", "") or ""),
        "scopes": data.get("scopes") if isinstance(data.get("scopes"), list) else [],
    }
    return out


def _pkce_verifier() -> str:
    return secrets.token_urlsafe(32)


def _pkce_challenge(verifier: str) -> str:
    digest = hashlib.sha256(verifier.encode("utf-8")).digest()
    return base64.urlsafe_b64encode(digest).decode("utf-8").rstrip("=")


def browser_login(auth_config: dict[str, Any], agent_url: str) -> dict[str, Any]:
    """OAuth2 authorization code + PKCE via agent-hosted callback."""
    auth_endpoint = (auth_config.get("authorization_endpoint") or "").strip()
    token_endpoint = (auth_config.get("token_endpoint") or "").strip()
    client_id = (auth_config.get("client_id") or "").strip()
    client_secret = (auth_config.get("client_secret") or "").strip()
    callback_url = (auth_config.get("cli_callback_url") or "").strip()
    scopes_raw = auth_config.get("scopes") or []
    scopes = [str(s) for s in scopes_raw] if isinstance(scopes_raw, list) else []

    if not auth_endpoint or not token_endpoint or not client_id or not callback_url:
        raise RuntimeError("SSO configuration from server is incomplete")

    state = secrets.token_urlsafe(16)
    code_verifier = _pkce_verifier()
    code_challenge = _pkce_challenge(code_verifier)
    scope_str = " ".join(scopes) if scopes else "openid"

    query = urllib.parse.urlencode(
        {
            "response_type": "code",
            "client_id": client_id,
            "redirect_uri": callback_url,
            "scope": scope_str,
            "state": state,
            "code_challenge": code_challenge,
            "code_challenge_method": "S256",
        }
    )
    authorize_url = f"{auth_endpoint}?{query}"

    logger.info("cli_oauth_browser_open", authorize_url=auth_endpoint)
    try:
        webbrowser.open(authorize_url, new=1, autoraise=True)
    except Exception as exc:
        logger.warning("cli_oauth_browser_failed", error=str(exc))

    poll_url = f"{agent_url.rstrip('/')}/auth/cli/poll"
    code = _poll_for_code(poll_url, state, timeout=120)

    return _exchange_code(
        code=code,
        redirect_uri=callback_url,
        token_endpoint=token_endpoint,
        client_id=client_id,
        client_secret=client_secret,
        code_verifier=code_verifier,
    )


def _poll_for_code(poll_url: str, state: str, timeout: int = 120) -> str:
    """Poll the agent's ``/auth/cli/poll`` until a code arrives."""
    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            resp = httpx.get(poll_url, params={"state": state}, timeout=10)
            data = resp.json()
        except (httpx.HTTPError, ValueError):
            time.sleep(2)
            continue
        status = data.get("status", "")
        if status == "ready":
            code = data.get("code", "")
            if code:
                return str(code)
            raise RuntimeError("Agent returned ready but no code")
        if status == "expired":
            raise RuntimeError("Login timed out on the server side")
        time.sleep(2)
    raise TimeoutError(f"No login callback received within {timeout}s")


def _exchange_code(
    *,
    code: str,
    redirect_uri: str,
    token_endpoint: str,
    client_id: str,
    client_secret: str,
    code_verifier: str,
) -> dict[str, Any]:
    """Exchange an authorization code for tokens."""
    form: dict[str, str] = {
        "grant_type": "authorization_code",
        "code": code,
        "redirect_uri": redirect_uri,
        "client_id": client_id,
        "code_verifier": code_verifier,
    }
    if client_secret:
        form["client_secret"] = client_secret
    try:
        resp = httpx.post(
            token_endpoint,
            data=form,
            headers={"Content-Type": "application/x-www-form-urlencoded"},
            timeout=30,
        )
        resp.raise_for_status()
        parsed = resp.json()
    except httpx.HTTPStatusError as exc:
        detail = exc.response.text if exc.response else str(exc)
        raise RuntimeError(
            f"Token exchange failed: HTTP "
            f"{exc.response.status_code if exc.response else '?'} {detail}"
        ) from exc
    except (httpx.HTTPError, ValueError) as exc:
        raise RuntimeError(f"Token exchange failed: {exc}") from exc

    if not isinstance(parsed, dict):
        raise RuntimeError("Token response was not a JSON object")
    access = parsed.get("access_token")
    if not access or not isinstance(access, str):
        raise RuntimeError("Token response missing access_token")

    result: dict[str, Any] = {
        "access_token": access,
        "refresh_token": str(parsed.get("refresh_token") or ""),
        "expires_in": parsed.get("expires_in"),
        "token_endpoint": token_endpoint,
        "client_id": client_id,
    }
    if client_secret:
        result["client_secret"] = client_secret
    return result


def api_key_login() -> dict[str, Any]:
    """Prompt for an API key (masked)."""
    key = Prompt.ask("API key", password=True)
    if not key or not str(key).strip():
        raise RuntimeError("API key is required")
    return {"api_key": str(key).strip(), "auth_type": "api_key"}


def is_token_expired(token: str, buffer_seconds: int = 30) -> bool:
    """Return True if JWT ``exp`` is within ``buffer_seconds`` of now (unverified decode)."""
    if not token or token.count(".") != 2:
        return False
    try:
        claims = jwt.decode(
            token,
            options={"verify_signature": False},
            algorithms=["HS256", "RS256", "ES256"],
        )
    except jwt.DecodeError:
        return False
    exp = claims.get("exp")
    if exp is None:
        return False
    try:
        exp_f = float(exp)
    except (TypeError, ValueError):
        return False
    return time.time() >= exp_f - buffer_seconds


def refresh_tokens(config: dict[str, Any]) -> dict[str, Any] | None:
    """POST refresh_token grant; return updated full config or ``None``."""
    auth = config.get("auth")
    if not isinstance(auth, dict):
        return None
    refresh = auth.get("refresh_token")
    token_ep = auth.get("token_endpoint")
    client_id = auth.get("client_id")
    client_secret = auth.get("client_secret", "")
    if not refresh or not token_ep or not client_id:
        return None
    form: dict[str, str] = {
        "grant_type": "refresh_token",
        "refresh_token": str(refresh),
        "client_id": str(client_id),
    }
    if client_secret:
        form["client_secret"] = str(client_secret)
    try:
        resp = httpx.post(
            str(token_ep),
            data=form,
            headers={"Content-Type": "application/x-www-form-urlencoded"},
            timeout=30,
        )
        resp.raise_for_status()
        body = resp.json()
    except (httpx.HTTPError, ValueError) as exc:
        logger.warning("cli_token_refresh_failed", error=str(exc))
        return None

    if not isinstance(body, dict):
        return None
    access = body.get("access_token")
    if not access or not isinstance(access, str):
        return None

    new_auth = dict(auth)
    new_auth["access_token"] = access
    if body.get("refresh_token"):
        new_auth["refresh_token"] = str(body["refresh_token"])
    if body.get("expires_in") is not None:
        new_auth["expires_in"] = body["expires_in"]

    merged = dict(config)
    merged["auth"] = new_auth
    return merged


def get_valid_token(url_override: str | None = None) -> tuple[str, str]:
    """Return ``(agent_url, secret_or_bearer_token)`` for API calls."""
    from deep_agent.cli.config import load_config, resolve_url, save_config

    url = resolve_url(url_override)
    cfg = load_config()
    discovered = discover_auth(url)
    atype = str(discovered.get("auth_type") or "none")
    if atype == "none":
        return url, ""

    auth_raw = cfg.get("auth")
    auth: dict[str, Any] = auth_raw if isinstance(auth_raw, dict) else {}

    if atype == "api_key":
        key = auth.get("api_key")
        if not key:
            raise RuntimeError(LOGIN_REQUIRED_MSG)
        return url, str(key)

    if atype == "sso":
        token = auth.get("access_token")
        if not token:
            raise RuntimeError(LOGIN_REQUIRED_MSG)
        token_str = str(token)
        if is_token_expired(token_str):
            updated = refresh_tokens(cfg)
            if not updated:
                raise RuntimeError(
                    f"Session expired. Run `{CLI_NAME} login` to sign in again."
                )
            save_config(updated)
            cfg = updated
            refreshed_auth = cfg.get("auth")
            auth = refreshed_auth if isinstance(refreshed_auth, dict) else {}
            token_str = str(auth.get("access_token") or "")
            if not token_str:
                raise RuntimeError(LOGIN_REQUIRED_MSG)
        return url, token_str

    raise RuntimeError(LOGIN_REQUIRED_MSG)


def auth_headers_for_request(agent_url: str, token: str) -> dict[str, str]:
    """Map a stored secret to request headers using current server auth mode."""
    if not token:
        return {}
    mode = discover_auth(agent_url).get("auth_type")
    if mode == "api_key":
        return {"X-API-Key": token}
    return {"Authorization": f"Bearer {token}"}
