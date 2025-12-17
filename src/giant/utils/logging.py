"""Structured logging configuration using structlog.

Provides correlation IDs for tracing across concurrent runs and
configurable output formats (JSON for production, colored console for dev).
"""

import logging
import sys
from collections.abc import MutableMapping
from contextvars import ContextVar
from typing import Any, cast

import structlog
from structlog.types import Processor

from giant.config import settings

# Context variables for correlation IDs
_run_id: ContextVar[str | None] = ContextVar("run_id", default=None)
_item_id: ContextVar[str | None] = ContextVar("item_id", default=None)
_step: ContextVar[int | None] = ContextVar("step", default=None)


def set_correlation_context(
    run_id: str | None = None,
    item_id: str | None = None,
    step: int | None = None,
) -> None:
    """Set correlation IDs for the current async context.

    Args:
        run_id: Unique identifier for the agent run
        item_id: Benchmark item ID (e.g., slide identifier)
        step: Current navigation step number
    """
    if run_id is not None:
        _run_id.set(run_id)
    if item_id is not None:
        _item_id.set(item_id)
    if step is not None:
        _step.set(step)


def clear_correlation_context() -> None:
    """Clear all correlation context variables."""
    _run_id.set(None)
    _item_id.set(None)
    _step.set(None)


def _add_correlation_ids(
    logger: logging.Logger,
    method_name: str,
    event_dict: MutableMapping[str, Any],
) -> MutableMapping[str, Any]:
    """Structlog processor to add correlation IDs to log events."""
    _ = logger, method_name  # Required by structlog processor signature
    run_id = _run_id.get()
    item_id = _item_id.get()
    step = _step.get()

    if run_id is not None:
        event_dict["run_id"] = run_id
    if item_id is not None:
        event_dict["item_id"] = item_id
    if step is not None:
        event_dict["step"] = step

    return event_dict


def configure_logging(
    level: str | None = None,
    log_format: str | None = None,
) -> None:
    """Configure structlog with the specified settings.

    Args:
        level: Log level (DEBUG, INFO, WARNING, ERROR, CRITICAL).
               Defaults to settings.LOG_LEVEL.
        log_format: Output format ("console" or "json").
                    Defaults to settings.LOG_FORMAT.
    """
    level = level or settings.LOG_LEVEL
    log_format = log_format or settings.LOG_FORMAT

    # Shared processors for all output formats
    shared_processors: list[Processor] = [
        structlog.contextvars.merge_contextvars,
        structlog.stdlib.add_log_level,
        structlog.stdlib.add_logger_name,
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.StackInfoRenderer(),
        structlog.processors.UnicodeDecoder(),
        _add_correlation_ids,
    ]

    if log_format == "json":
        # JSON output for production
        processors: list[Processor] = [
            *shared_processors,
            structlog.processors.format_exc_info,
            structlog.processors.JSONRenderer(),
        ]
    else:
        # Colored console output for development
        processors = [
            *shared_processors,
            structlog.dev.ConsoleRenderer(colors=True),
        ]

    structlog.configure(
        processors=processors,
        wrapper_class=structlog.stdlib.BoundLogger,
        context_class=dict,
        logger_factory=structlog.stdlib.LoggerFactory(),
        cache_logger_on_first_use=True,
    )

    # Configure stdlib logging to match
    logging.basicConfig(
        format="%(message)s",
        stream=sys.stdout,
        level=getattr(logging, level.upper()),
    )


def get_logger(name: str | None = None) -> structlog.stdlib.BoundLogger:
    """Get a structlog logger instance.

    Args:
        name: Logger name. If None, uses the calling module's name.

    Returns:
        A bound structlog logger instance.
    """
    return cast(structlog.stdlib.BoundLogger, structlog.get_logger(name))
