"""Worker pool configuration for Aegra deployment.

Defines settings for Aegra worker concurrency, task
queues, and resource limits. These values are read by aegra.json
and by the Aegra container entrypoint.

Environment variables:
    AEGRA_NUM_WORKERS: Number of worker processes (default: 4)
    AEGRA_MAX_CONCURRENT: Max concurrent graph invocations per worker (default: 10)
    AEGRA_TASK_TIMEOUT: Seconds before a task is killed (default: 300)
    AEGRA_QUEUE_SIZE: Max pending tasks in the queue (default: 100)
    AEGRA_GRACEFUL_SHUTDOWN: Seconds to wait for in-flight tasks (default: 30)
"""

import os
from typing import Any

from deep_agent.utils.pylogger import get_python_logger

logger = get_python_logger()

NUM_WORKERS = int(os.environ.get("AEGRA_NUM_WORKERS", "4"))
MAX_CONCURRENT = int(os.environ.get("AEGRA_MAX_CONCURRENT", "10"))
TASK_TIMEOUT = int(os.environ.get("AEGRA_TASK_TIMEOUT", "300"))
QUEUE_SIZE = int(os.environ.get("AEGRA_QUEUE_SIZE", "100"))
GRACEFUL_SHUTDOWN = int(os.environ.get("AEGRA_GRACEFUL_SHUTDOWN", "30"))
HEARTBEAT_INTERVAL = int(os.environ.get("AEGRA_HEARTBEAT_INTERVAL", "10"))


def get_worker_config() -> dict[str, Any]:
    """Return the full worker configuration dict."""
    return {
        "num_workers": NUM_WORKERS,
        "max_concurrent": MAX_CONCURRENT,
        "task_timeout_seconds": TASK_TIMEOUT,
        "queue_size": QUEUE_SIZE,
        "graceful_shutdown_seconds": GRACEFUL_SHUTDOWN,
        "heartbeat_interval_seconds": HEARTBEAT_INTERVAL,
        "effective_capacity": NUM_WORKERS * MAX_CONCURRENT,
    }


def validate_worker_config() -> list[str]:
    """Validate worker configuration and return a list of warnings."""
    warnings: list[str] = []
    cfg = get_worker_config()

    if cfg["num_workers"] < 1:
        warnings.append("AEGRA_NUM_WORKERS must be >= 1")
    if cfg["num_workers"] > 32:
        warnings.append("AEGRA_NUM_WORKERS > 32 may cause resource exhaustion")

    if cfg["max_concurrent"] < 1:
        warnings.append("AEGRA_MAX_CONCURRENT must be >= 1")

    if cfg["task_timeout_seconds"] < 30:
        warnings.append("AEGRA_TASK_TIMEOUT < 30s may cause premature task kills")
    if cfg["task_timeout_seconds"] > 3600:
        warnings.append("AEGRA_TASK_TIMEOUT > 3600s — tasks may hang without feedback")

    if cfg["queue_size"] < cfg["effective_capacity"]:
        warnings.append(
            f"AEGRA_QUEUE_SIZE ({cfg['queue_size']}) < effective capacity "
            f"({cfg['effective_capacity']}) — queue may reject tasks under load"
        )

    for w in warnings:
        logger.warning("Worker config: %s", w)

    return warnings


def log_worker_config() -> None:
    """Log the current worker configuration at INFO level."""
    cfg = get_worker_config()
    logger.info(
        "Aegra worker pool: %d workers × %d concurrent = %d capacity, "
        "timeout=%ds, queue=%d, shutdown=%ds",
        cfg["num_workers"],
        cfg["max_concurrent"],
        cfg["effective_capacity"],
        cfg["task_timeout_seconds"],
        cfg["queue_size"],
        cfg["graceful_shutdown_seconds"],
    )
