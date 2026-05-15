"""Unit tests for CLI interrupt helpers."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

from deep_agent.cli import interrupts as intr_mod


def test_check_for_interrupt_returns_payload() -> None:
    state = {
        "values": {"messages": []},
        "tasks": [
            {
                "id": "task-9",
                "interrupts": [{"value": "Proceed?", "task_id": "task-9"}],
            },
        ],
    }
    intr = intr_mod.check_for_interrupt(state)
    assert intr is not None
    assert intr["value"] == "Proceed?"
    assert intr["task_id"] == "task-9"


def test_check_for_interrupt_fills_task_id_from_task() -> None:
    state = {
        "tasks": [
            {"id": "outer-1", "interrupts": [{"value": "Pick one"}]},
        ],
    }
    intr = intr_mod.check_for_interrupt(state)
    assert intr is not None
    assert intr["task_id"] == "outer-1"


def test_check_for_interrupt_none_when_clean() -> None:
    assert intr_mod.check_for_interrupt({"tasks": []}) is None
    assert intr_mod.check_for_interrupt({"tasks": None}) is None
    assert intr_mod.check_for_interrupt({}) is None


def test_format_interrupt_question_and_options() -> None:
    console = MagicMock()
    text = intr_mod.format_interrupt(
        {
            "value": {
                "question": "Choose",
                "options": ["A", "B"],
            }
        },
        console,
    )
    assert "Choose" in text
    assert "1. A" in text
    assert "2. B" in text


def test_format_interrupt_plain_string() -> None:
    assert intr_mod.format_interrupt({"value": "Hello?"}, MagicMock()) == "Hello?"


def test_format_interrupt_empty_dict_returns_empty() -> None:
    assert intr_mod.format_interrupt({}, MagicMock()) == ""


def test_build_resume_input_structure() -> None:
    body = intr_mod.build_resume_input("yes", {"task_id": "t1"})
    assert body == {"input": {"resume": "yes"}, "config": {}}


def test_handle_interrupt_flow_no_interrupt() -> None:
    out = intr_mod.handle_interrupt_flow(
        "http://x",
        {},
        "tid",
        {"tasks": []},
        MagicMock(),
    )
    assert out is None


def test_handle_interrupt_flow_prompts() -> None:
    console = MagicMock()
    state = {
        "tasks": [{"id": "t1", "interrupts": [{"value": "OK?"}]}],
    }
    with patch("rich.prompt.Prompt.ask", return_value="sure"):
        out = intr_mod.handle_interrupt_flow(
            "http://x",
            {},
            "tid-2",
            state,
            console,
        )
    assert out == "sure"
    console.print.assert_called()
