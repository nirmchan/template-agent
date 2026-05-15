"""HTTP helpers and Typer commands for LangGraph thread APIs."""

from __future__ import annotations

import json
from datetime import datetime
from typing import Any, Optional

import httpx

from deep_agent.utils.pylogger import get_python_logger

logger = get_python_logger()

_DEFAULT_TIMEOUT = 30.0


def list_threads(
    url: str, headers: dict[str, str], limit: int = 20
) -> list[dict[str, Any]]:
    """GET ``/threads?limit=`` and return a list of thread dicts."""
    base = url.rstrip("/")
    target = f"{base}/threads"
    resp = httpx.get(
        target,
        params={"limit": limit},
        headers=headers,
        timeout=_DEFAULT_TIMEOUT,
    )
    resp.raise_for_status()
    data = resp.json()
    if isinstance(data, list):
        return [t for t in data if isinstance(t, dict)]
    if isinstance(data, dict):
        for key in ("items", "threads", "data"):
            chunk = data.get(key)
            if isinstance(chunk, list):
                return [t for t in chunk if isinstance(t, dict)]
    logger.warning("cli_threads_list_unexpected_shape", preview=json.dumps(data)[:300])
    return []


def get_thread_state(
    url: str, headers: dict[str, str], thread_id: str
) -> dict[str, Any]:
    """GET ``/threads/{thread_id}/state``."""
    base = url.rstrip("/")
    tid = thread_id.strip()
    target = f"{base}/threads/{tid}/state"
    resp = httpx.get(target, headers=headers, timeout=_DEFAULT_TIMEOUT)
    resp.raise_for_status()
    body = resp.json()
    if not isinstance(body, dict):
        msg = "thread state response was not a JSON object"
        raise ValueError(msg)
    return body


def delete_thread(url: str, headers: dict[str, str], thread_id: str) -> None:
    """DELETE ``/threads/{thread_id}``; raises ``httpx.HTTPStatusError`` on failure."""
    base = url.rstrip("/")
    tid = thread_id.strip()
    target = f"{base}/threads/{tid}"
    resp = httpx.delete(target, headers=headers, timeout=_DEFAULT_TIMEOUT)
    resp.raise_for_status()


def _values_messages(state: dict[str, Any]) -> list[Any]:
    values = state.get("values")
    if not isinstance(values, dict):
        return []
    msgs = values.get("messages")
    if not isinstance(msgs, list):
        return []
    return msgs


def _message_preview_from_state(
    state: dict[str, Any], max_len: int = 80
) -> tuple[int, str]:
    msgs = _values_messages(state)
    count = len(msgs)
    if not msgs:
        return count, ""
    last = msgs[-1]
    text = _message_content_preview(last)
    text_one_line = " ".join(text.split())
    if len(text_one_line) > max_len:
        return count, text_one_line[: max_len - 1] + "…"
    return count, text_one_line


def _message_content_preview(msg_obj: Any) -> str:
    if msg_obj is None:
        return ""
    if isinstance(msg_obj, str):
        return msg_obj
    if isinstance(msg_obj, dict):
        for key in ("content", "text"):
            raw = msg_obj.get(key)
            if isinstance(raw, str):
                return raw
            if isinstance(raw, list):
                parts: list[str] = []
                for block in raw:
                    if isinstance(block, str):
                        parts.append(block)
                    elif isinstance(block, dict) and isinstance(block.get("text"), str):
                        parts.append(str(block["text"]))
                if parts:
                    return "".join(parts)
        extra = msg_obj.get("kwargs")
        if isinstance(extra, dict) and isinstance(extra.get("content"), str):
            return str(extra["content"])
        return json.dumps(msg_obj, default=str)[:500]
    return str(msg_obj)


def _message_role(msg_obj: Any) -> str:
    if isinstance(msg_obj, dict):
        t = str(msg_obj.get("type") or "").lower()
        if t in ("human", "user"):
            return "human"
        if t in ("ai", "assistant"):
            return "ai"
        role = str(msg_obj.get("role") or "").lower()
        if role in ("human", "user"):
            return "human"
        if role in ("ai", "assistant"):
            return "ai"
    return ""


def _format_created(created: Any) -> str:
    if created is None:
        return ""
    s = str(created).strip()
    if not s:
        return ""
    try:
        raw = s.replace("Z", "+00:00")
        dt = datetime.fromisoformat(raw)
    except ValueError:
        return s
    if dt.tzinfo:
        return dt.strftime("%Y-%m-%d %H:%M %Z")
    return dt.strftime("%Y-%m-%d %H:%M")


