"""Typer entrypoint: ``ask`` console script."""

from __future__ import annotations

import importlib.metadata
import json
from typing import Any, Optional

import httpx
import typer
from rich.console import Console

from deep_agent.cli.config import load_config, resolve_url, save_config
from deep_agent.cli.constants import (
    APP_DESCRIPTION,
    CLI_DISABLED_MSG,
    CLI_NAME,
    is_cli_enabled,
)
from deep_agent.cli.threads import register_thread_commands

app = typer.Typer(name=CLI_NAME, help=APP_DESCRIPTION, no_args_is_help=True)
console = Console(stderr=True)

register_thread_commands(app)

config_app = typer.Typer(help="Manage CLI configuration.", no_args_is_help=True)
config_set_app = typer.Typer(
    help="Persist a configuration value.", no_args_is_help=True
)
alias_app = typer.Typer(help="Manage agent URL aliases.", no_args_is_help=True)
app.add_typer(config_app, name="config")
config_app.add_typer(config_set_app, name="set")
config_app.add_typer(alias_app, name="alias")


def _version_str() -> str:
    try:
        return importlib.metadata.version("template-agent")
    except importlib.metadata.PackageNotFoundError:
        return "0.0.0"


def _version_callback(value: bool) -> None:
    if value:
        typer.echo(_version_str())
        raise typer.Exit()


@app.callback()
def _main(
    _version: bool = typer.Option(
        False,
        "--version",
        callback=_version_callback,
        is_eager=True,
    ),
) -> None:
    """Deep Agent CLI."""
    if not is_cli_enabled():
        console.print(f"[red]{CLI_DISABLED_MSG}[/red]")
        raise typer.Exit(code=1)


def _mask_value(val: str, visible: int = 4) -> str:
    if len(val) <= visible:
        return "***"
    return f"{'*' * (len(val) - visible)}{val[-visible:]}"


def _masked_config_view(cfg: dict[str, Any]) -> dict[str, Any]:
    out: dict[str, Any] = json.loads(json.dumps(cfg))
    auth_o = out.get("auth")
    if isinstance(auth_o, dict):
        for key in ("access_token", "refresh_token", "api_key"):
            if key in auth_o and auth_o[key]:
                auth_o[key] = _mask_value(str(auth_o[key]))
    return out


@config_set_app.command("url")
def config_set_url(url: str = typer.Argument(..., metavar="URL")) -> None:
    """Save the default agent base URL."""
    cfg = load_config()
    cfg["url"] = url.strip().rstrip("/")
    save_config(cfg)
    console.print(f"Saved URL for [bold]{CLI_NAME}[/bold].")


@config_set_app.command("token")
def config_set_token(token: str = typer.Argument(..., metavar="TOKEN")) -> None:
    """Save a literal bearer/API token (prefer ``login`` for SSO)."""
    cfg = load_config()
    auth = cfg.get("auth")
    if not isinstance(auth, dict):
        auth = {}
    auth["access_token"] = token.strip()
    cfg["auth"] = auth
    save_config(cfg)
    console.print(f"Saved token in [bold]{CLI_NAME}[/bold] config.")


@config_app.command("show")
def config_show() -> None:
    """Print effective configuration (secrets masked)."""
    cfg = load_config()
    if not cfg:
        console.print("(empty config)")
        return
    console.print(json.dumps(_masked_config_view(cfg), indent=2))


@alias_app.command("add")
def alias_add(
    name: str = typer.Argument(..., help="Short name for the agent."),
    url: str = typer.Argument(..., help="Agent base URL."),
) -> None:
    """Save a named agent URL alias (e.g. ``prod``, ``local``)."""
    cfg = load_config()
    aliases = cfg.get("aliases")
    if not isinstance(aliases, dict):
        aliases = {}
    aliases[name.strip()] = url.strip().rstrip("/")
    cfg["aliases"] = aliases
    save_config(cfg)
    console.print(f"Alias [bold]{name}[/bold] -> {url}")


@alias_app.command("remove")
def alias_remove(
    name: str = typer.Argument(..., help="Alias to remove."),
) -> None:
    """Remove a saved agent URL alias."""
    cfg = load_config()
    aliases = cfg.get("aliases")
    if not isinstance(aliases, dict) or name.strip() not in aliases:
        console.print(f"[yellow]Alias '{name}' not found.[/yellow]")
        raise typer.Exit(code=1)
    del aliases[name.strip()]
    cfg["aliases"] = aliases
    save_config(cfg)
    console.print(f"Removed alias [bold]{name}[/bold].")


