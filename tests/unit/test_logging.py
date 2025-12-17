"""Tests for giant.utils.logging module."""

from __future__ import annotations

import json
import logging

import pytest

from giant.utils.logging import (
    clear_correlation_context,
    configure_logging,
    get_logger,
    set_correlation_context,
)


def _read_last_json_log_line(capsys: pytest.CaptureFixture[str]) -> dict[str, object]:
    captured = capsys.readouterr()
    lines = [line for line in captured.out.splitlines() if line.strip()]
    assert lines, "Expected at least one log line on stdout"
    return json.loads(lines[-1])


def test_configure_logging_sets_root_level() -> None:
    configure_logging(level="WARNING", log_format="console")
    assert logging.getLogger().level == logging.WARNING


def test_configure_logging_default_settings_do_not_error() -> None:
    configure_logging()


def test_get_logger_returns_logger_proxy() -> None:
    configure_logging(level="DEBUG", log_format="console")
    logger = get_logger("test.module")
    assert hasattr(logger, "info")
    assert hasattr(logger, "debug")
    assert hasattr(logger, "warning")
    assert hasattr(logger, "error")


def test_json_log_is_valid_and_contains_correlation_ids(
    capsys: pytest.CaptureFixture[str],
) -> None:
    configure_logging(level="INFO", log_format="json")
    expected_step = 7
    set_correlation_context(run_id="run-123", item_id="item-456", step=expected_step)

    logger = get_logger("test.json")
    logger.info("hello", foo="bar")
    payload = _read_last_json_log_line(capsys)

    assert payload["event"] == "hello"
    assert payload["foo"] == "bar"
    assert payload["run_id"] == "run-123"
    assert payload["item_id"] == "item-456"
    assert payload["step"] == expected_step
    assert payload["level"] == "info"
    assert payload["logger"] == "test.json"
    assert "timestamp" in payload


def test_json_log_omits_correlation_ids_when_unset(
    capsys: pytest.CaptureFixture[str],
) -> None:
    configure_logging(level="INFO", log_format="json")
    clear_correlation_context()

    logger = get_logger("test.json")
    logger.info("hello")
    payload = _read_last_json_log_line(capsys)

    assert payload["event"] == "hello"
    assert payload["logger"] == "test.json"
    assert "run_id" not in payload
    assert "item_id" not in payload
    assert "step" not in payload
