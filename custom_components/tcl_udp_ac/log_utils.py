"""Logging helpers for TCL UDP AC integration."""

from __future__ import annotations

import logging
from typing import Any


def _format_fields(fields: dict[str, Any]) -> str:
    parts = []
    for key, value in fields.items():
        if value is None:
            continue
        parts.append(f"{key}={value}")
    return ", ".join(parts)


def log_event(logger: logging.Logger, level: int, event: str, **fields: Any) -> None:
    """Log an event with structured key/value details."""
    details = _format_fields(fields)
    if details:
        logger.log(level, "%s | %s", event, details)
    else:
        logger.log(level, "%s", event)


def log_debug(logger: logging.Logger, event: str, **fields: Any) -> None:
    """Log a debug event."""
    log_event(logger, logging.DEBUG, event, **fields)


def log_info(logger: logging.Logger, event: str, **fields: Any) -> None:
    """Log an info event."""
    log_event(logger, logging.INFO, event, **fields)


def log_warning(logger: logging.Logger, event: str, **fields: Any) -> None:
    """Log a warning event."""
    log_event(logger, logging.WARNING, event, **fields)


def log_error(logger: logging.Logger, event: str, **fields: Any) -> None:
    """Log an error event."""
    log_event(logger, logging.ERROR, event, **fields)
