"""Structured logging configured explicitly at the application boundary."""

from __future__ import annotations

import json
import logging
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, TextIO


class JsonFormatter(logging.Formatter):
    """Render log records as stable JSON objects."""

    def format(self, record: logging.LogRecord) -> str:
        """Serialize one record without mutating it."""
        timestamp = datetime.fromtimestamp(record.created, tz=timezone.utc).isoformat()
        payload: dict[str, Any] = {
            "timestamp": timestamp,
            "level": record.levelname,
            "logger": record.name,
            "event": getattr(record, "event", record.getMessage()),
            "context": getattr(record, "context", {}),
        }
        if record.exc_info:
            payload["exception"] = self.formatException(record.exc_info)
        return json.dumps(payload, ensure_ascii=False, sort_keys=True, default=str)


class StructuredLogger:
    """Small typed facade that keeps event names separate from context."""

    def __init__(self, logger: logging.Logger) -> None:
        self._logger = logger

    @property
    def logger(self) -> logging.Logger:
        """Expose the underlying standard-library logger for integration."""
        return self._logger

    def debug(self, event: str, **context: object) -> None:
        self._log(logging.DEBUG, event, context)

    def info(self, event: str, **context: object) -> None:
        self._log(logging.INFO, event, context)

    def warning(self, event: str, **context: object) -> None:
        self._log(logging.WARNING, event, context)

    def error(self, event: str, **context: object) -> None:
        self._log(logging.ERROR, event, context)

    def exception(self, event: str, **context: object) -> None:
        self._logger.exception(
            event,
            extra={"event": event, "context": context},
        )

    def _log(self, level: int, event: str, context: dict[str, object]) -> None:
        self._logger.log(
            level,
            event,
            extra={"event": event, "context": context},
        )


def configure_logging(
    *,
    level: str | int = "INFO",
    name: str = "word_madness_bot",
    stream: TextIO | None = None,
    log_file: Path | None = None,
) -> StructuredLogger:
    """Configure and return the package logger.

    Filesystem access occurs only when the caller explicitly supplies
    ``log_file``. Repeated calls replace this package logger's handlers instead
    of duplicating output.
    """
    package_logger = logging.getLogger(name)
    package_logger.setLevel(level)
    package_logger.propagate = False
    package_logger.handlers.clear()

    formatter = JsonFormatter()
    stream_handler = logging.StreamHandler(stream or sys.stderr)
    stream_handler.setFormatter(formatter)
    package_logger.addHandler(stream_handler)

    if log_file is not None:
        log_file.parent.mkdir(parents=True, exist_ok=True)
        file_handler = logging.FileHandler(log_file, encoding="utf-8")
        file_handler.setFormatter(formatter)
        package_logger.addHandler(file_handler)

    return StructuredLogger(package_logger)
