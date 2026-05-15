"""Detect human-in-the-loop interrupts from thread state and build resume payloads."""

from __future__ import annotations

import json
from typing import Any

from deep_agent.cli._log import get_logger

logger = get_logger()


def check_for_interrupt(thread_state: dict[str, Any]) -> dict[str, Any] | None:
    """Return the first interrupt payload if ``tasks[].interrupts`` is non-empty.

    The returned dict includes at least ``value`` and ``task_id`` when available.
    """
    tasks = thread_state.get("tasks")
    if not isinstance(tasks, list):
        return None

    for task in tasks:
        if not isinstance(task, dict):
            continue
        interrupts = task.get("interrupts")
        if not interrupts:
            continue
        if not isinstance(interrupts, list):
            continue

        task_id = task.get("task_id") or task.get("id") or ""

        for intr in interrupts:
            if not isinstance(intr, dict):
                continue
            merged: dict[str, Any] = dict(intr)
            existing_tid = merged.get("task_id")
            if existing_tid is None or str(existing_tid).strip() == "":
                merged["task_id"] = task_id
            return merged

    return None


def format_interrupt(interrupt: dict[str, Any], console: Any) -> str:
    """Return human-readable interrupt text (question and optional numbered options)."""
    _ = console
    if not interrupt:
        return ""

    lines: list[str] = []
    value = interrupt.get("value")

    opts = interrupt.get("options")
    if not isinstance(opts, list) and isinstance(value, dict):
        opts = value.get("options")

    if isinstance(value, dict):
        q = (
            value.get("question")
            or value.get("prompt")
            or value.get("message")
            or value.get("text")
        )
        if q is not None and str(q).strip():
            lines.append(str(q).strip())
        elif opts is None:
            try:
                lines.append(json.dumps(value, indent=2, default=str))
            except TypeError:
                lines.append(str(value))
    elif value is not None:
        lines.append(str(value).strip())

    if isinstance(opts, list) and opts:
        for i, opt in enumerate(opts, start=1):
            lines.append(f"  {i}. {opt}")

    return "\n".join(lines).strip()


def build_resume_input(user_response: str, interrupt: dict[str, Any]) -> dict[str, Any]:
    """Build the JSON body to resume a run after an interrupt.

    ``interrupt`` is accepted for forward-compatible extensions (e.g. attaching
    ``task_id`` into ``config`` later). Shape matches LangGraph ``Command(resume=…)``.
    """
    _ = interrupt
    return {
        "input": {"resume": user_response},
        "config": {},
    }


def handle_interrupt_flow(
    url: str,
    headers: dict[str, str],
    thread_id: str,
    thread_state: dict[str, Any],
    console: Any,
) -> str | None:
    """If the thread is interrupted, display the prompt and ask for input.

    Returns the user's response string, or ``None`` when there is no interrupt.
    ``url``, ``headers``, and ``thread_id`` are reserved for callers that need
    correlation logging or future server-assisted prompts.
    """
    _ = url, headers
    intr = check_for_interrupt(thread_state)
    if not intr:
        return None

    logger.info(
        "cli_interrupt_detected",
        thread_id=thread_id,
        task_id=intr.get("task_id"),
    )

    text = format_interrupt(intr, console)
    if text:
        console.print(text)

    from rich.prompt import Prompt

    return str(Prompt.ask("Your response"))
