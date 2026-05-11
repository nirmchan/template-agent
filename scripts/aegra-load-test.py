#!/usr/bin/env python3
"""Load test for aegra LangGraph Platform deployment (MR-33).

Sends concurrent requests to the LangGraph API and measures
throughput, latency percentiles, and error rates.

Usage:
    python scripts/aegra-load-test.py --url http://127.0.0.1:2024 --concurrency 10 --requests 50

Requires: httpx (already a dev dependency)
"""

import argparse
import asyncio
import statistics
import sys
import time
from dataclasses import dataclass, field

import httpx

ASSISTANT_ID = "agent"
TEST_MESSAGE = "Hello, what can you do? Keep your answer to one sentence."


@dataclass
class LoadTestResult:
    """Aggregated load test results."""

    total_requests: int = 0
    successful: int = 0
    failed: int = 0
    latencies_ms: list[float] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)
    start_time: float = 0.0
    end_time: float = 0.0

    @property
    def duration_s(self) -> float:
        """Total test duration in seconds."""
        return self.end_time - self.start_time

    @property
    def rps(self) -> float:
        """Requests per second."""
        return self.total_requests / self.duration_s if self.duration_s > 0 else 0

    @property
    def error_rate(self) -> float:
        """Fraction of requests that failed."""
        return self.failed / self.total_requests if self.total_requests > 0 else 0

    def summary(self) -> str:
        """Format results as a human-readable report."""
        lines = [
            "=" * 60,
            "AEGRA LOAD TEST RESULTS",
            "=" * 60,
            f"Total requests:    {self.total_requests}",
            f"Successful:        {self.successful}",
            f"Failed:            {self.failed}",
            f"Error rate:        {self.error_rate:.1%}",
            f"Duration:          {self.duration_s:.1f}s",
            f"Throughput:        {self.rps:.1f} req/s",
        ]
        if self.latencies_ms:
            lines.extend(
                [
                    f"Latency p50:       {statistics.median(self.latencies_ms):.0f}ms",
                    f"Latency p95:       {_percentile(self.latencies_ms, 95):.0f}ms",
                    f"Latency p99:       {_percentile(self.latencies_ms, 99):.0f}ms",
                    f"Latency mean:      {statistics.mean(self.latencies_ms):.0f}ms",
                    f"Latency min:       {min(self.latencies_ms):.0f}ms",
                    f"Latency max:       {max(self.latencies_ms):.0f}ms",
                ]
            )
        if self.errors:
            lines.append("\nFirst 5 errors:")
            for err in self.errors[:5]:
                lines.append(f"  - {err}")
        lines.append("=" * 60)
        return "\n".join(lines)


async def _send_request(
    client: httpx.AsyncClient,
    base_url: str,
    result: LoadTestResult,
    semaphore: asyncio.Semaphore,
) -> None:
    """Send a single request to the LangGraph API."""
    async with semaphore:
        result.total_requests += 1
        start = time.perf_counter()

        try:
            thread_resp = await client.post(f"{base_url}/threads", json={})
            thread_resp.raise_for_status()
            thread_id = thread_resp.json()["thread_id"]

            run_resp = await client.post(
                f"{base_url}/threads/{thread_id}/runs/wait",
                json={
                    "assistant_id": ASSISTANT_ID,
                    "input": {"messages": [{"role": "human", "content": TEST_MESSAGE}]},
                },
                timeout=120,
            )
            run_resp.raise_for_status()
            elapsed_ms = (time.perf_counter() - start) * 1000
            result.successful += 1
            result.latencies_ms.append(elapsed_ms)
        except Exception as exc:
            elapsed_ms = (time.perf_counter() - start) * 1000
            result.failed += 1
            result.errors.append(f"{type(exc).__name__}: {exc}")
            result.latencies_ms.append(elapsed_ms)


async def run_load_test(
    base_url: str, concurrency: int, total_requests: int
) -> LoadTestResult:
    """Execute the load test with the given parameters."""
    result = LoadTestResult()
    semaphore = asyncio.Semaphore(concurrency)

    async with httpx.AsyncClient(timeout=120) as client:
        result.start_time = time.perf_counter()
        tasks = [
            _send_request(client, base_url, result, semaphore)
            for _ in range(total_requests)
        ]
        await asyncio.gather(*tasks)
        result.end_time = time.perf_counter()

    return result


def _percentile(data: list[float], pct: float) -> float:
    """Calculate a percentile value from a sorted list."""
    sorted_data = sorted(data)
    idx = int(len(sorted_data) * pct / 100)
    return sorted_data[min(idx, len(sorted_data) - 1)]


def main():
    """Parse CLI args and run the load test."""
    parser = argparse.ArgumentParser(description="Aegra Load Test")
    parser.add_argument(
        "--url", default="http://127.0.0.1:2024", help="LangGraph API URL"
    )
    parser.add_argument(
        "--concurrency", type=int, default=5, help="Concurrent requests"
    )
    parser.add_argument("--requests", type=int, default=20, help="Total requests")
    args = parser.parse_args()

    print(
        f"Starting load test: {args.requests} requests, {args.concurrency} concurrent"
    )
    print(f"Target: {args.url}")
    print()

    result = asyncio.run(run_load_test(args.url, args.concurrency, args.requests))
    print(result.summary())

    sys.exit(1 if result.error_rate > 0.1 else 0)


if __name__ == "__main__":
    main()
