"""Unit tests for aegra worker configuration."""

from unittest.mock import patch

import pytest

from deep_agent.aegra.worker import (
    get_worker_config,
    log_worker_config,
    validate_worker_config,
)


class TestGetWorkerConfig:
    def test_returns_all_keys(self):
        cfg = get_worker_config()
        expected_keys = {
            "num_workers",
            "max_concurrent",
            "task_timeout_seconds",
            "queue_size",
            "graceful_shutdown_seconds",
            "heartbeat_interval_seconds",
            "effective_capacity",
        }
        assert expected_keys == set(cfg.keys())

    def test_effective_capacity(self):
        cfg = get_worker_config()
        assert cfg["effective_capacity"] == cfg["num_workers"] * cfg["max_concurrent"]


class TestValidateWorkerConfig:
    def test_defaults_are_valid(self):
        warnings = validate_worker_config()
        assert len(warnings) == 0

    def test_warns_num_workers_below_one(self):
        with patch("deep_agent.aegra.worker.NUM_WORKERS", 0):
            warnings = validate_worker_config()
            assert any("must be >= 1" in w for w in warnings)

    def test_warns_num_workers_above_32(self):
        with patch("deep_agent.aegra.worker.NUM_WORKERS", 64):
            warnings = validate_worker_config()
            assert any("resource exhaustion" in w for w in warnings)

    def test_warns_max_concurrent_below_one(self):
        with patch("deep_agent.aegra.worker.MAX_CONCURRENT", 0):
            warnings = validate_worker_config()
            assert any("MAX_CONCURRENT must be >= 1" in w for w in warnings)

    def test_warns_timeout_too_low(self):
        with patch("deep_agent.aegra.worker.TASK_TIMEOUT", 10):
            warnings = validate_worker_config()
            assert any("premature" in w for w in warnings)

    def test_warns_timeout_too_high(self):
        with patch("deep_agent.aegra.worker.TASK_TIMEOUT", 7200):
            warnings = validate_worker_config()
            assert any("hang" in w for w in warnings)

    def test_warns_queue_smaller_than_capacity(self):
        with (
            patch("deep_agent.aegra.worker.NUM_WORKERS", 10),
            patch("deep_agent.aegra.worker.MAX_CONCURRENT", 20),
            patch("deep_agent.aegra.worker.QUEUE_SIZE", 5),
        ):
            warnings = validate_worker_config()
            assert any("reject tasks" in w for w in warnings)


class TestLogWorkerConfig:
    def test_does_not_raise(self):
        log_worker_config()