def register_thread_commands(app: Any) -> None:
    """Attach ``threads`` subcommands to the main CLI app."""
    import typer as typer_mod
    from rich.console import Console

    from deep_agent.cli import auth as auth_mod
    from deep_agent.cli.constants import CLI_NAME

    console = Console(stderr=True)
    threads_app = typer_mod.Typer(
        help="Manage conversation threads.",
        no_args_is_help=True,
    )

    @threads_app.command("list")
    def threads_list_cmd(
        limit: int = typer_mod.Option(
            20, "--limit", "-l", help="Maximum threads to fetch."
        ),
        url: Optional[str] = typer_mod.Option(
            None,
            "--url",
            help="Agent base URL (overrides env and config).",
        ),
    ) -> None:
        """List recent threads with timestamps and message counts."""
        from rich.table import Table

        try:
            base_url, token = auth_mod.get_valid_token(url)
        except (ValueError, RuntimeError) as exc:
            console.print(f"[red]{exc}[/red]")
            raise typer_mod.Exit(code=1) from exc

        headers = auth_mod.auth_headers_for_request(base_url, token)

        try:
            threads = list_threads(base_url, headers, limit=limit)
        except httpx.HTTPError as exc:
            logger.warning("cli_threads_list_failed", error=str(exc))
            console.print(f"[red]Failed to list threads: {exc}[/red]")
            raise typer_mod.Exit(code=1) from exc

        table = Table(title="Threads")
        table.add_column("Thread ID", overflow="fold")
        table.add_column("Created")
        table.add_column("Messages", justify="right")
        table.add_column("Last Message Preview", overflow="fold")

        for trec in threads:
            tid = str(
                trec.get("thread_id") or trec.get("threadId") or trec.get("id") or ""
            )
            if not tid:
                continue
            created_src = trec.get("created_at") or trec.get("createdAt")
            created_disp = _format_created(created_src)
            try:
                st = get_thread_state(base_url, headers, tid)
                n_msgs, preview = _message_preview_from_state(st)
            except (httpx.HTTPError, ValueError) as exc:
                logger.warning(
                    "cli_threads_state_for_list_failed",
                    thread_id=tid,
                    error=str(exc),
                )
                n_msgs, preview = 0, f"(state error: {exc})"

            table.add_row(tid, created_disp, str(n_msgs), preview)

        console.print(table)

    @threads_app.command("show")
    def threads_show_cmd(
        thread_id: str = typer_mod.Argument(..., help="Thread identifier."),
        url: Optional[str] = typer_mod.Option(
            None,
            "--url",
            help="Agent base URL (overrides env and config).",
        ),
    ) -> None:
        """Print the full conversation for a thread."""
        from rich.markdown import Markdown

        try:
            base_url, token = auth_mod.get_valid_token(url)
        except (ValueError, RuntimeError) as exc:
            console.print(f"[red]{exc}[/red]")
            raise typer_mod.Exit(code=1) from exc

        headers = auth_mod.auth_headers_for_request(base_url, token)

        try:
            state = get_thread_state(base_url, headers, thread_id)
        except httpx.HTTPError as exc:
            console.print(f"[red]Failed to load thread: {exc}[/red]")
            raise typer_mod.Exit(code=1) from exc

        for msg in _values_messages(state):
            role = _message_role(msg)
            text = _message_content_preview(msg)
            if role == "human":
                console.print("[bold]You:[/bold]")
                console.print(text or "(empty)")
            else:
                label = "Assistant:" if role == "ai" else "Message:"
                console.print(f"[bold]{label}[/bold]")
                if text.strip():
                    console.print(Markdown(text))
                else:
                    console.print("(empty)")

    @threads_app.command("delete")
    def threads_delete_cmd(
        thread_id: str = typer_mod.Argument(..., help="Thread identifier."),
        url: Optional[str] = typer_mod.Option(
            None,
            "--url",
            help="Agent base URL (overrides env and config).",
        ),
        force: bool = typer_mod.Option(
            False, "--force", "-f", help="Skip confirmation."
        ),
    ) -> None:
        """Delete a thread."""
        from rich.prompt import Confirm

        try:
            base_url, token = auth_mod.get_valid_token(url)
        except (ValueError, RuntimeError) as exc:
            console.print(f"[red]{exc}[/red]")
            raise typer_mod.Exit(code=1) from exc

        headers = auth_mod.auth_headers_for_request(base_url, token)

        tid = thread_id.strip()
        if not force:
            confirmed = Confirm.ask(f"Delete thread [bold]{tid}[/bold]?", default=False)
            if not confirmed:
                console.print("[dim]Cancelled.[/dim]")
                return

        try:
            delete_thread(base_url, headers, tid)
        except httpx.HTTPStatusError as exc:
            logger.warning(
                "cli_threads_delete_http_error",
                thread_id=tid,
                status_code=exc.response.status_code if exc.response else None,
            )
            console.print(f"[red]Delete failed: {exc}[/red]")
            raise typer_mod.Exit(code=1) from exc
        except httpx.HTTPError as exc:
            console.print(f"[red]Delete failed: {exc}[/red]")
            raise typer_mod.Exit(code=1) from exc

        console.print(f"[green]Deleted thread {tid}.[/green]")
        logger.info("cli_thread_deleted", thread_id=tid, cli=CLI_NAME)

    app.add_typer(threads_app, name="threads")