@alias_app.command("list")
def alias_list() -> None:
    """List all saved agent URL aliases."""
    from deep_agent.cli.config import get_aliases

    aliases = get_aliases()
    if not aliases:
        console.print("(no aliases)")
        return
    for name, url in sorted(aliases.items()):
        console.print(f"  [bold]{name}[/bold]  ->  {url}")


@app.command("login")
def login_cmd(
    url: Optional[str] = typer.Option(
        None,
        "--url",
        help="Agent base URL (overrides env and config).",
    ),
) -> None:
    """Authenticate with the agent (browser SSO or API key) and store credentials."""
    from deep_agent.cli import auth as auth_mod

    try:
        agent_url = resolve_url(url)
    except ValueError as exc:
        console.print(f"[red]{exc}[/red]")
        raise typer.Exit(code=1) from exc

    discovered = auth_mod.discover_auth(agent_url)
    atype = discovered.get("auth_type", "none")

    if atype == "none":
        console.print("No auth required.")
        return

    cfg = load_config()
    auth_raw = cfg.get("auth")
    auth: dict[str, Any] = auth_raw if isinstance(auth_raw, dict) else {}

    if atype == "sso":
        try:
            tokens = auth_mod.browser_login(discovered)
        except Exception as exc:
            console.print(f"[red]Login failed: {exc}[/red]")
            raise typer.Exit(code=1) from exc
        auth.update(
            {
                "auth_type": "sso",
                "access_token": tokens["access_token"],
                "refresh_token": tokens.get("refresh_token") or "",
                "token_endpoint": tokens.get("token_endpoint") or "",
                "client_id": tokens.get("client_id") or "",
            }
        )
        if tokens.get("expires_in") is not None:
            auth["expires_in"] = tokens["expires_in"]
    elif atype == "api_key":
        try:
            bundle = auth_mod.api_key_login()
        except Exception as exc:
            console.print(f"[red]{exc}[/red]")
            raise typer.Exit(code=1) from exc
        auth.update(
            {
                "auth_type": "api_key",
                "api_key": bundle["api_key"],
            }
        )
    else:
        console.print(f"[red]Unsupported auth type: {atype}[/red]")
        raise typer.Exit(code=1)

    cfg["auth"] = auth
    cfg["url"] = agent_url
    save_config(cfg)
    console.print("[green]Login successful. Credentials saved.[/green]")


@app.command("ping")
def ping_cmd(
    url: Optional[str] = typer.Option(
        None,
        "--url",
        help="Agent base URL (overrides env and config).",
    ),
) -> None:
    """Check connectivity to the agent (uses stored credentials when required)."""
    from deep_agent.cli import auth as auth_mod

    try:
        agent_url, token = auth_mod.get_valid_token(url)
    except ValueError as exc:
        console.print(f"[red]{exc}[/red]")
        raise typer.Exit(code=1) from exc
    except RuntimeError as exc:
        console.print(f"[red]{exc}[/red]")
        raise typer.Exit(code=1) from exc

    headers = auth_mod.auth_headers_for_request(agent_url, token)
    target = f"{agent_url.rstrip('/')}/livez"
    try:
        resp = httpx.get(target, headers=headers, timeout=15.0)
        resp.raise_for_status()
    except httpx.HTTPError as exc:
        console.print(f"[red]Request failed: {exc}[/red]")
        raise typer.Exit(code=1) from exc

    console.print(f"[green]OK[/green] {target} -> {resp.status_code}")


@app.command("chat")
def chat_cmd(
    message: Optional[str] = typer.Argument(
        None,
        help="Message to send; omit for interactive REPL.",
    ),
    thread_id: Optional[str] = typer.Option(
        None,
        "--thread",
        "-t",
        help="Continue an existing thread.",
    ),
    url: Optional[str] = typer.Option(
        None,
        "--url",
        help="Agent base URL (overrides env and config).",
    ),
    new: bool = typer.Option(
        False,
        "--new",
        "-n",
        help="Create a new thread on the server.",
    ),
) -> None:
    """Interactive chat session with the agent."""
    from deep_agent.cli import chat as chat_mod

    chat_mod.chat_cmd(
        message=message,
        thread_id=thread_id,
        url=url,
        new=new,
        console=console,
    )


@app.command("ask")
def ask_cmd(
    message: str = typer.Argument(..., help="Message to send."),
    thread_id: Optional[str] = typer.Option(
        None,
        "--thread",
        "-t",
        help="Continue an existing thread.",
    ),
    url: Optional[str] = typer.Option(
        None,
        "--url",
        help="Agent base URL (overrides env and config).",
    ),
) -> None:
    """Send a single message to the agent (one-shot)."""
    from deep_agent.cli import chat as chat_mod

    chat_mod.ask_cmd(message=message, thread_id=thread_id, url=url, console=console)
