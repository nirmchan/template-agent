"""Interactive chat and one-shot ask commands."""

from __future__ import annotations

import json
import uuid
from typing import Any, AsyncIterator, Optional

from deep_agent.cli._log import get_logger
from deep_agent.cli.auth import auth_headers_for_request, get_valid_token

logger = get_logger()


async def stream_agent_response(
    url: str,
    headers: dict[str, str],
    thread_id: str,
    message: str,
    stream_tokens: bool = True,
) -> AsyncIterator[Any]:
    """POST run/stream and yield parsed ``data:`` JSON payloads until ``event: end``."""
    import httpx

    base = url.rstrip("/")
    target = f"{base}/threads/{thread_id}/runs/stream"
    body: dict[str, Any] = {
        "assistant_id": "agent",
        "input": {"messages": [{"role": "human", "content": message}]},
        "stream_mode": ["updates", "messages"] if stream_tokens else ["updates"],
        "config": {"configurable": {"thread_id": thread_id}},
    }
    req_headers = {
        **headers,
        "Content-Type": "application/json",
        "Accept": "text/event-stream",
    }
    timeout = httpx.Timeout(300.0, connect=30.0, read=300.0, write=30.0, pool=30.0)
    async with httpx.AsyncClient(timeout=timeout) as client:
        async with client.stream(
            "POST", target, json=body, headers=req_headers
        ) as resp:
            resp.raise_for_status()
            current_event = ""
            async for raw_line in resp.aiter_lines():
                line = raw_line.rstrip("\r")
                if line.startswith("event:"):
                    current_event = line[len("event:") :].strip()
                    continue
                if line.startswith("data:"):
                    payload = line[len("data:") :].lstrip()
                    if current_event == "end":
                        return
                    if not payload.strip():
                        continue
                    try:
                        yield json.loads(payload)
                    except json.JSONDecodeError:
                        logger.warning(
                            "cli_chat_sse_json_error",
                            thread_id=thread_id,
                            payload_preview=payload[:200],
                        )
                        continue


def _extract_text_and_tool_hint(payload: Any) -> tuple[str, Optional[str]]:
    """Extract human text and optional tool-call summary from one SSE data payload."""
    text_parts: list[str] = []
    tool_hint: Optional[str] = None

    if isinstance(payload, dict):
        msg_type = str(payload.get("type") or "")
        content = payload.get("content")
        if msg_type in ("ai", "AIMessage", "AIMessageChunk") and isinstance(
            content, str
        ):
            text_parts.append(content)
        elif isinstance(content, str) and msg_type not in ("tool", "tool_call"):
            text_parts.append(content)
        tool_calls = payload.get("tool_calls")
        if tool_calls is not None:
            tool_hint = json.dumps(tool_calls, default=str)[:500]
        elif msg_type in ("tool", "tool_call"):
            tool_hint = json.dumps(payload, default=str)[:500]
    elif isinstance(payload, list):
        for item in payload:
            if not isinstance(item, dict):
                continue
            t = str(item.get("type") or "")
            c = item.get("content")
            if t in (
                "AIMessageChunk",
                "AIMessage",
                "ai",
            ) and isinstance(c, str):
                text_parts.append(c)
            if item.get("tool_calls") is not None:
                tool_hint = json.dumps(item["tool_calls"], default=str)[:500]
    return ("".join(text_parts), tool_hint)


async def render_stream(
    stream: AsyncIterator[Any],
    console: Any,
) -> str:
    """Consume the SSE payload stream; show tool lines dim; return full assistant text."""
    from rich.markdown import Markdown

    buffer: list[str] = []
    async for payload in stream:
        text, tool_hint = _extract_text_and_tool_hint(payload)
        if tool_hint:
            console.print(f"[dim]{tool_hint}[/dim]")
        if text:
            buffer.append(text)

    full_text = "".join(buffer)
    if full_text.strip():
        console.print(Markdown(full_text))
    return full_text


async def create_thread(url: str, headers: dict[str, str]) -> str:
    """POST ``/threads`` and return ``thread_id`` from the JSON body."""
    import httpx

    base = url.rstrip("/")
    target = f"{base}/threads"
    req_headers = {**headers, "Content-Type": "application/json"}
    timeout = httpx.Timeout(60.0, connect=15.0)
    async with httpx.AsyncClient(timeout=timeout) as client:
        resp = await client.post(target, headers=req_headers, json={})
        resp.raise_for_status()
        data = resp.json()
    if not isinstance(data, dict):
        raise RuntimeError("create thread response was not a JSON object")
    tid = data.get("thread_id")
    if not tid:
        raise RuntimeError("create thread response missing thread_id")
    return str(tid)


def _resolve_thread_id(
    *,
    thread_opt: Optional[str],
    force_new: bool,
    url: str,
    headers: dict[str, str],
) -> str:
    """Pick thread id: server create, CLI option, or client UUID."""
    import asyncio

    if force_new:
        return asyncio.run(create_thread(url, headers))
    if thread_opt:
        return thread_opt.strip()
    return uuid.uuid4().hex


async def _async_one_shot(
    *,
    console: Any,
    url: str,
    headers: dict[str, str],
    thread_id: str,
    message: str,
) -> None:
    stream = stream_agent_response(url, headers, thread_id, message, stream_tokens=True)
    await render_stream(stream, console)


async def _async_repl(
    *,
    console: Any,
    url: str,
    headers: dict[str, str],
    initial_thread_id: str,
) -> None:
    from rich.prompt import Prompt

    thread_id = initial_thread_id
    console.print(f"Thread: [bold]{thread_id}[/bold] (commands: /new, /thread, exit)")

    while True:
        try:
            line = Prompt.ask(">")
        except (EOFError, KeyboardInterrupt):
            console.print("\n[dim]Bye.[/dim]")
            return

        user = (line or "").strip()
        if not user:
            continue
        lowered = user.lower()
        if lowered in ("exit", "quit", "/bye"):
            console.print("[dim]Bye.[/dim]")
            return
        if lowered == "/new":
            thread_id = await create_thread(url, headers)
            console.print(f"New thread: [bold]{thread_id}[/bold]")
            continue
        if lowered == "/thread":
            console.print(thread_id)
            continue

        stream = stream_agent_response(
            url, headers, thread_id, user, stream_tokens=True
        )
        await render_stream(stream, console)


def chat_cmd(
    message: Optional[str],
    thread_id: Optional[str],
    url: Optional[str],
    new: bool,
    console: Any,
) -> None:
    """Run interactive REPL or one-shot chat (sync entry; uses ``asyncio.run`` internally)."""
    import asyncio

    try:
        base_url, token = get_valid_token(url)
    except (ValueError, RuntimeError) as exc:
        console.print(f"[red]{exc}[/red]")
        raise SystemExit(1) from exc

    headers = auth_headers_for_request(base_url, token)

    tid = _resolve_thread_id(
        thread_opt=thread_id, force_new=new, url=base_url, headers=headers
    )

    if message is not None and message.strip():
        asyncio.run(
            _async_one_shot(
                console=console,
                url=base_url,
                headers=headers,
                thread_id=tid,
                message=message.strip(),
            )
        )
        return

    asyncio.run(
        _async_repl(
            console=console,
            url=base_url,
            headers=headers,
            initial_thread_id=tid,
        )
    )


def ask_cmd(
    message: str,
    thread_id: Optional[str],
    url: Optional[str],
    console: Any,
) -> None:
    """One-shot message (no REPL)."""
    chat_cmd(message=message, thread_id=thread_id, url=url, new=False, console=console)
