"""Unit tests for CLI chat streaming and thread helpers."""

from __future__ import annotations

import io
from unittest.mock import MagicMock, patch

import pytest

from deep_agent.cli import chat as chat_mod


@pytest.mark.asyncio
async def test_stream_agent_response_yields_json_and_stops_on_end() -> None:
    lines = [
        "event: updates",
        'data: {"type":"ai","content":"Hello"}',
        "event: messages/partial",
        'data: [{"type":"AIMessageChunk","content":"!"}]',
        "event: end",
        "data:",
    ]

    class FakeResp:
        async def aiter_lines(self):
            for ln in lines:
                yield ln

        def raise_for_status(self) -> None:
            return None

    class FakeStreamCtx:
        async def __aenter__(self) -> FakeResp:
            return FakeResp()

        async def __aexit__(self, *args: object) -> None:
            return None

    class FakeClient:
        def __init__(self, *args: object, **kwargs: object) -> None:
            pass

        def stream(self, *args: object, **kwargs: object) -> FakeStreamCtx:
            return FakeStreamCtx()

        async def __aenter__(self) -> FakeClient:
            return self

        async def __aexit__(self, *args: object) -> None:
            return None

    with patch("httpx.AsyncClient", return_value=FakeClient()):
        out: list[object] = []
        async for payload in chat_mod.stream_agent_response(
            "http://agent.test",
            {},
            "thr1",
            "hi",
        ):
            out.append(payload)

    assert out == [
        {"type": "ai", "content": "Hello"},
        [{"type": "AIMessageChunk", "content": "!"}],
    ]


@pytest.mark.asyncio
async def test_render_stream_accumulates_text() -> None:
    from rich.console import Console

    async def gen():
        yield {"type": "ai", "content": "Hello "}
        yield {"type": "ai", "content": "world"}

    buf = io.StringIO()
    console = Console(file=buf, width=120, force_terminal=True)
    text = await chat_mod.render_stream(gen(), console)
    assert text == "Hello world"


@pytest.mark.asyncio
async def test_create_thread_posts_to_threads_endpoint() -> None:
    class Resp:
        def raise_for_status(self) -> None:
            return None

        def json(self) -> dict[str, str]:
            return {"thread_id": "abc-123"}

    class Client:
        def __init__(self, *args: object, **kwargs: object) -> None:
            pass

        async def post(self, url: str, **kwargs: object) -> Resp:
            assert url == "http://agent.test/threads"
            assert kwargs.get("json") == {}
            return Resp()

        async def __aenter__(self) -> Client:
            return self

        async def __aexit__(self, *args: object) -> None:
            return None

    with patch("httpx.AsyncClient", return_value=Client()):
        tid = await chat_mod.create_thread("http://agent.test", {"X-API-Key": "k"})
    assert tid == "abc-123"


@pytest.mark.parametrize("exit_line", ["exit", "quit", "/bye"])
@pytest.mark.asyncio
async def test_async_repl_exits_on_commands(exit_line: str) -> None:
    from rich.console import Console

    console = Console(file=io.StringIO(), width=80, force_terminal=True)
    prompt_mock = MagicMock(side_effect=[exit_line])

    with patch("rich.prompt.Prompt.ask", prompt_mock):
        await chat_mod._async_repl(
            console=console,
            url="http://agent.test",
            headers={},
            initial_thread_id="t1",
        )

    prompt_mock.assert_called()
