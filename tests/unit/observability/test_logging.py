"""Tests for explicit application logging configuration."""

import logging
from pathlib import Path

from word_madness_bot.observability.logging import configure_logging


def test_configure_logging_is_idempotent() -> None:
    """Repeated configuration does not accumulate duplicate handlers."""

    logger = configure_logging(level="INFO")
    logger = configure_logging(level="DEBUG")

    assert logger.level == logging.DEBUG
    assert len(logger.handlers) == 1


def test_file_logging_is_created_only_when_requested(tmp_path: Path) -> None:
    """An explicit log path creates its parent and receives messages."""

    log_file = tmp_path / "nested" / "bot.log"
    logger = configure_logging(log_file=log_file)
    logger.info("foundation ready")
    for handler in logger.handlers:
        handler.flush()

    assert log_file.read_text(encoding="utf-8").endswith("foundation ready\n")
