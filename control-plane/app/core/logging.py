"""Structured JSON logging via structlog.

Emits one JSON object per log line with a severity level and timestamp.
A redaction processor drops sensitive keys so secrets never reach the logs.
"""

from __future__ import annotations

import logging
from typing import Any

import structlog

# Keys whose values must never be logged (working rule: never log secrets).
_SENSITIVE_KEYS = frozenset(
    {
        "password",
        "password_hash",
        "token",
        "access_token",
        "refresh_token",
        "authorization",
        "api_key",
        "secret",
        "key_hash",
        "set-cookie",
        "cookie",
    }
)

_REDACTED = "***REDACTED***"


def _redact_processor(
    _logger: object, _method: str, event_dict: dict[str, Any]
) -> dict[str, Any]:
    """Redact sensitive values from the structured event."""
    for key in list(event_dict.keys()):
        if key.lower() in _SENSITIVE_KEYS:
            event_dict[key] = _REDACTED
    return event_dict


def configure_logging(level: str = "INFO") -> None:
    """Configure structlog + stdlib logging for JSON output.

    Args:
        level: Minimum log level name (e.g. "INFO", "DEBUG").
    """
    log_level = getattr(logging, level.upper(), logging.INFO)
    logging.basicConfig(format="%(message)s", level=log_level)

    structlog.configure(
        processors=[
            structlog.contextvars.merge_contextvars,
            structlog.processors.add_log_level,
            structlog.processors.TimeStamper(fmt="iso", utc=True),
            _redact_processor,
            structlog.processors.dict_tracebacks,
            structlog.processors.JSONRenderer(),
        ],
        wrapper_class=structlog.make_filtering_bound_logger(log_level),
        cache_logger_on_first_use=True,
    )


def get_logger(name: str | None = None) -> structlog.stdlib.BoundLogger:
    """Return a bound structlog logger."""
    return structlog.get_logger(name)
