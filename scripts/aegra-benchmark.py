#!/usr/bin/env python3
"""Performance benchmarks for aegra modules (MR-42).

Measures serialization speed, state roundtrip latency, and
converter throughput without requiring a running agent.

Usage:
    python scripts/aegra-benchmark.py
"""

import sys
import time  # noqa: E402
from pathlib import Path

_PROJECT_ROOT = str(Path(__file__).resolve().parent.parent)
if _PROJECT_ROOT not in sys.path:
    sys.path.insert(0, _PROJECT_ROOT)

from langchain_core.messages import AIMessage, HumanMessage, ToolMessage  # noqa: E402

from deep_agent.aegra.converters import (  # noqa: E402
    extract_final_response,
    langgraph_messages_to_dicts,
    stream_request_to_langgraph_input,
)
from deep_agent.aegra.serialization import (  # noqa: E402
    deserialize_state,
    serialize_state,
    state_from_json,
    state_to_json,
)
from deep_agent.aegra.state import (  # noqa: E402
    AegraMetadata,
    make_health_status,
    serialize_metadata,
)


def _build_large_state(num_turns: int) -> dict:
    """Build a realistic multi-turn conversation state."""
    messages = []
    for i in range(num_turns):
        messages.append(HumanMessage(content=f"User message {i}: What is my BMI?"))
        messages.append(
            AIMessage(
                content=f"Response {i}: Your BMI is 24.7",
                tool_calls=[
                    {
                        "id": f"tc-{i}",
                        "name": "calculate_bmi",
                        "args": {"height_cm": 180, "weight_kg": 80},
                    }
                ],
            )
        )
        messages.append(
            ToolMessage(
                content='{"bmi": 24.7, "category": "Normal"}',
                tool_call_id=f"tc-{i}",
                name="calculate_bmi",
            )
        )
    return {"messages": messages}


def benchmark(name: str, fn, iterations: int = 1000):
    """Run a benchmark and print results."""
    # Warmup
    for _ in range(min(10, iterations)):
        fn()

    start = time.perf_counter()
    for _ in range(iterations):
        fn()
    elapsed = time.perf_counter() - start

    per_op = (elapsed / iterations) * 1_000_000
    ops_per_sec = iterations / elapsed
    print(f"  {name:.<50s} {per_op:>8.1f} us/op  ({ops_per_sec:>8.0f} ops/s)")


def run_benchmarks():
    """Execute all aegra benchmarks and print results."""
    print("=" * 70)
    print("AEGRA PERFORMANCE BENCHMARKS")
    print("=" * 70)

    small_state = _build_large_state(3)
    medium_state = _build_large_state(20)
    large_state = _build_large_state(100)

    print("\n--- Serialization ---")
    benchmark("serialize_state (3 turns)", lambda: serialize_state(small_state))
    benchmark("serialize_state (20 turns)", lambda: serialize_state(medium_state))
    benchmark("serialize_state (100 turns)", lambda: serialize_state(large_state), 100)

    print("\n--- Deserialization ---")
    small_ser = serialize_state(small_state)
    medium_ser = serialize_state(medium_state)
    large_ser = serialize_state(large_state)
    benchmark("deserialize_state (3 turns)", lambda: deserialize_state(small_ser))
    benchmark("deserialize_state (20 turns)", lambda: deserialize_state(medium_ser))
    benchmark(
        "deserialize_state (100 turns)", lambda: deserialize_state(large_ser), 100
    )

    print("\n--- JSON roundtrip ---")
    benchmark("state_to_json (20 turns)", lambda: state_to_json(medium_state))
    medium_json = state_to_json(medium_state)
    benchmark("state_from_json (20 turns)", lambda: state_from_json(medium_json))

    print("\n--- Converters ---")
    benchmark(
        "stream_request_to_langgraph_input",
        lambda: stream_request_to_langgraph_input("Hello world"),
    )
    benchmark(
        "langgraph_messages_to_dicts (20 turns)",
        lambda: langgraph_messages_to_dicts(medium_state["messages"]),
    )
    benchmark(
        "extract_final_response (20 turns)",
        lambda: extract_final_response(medium_state),
    )

    print("\n--- Metadata ---")
    meta: AegraMetadata = {
        "run_id": "r1",
        "trace_id": "t1",
        "thread_id": "th1",
        "error_count": 0,
        "last_error": None,
    }
    benchmark("serialize_metadata", lambda: serialize_metadata(meta))
    benchmark(
        "make_health_status",
        lambda: make_health_status(
            agent_name="test",
            model="gemini",
            mcp_tools_count=4,
            subagents_count=2,
            backend_ready=True,
        ),
    )

    print("\n" + "=" * 70)
    print("DONE")


if __name__ == "__main__":
    run_benchmarks()
