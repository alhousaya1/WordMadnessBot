"""Immutable runtime settings with explicit environment loading."""

from __future__ import annotations

import os
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import ClassVar

from word_madness_bot.domain.errors import ConfigurationError


@dataclass(frozen=True, slots=True)
class Settings:
    """Validated settings shared through explicit dependency injection."""

    ENV_PREFIX: ClassVar[str] = "WMB_"

    adb_executable: str = "adb"
    adb_timeout_seconds: float = 15.0
    adb_retries: int = 2
    log_level: str = "INFO"
    data_directory: Path = Path("data")
    log_directory: Path = Path("logs")
    screenshot_directory: Path = Path("screenshots")
    template_directory: Path = Path("templates")
    debug_directory: Path = Path("debug")

    def __post_init__(self) -> None:
        if not self.adb_executable.strip():
            raise ConfigurationError("adb_executable cannot be empty")
        if self.adb_timeout_seconds <= 0:
            raise ConfigurationError("adb_timeout_seconds must be greater than zero")
        if self.adb_retries < 0:
            raise ConfigurationError("adb_retries cannot be negative")
        normalized_level = self.log_level.upper()
        if normalized_level not in {"CRITICAL", "ERROR", "WARNING", "INFO", "DEBUG"}:
            raise ConfigurationError(f"Unsupported log level: {self.log_level!r}")
        object.__setattr__(self, "log_level", normalized_level)

    @classmethod
    def from_environment(cls, environ: Mapping[str, str] | None = None) -> Settings:
        """Create settings from a mapping without mutating process state."""
        values = os.environ if environ is None else environ
        return cls(
            adb_executable=values.get(f"{cls.ENV_PREFIX}ADB_EXECUTABLE", "adb"),
            adb_timeout_seconds=_positive_float(
                values.get(f"{cls.ENV_PREFIX}ADB_TIMEOUT_SECONDS", "15"),
                "ADB_TIMEOUT_SECONDS",
            ),
            adb_retries=_non_negative_int(
                values.get(f"{cls.ENV_PREFIX}ADB_RETRIES", "2"),
                "ADB_RETRIES",
            ),
            log_level=values.get(f"{cls.ENV_PREFIX}LOG_LEVEL", "INFO"),
            data_directory=Path(values.get(f"{cls.ENV_PREFIX}DATA_DIRECTORY", "data")),
            log_directory=Path(values.get(f"{cls.ENV_PREFIX}LOG_DIRECTORY", "logs")),
            screenshot_directory=Path(
                values.get(f"{cls.ENV_PREFIX}SCREENSHOT_DIRECTORY", "screenshots")
            ),
            template_directory=Path(
                values.get(f"{cls.ENV_PREFIX}TEMPLATE_DIRECTORY", "templates")
            ),
            debug_directory=Path(values.get(f"{cls.ENV_PREFIX}DEBUG_DIRECTORY", "debug")),
        )


def _positive_float(value: str, name: str) -> float:
    try:
        parsed = float(value)
    except ValueError as error:
        raise ConfigurationError(f"{name} must be a number") from error
    if parsed <= 0:
        raise ConfigurationError(f"{name} must be greater than zero")
    return parsed


def _non_negative_int(value: str, name: str) -> int:
    try:
        parsed = int(value)
    except ValueError as error:
        raise ConfigurationError(f"{name} must be an integer") from error
    if parsed < 0:
        raise ConfigurationError(f"{name} cannot be negative")
    return parsed
