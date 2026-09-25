"""Structured logging setup.

JobPilot logs as structured events (key-value pairs) rather than freeform
strings, so operational logs can be filtered and aggregated in a log
platform without regex parsing. In development, events render as
human-readable console lines; in production, they render as JSON lines.
"""

from __future__ import annotations

import logging
import sys
from typing import Any

import structlog

_CONFIGURED = False


def configure_logging(level: str = "INFO", fmt: str = "console") -> None:
    """Configure structlog + stdlib logging. Idempotent."""

    global _CONFIGURED
    if _CONFIGURED:
        return

    shared_processors: list[Any] = [
        structlog.contextvars.merge_contextvars,
        structlog.stdlib.add_log_level,
        structlog.stdlib.add_logger_name,
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.StackInfoRenderer(),
        structlog.processors.format_exc_info,
    ]

    if fmt == "json":
        renderer: Any = structlog.processors.JSONRenderer()
    else:
        renderer = structlog.dev.ConsoleRenderer()

    structlog.configure(
        processors=[*shared_processors, structlog.stdlib.ProcessorFormatter.wrap_for_formatter],
        logger_factory=structlog.stdlib.LoggerFactory(),
        wrapper_class=structlog.stdlib.BoundLogger,
        cache_logger_on_first_use=True,
    )

    formatter = structlog.stdlib.ProcessorFormatter(
        processors=[structlog.stdlib.ProcessorFormatter.remove_processors_meta, renderer],
        foreign_pre_chain=shared_processors,
    )

    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(formatter)

    root = logging.getLogger()
    root.handlers = [handler]
    root.setLevel(level.upper())

    _CONFIGURED = True


def get_logger(name: str) -> structlog.stdlib.BoundLogger:
    """Return a bound structlog logger for `name`.

    Callers should bind request/turn-scoped context (e.g. `turn_id`,
    `user_id`) via `logger.bind(...)` rather than interpolating them
    into the message string.
    """

    if not _CONFIGURED:
        configure_logging()
    return structlog.get_logger(name)
