"""Explicit, idempotent logging configuration for all application layers."""

import json
import logging
from datetime import UTC, datetime
from pathlib import Path

_LOG_FORMAT = "[%(asctime)s] %(levelname)s %(name)s: %(message)s"
_DATE_FORMAT = "%Y-%m-%dT%H:%M:%S%z"


class JsonFormatter(logging.Formatter):
    """Format standard and structured logging fields as one JSON object per line."""

    _standard_fields = frozenset(logging.makeLogRecord({}).__dict__) | {"message", "asctime"}

    def format(self, record: logging.LogRecord) -> str:
        """Return deterministic JSON while preserving exception diagnostics."""

        payload: dict[str, object] = {
            "timestamp": datetime.now(UTC).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }
        payload.update(
            sorted(
                (key, value)
                for key, value in record.__dict__.items()
                if key not in self._standard_fields and key not in {"msg", "args"}
            )
        )
        if record.exc_info:
            payload["exception"] = self.formatException(record.exc_info)
        return json.dumps(payload, default=str, sort_keys=True)


def configure_logging(
    *,
    level: str = "INFO",
    log_file: Path | None = None,
    structured: bool = False,
) -> logging.Logger:
    """Configure and return the application logger.

    Calling this function repeatedly replaces only handlers owned by the application
    logger. Parent/root logging configuration is left untouched for embedding hosts.
    Directories are created only when the caller explicitly requests a log file.
    """

    logger = logging.getLogger("word_madness_bot")
    logger.setLevel(level.upper())
    logger.propagate = False

    for handler in tuple(logger.handlers):
        handler.close()
        logger.removeHandler(handler)

    formatter: logging.Formatter = (
        JsonFormatter() if structured else logging.Formatter(_LOG_FORMAT, _DATE_FORMAT)
    )
    console_handler = logging.StreamHandler()
    console_handler.setFormatter(formatter)
    logger.addHandler(console_handler)

    if log_file is not None:
        resolved_file = log_file.expanduser().resolve()
        resolved_file.parent.mkdir(parents=True, exist_ok=True)
        file_handler = logging.FileHandler(resolved_file, encoding="utf-8")
        file_handler.setFormatter(formatter)
        logger.addHandler(file_handler)

    return logger
