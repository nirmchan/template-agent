"""Config file helpers for the CLI."""

from __future__ import annotations

import json
import os
import tempfile
from pathlib import Path
from typing import Any

from deep_agent.cli._log import get_logger
from deep_agent.cli.constants import MISSING_URL_MSG

logger = get_logger()


def get_config_dir() -> Path:
    """Return ``~/.config/{CONFIG_DIR_NAME}/``, creating directories if needed."""
    from deep_agent.cli.constants import CONFIG_DIR_NAME

    base = Path.home() / ".config" / CONFIG_DIR_NAME
    base.mkdir(parents=True, exist_ok=True)
    return base


def _config_path() -> Path:
    return get_config_dir() / "config.json"


def load_config() -> dict[str, Any]:
    """Read ``config.json``; return an empty dict if missing or invalid."""
    path = _config_path()
    if not path.is_file():
        return {}
    try:
        raw = path.read_text(encoding="utf-8")
        data = json.loads(raw)
    except (OSError, json.JSONDecodeError) as exc:
        logger.warning(
            "cli_config_load_failed",
            path=str(path),
            error=str(exc),
        )
        return {}
    if not isinstance(data, dict):
        return {}
    return data


def save_config(data: dict[str, Any]) -> None:
    """Write ``config.json`` atomically (tmp file + replace)."""
    path = _config_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = json.dumps(data, indent=2, sort_keys=True) + "\n"
    fd, tmppath = tempfile.mkstemp(
        prefix=".config-",
        suffix=".json",
        dir=path.parent,
        text=True,
    )
    tmp = Path(tmppath)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as fh:
            fh.write(payload)
        os.replace(tmp, path)
    except Exception:
        try:
            tmp.unlink(missing_ok=True)
        except OSError:
            logger.warning("cli_config_temp_cleanup_failed", path=str(tmp))
        raise


def get_url() -> str | None:
    """URL from config only (no flag, no env)."""
    cfg = load_config()
    u = cfg.get("url")
    if u is None:
        return None
    s = str(u).strip()
    return s or None


def get_token() -> str | None:
    """Secret used for API calls (access token or API key) from config."""
    cfg = load_config()
    auth = cfg.get("auth")
    if not isinstance(auth, dict):
        return None
    for key in ("access_token", "api_key"):
        val = auth.get(key)
        if val:
            return str(val).strip() or None
    return None


def get_aliases() -> dict[str, str]:
    """Return the ``aliases`` dict from config (name -> url)."""
    cfg = load_config()
    raw = cfg.get("aliases")
    if not isinstance(raw, dict):
        return {}
    return {str(k): str(v) for k, v in raw.items() if v}


def resolve_alias(name: str) -> str | None:
    """Look up *name* in saved aliases; return URL or None."""
    return get_aliases().get(name)


def resolve_url(url_option: str | None) -> str:
    """Precedence: CLI flag/alias > ``AGENT_URL`` > config ``url`` > error."""
    if url_option:
        u = url_option.strip().rstrip("/")
        if u:
            aliased = resolve_alias(u)
            if aliased:
                return aliased.strip().rstrip("/")
            return u
    env = os.environ.get("AGENT_URL", "").strip()
    if env:
        return env.rstrip("/")
    cfg_url = get_url()
    if cfg_url:
        return str(cfg_url).strip().rstrip("/")
    raise ValueError(MISSING_URL_MSG)


def url_or_env_display() -> str | None:
    """Non-secret URL from env or config (for messaging)."""
    env = os.environ.get("AGENT_URL", "").strip()
    if env:
        return env.rstrip("/")
    return get_url()
