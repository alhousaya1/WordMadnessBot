"""Side-effect-free runtime settings loaded from environment variables."""

import logging
import os
import sys
from collections.abc import Mapping
from dataclasses import dataclass, field
from pathlib import Path

from word_madness_bot.domain.errors import ConfigurationError

_PREFIX = "WORD_MADNESS_"
_TRUE_VALUES = frozenset({"1", "true", "yes", "on"})
_FALSE_VALUES = frozenset({"0", "false", "no", "off"})


def _default_project_root() -> Path:
    source_root = Path(__file__).resolve().parents[3]
    if (source_root / "pyproject.toml").is_file():
        return source_root
    return Path(sys.prefix).resolve()


def _parse_bool(name: str, value: str) -> bool:
    normalized = value.strip().lower()
    if normalized in _TRUE_VALUES:
        return True
    if normalized in _FALSE_VALUES:
        return False
    raise ConfigurationError(f"{name} must be a boolean value")


def _parse_positive_float(name: str, value: str) -> float:
    try:
        parsed = float(value)
    except ValueError as error:
        raise ConfigurationError(f"{name} must be a number") from error
    if parsed <= 0:
        raise ConfigurationError(f"{name} must be greater than zero")
    return parsed


def _parse_positive_int(name: str, value: str) -> int:
    try:
        parsed = int(value)
    except ValueError as error:
        raise ConfigurationError(f"{name} must be an integer") from error
    if parsed <= 0:
        raise ConfigurationError(f"{name} must be greater than zero")
    return parsed


def _parse_nonnegative_int(name: str, value: str) -> int:
    try:
        parsed = int(value)
    except ValueError as error:
        raise ConfigurationError(f"{name} must be an integer") from error
    if parsed < 0:
        raise ConfigurationError(f"{name} cannot be negative")
    return parsed


def _parse_probability(name: str, value: str) -> float:
    try:
        parsed = float(value)
    except ValueError as error:
        raise ConfigurationError(f"{name} must be a number") from error
    if not 0.0 <= parsed <= 1.0:
        raise ConfigurationError(f"{name} must be between zero and one")
    return parsed


def _parse_nonnegative_float(name: str, value: str) -> float:
    try:
        parsed = float(value)
    except ValueError as error:
        raise ConfigurationError(f"{name} must be a number") from error
    if parsed < 0.0:
        raise ConfigurationError(f"{name} cannot be negative")
    return parsed


@dataclass(frozen=True, slots=True)
class Settings:
    """Validated application settings with no import-time filesystem effects."""

    project_root: Path = field(default_factory=_default_project_root)
    log_level: str = "INFO"
    debug: bool = False
    save_screenshots: bool = False
    save_debug_images: bool = False
    adb_command: str = "adb"
    adb_timeout_seconds: float = 15.0
    device_serial: str | None = None
    state_minimum_confidence: float = 0.65
    state_conflict_margin: float = 0.10
    state_stable_frames: int = 2
    swipe_interpolation_points: int = 4
    swipe_smoothing_strength: float = 0.5
    swipe_duration_per_letter_ms: int = 120
    swipe_maximum_step_fraction: float = 0.25
    ad_initial_wait_seconds: float = 3.0
    ad_retry_delay_seconds: float = 1.0
    ad_timeout_seconds: float = 30.0
    ad_max_attempts: int = 4
    ad_minimum_confidence: float = 0.75
    ad_allow_back_fallback: bool = True
    ad_back_key_code: int = 4
    decision_max_retries: int = 3
    decision_retry_delay_seconds: float = 1.0
    word_max_attempts: int = 2
    run_interval_seconds: float = 1.0
    metrics_enabled: bool = True
    diagnostics_enabled: bool = False
    diagnostic_artifacts_enabled: bool = False
    artifact_maximum_files: int = 100
    artifact_maximum_bytes: int = 100_000_000
    health_stale_after_seconds: float = 30.0

    def __post_init__(self) -> None:
        root = self.project_root.expanduser().resolve()
        object.__setattr__(self, "project_root", root)
        normalized_level = self.log_level.strip().upper()
        if normalized_level not in logging.getLevelNamesMapping():
            raise ConfigurationError(f"unsupported log level: {self.log_level!r}")
        object.__setattr__(self, "log_level", normalized_level)
        if not self.adb_command.strip():
            raise ConfigurationError("adb_command cannot be empty")
        if self.adb_timeout_seconds <= 0:
            raise ConfigurationError("adb_timeout_seconds must be greater than zero")
        if not 0.0 <= self.state_minimum_confidence <= 1.0:
            raise ConfigurationError("state_minimum_confidence must be between zero and one")
        if not 0.0 <= self.state_conflict_margin <= 1.0:
            raise ConfigurationError("state_conflict_margin must be between zero and one")
        if self.state_stable_frames <= 0:
            raise ConfigurationError("state_stable_frames must be greater than zero")
        if self.swipe_interpolation_points < 0:
            raise ConfigurationError("swipe_interpolation_points cannot be negative")
        if not 0.0 <= self.swipe_smoothing_strength <= 1.0:
            raise ConfigurationError("swipe_smoothing_strength must be between zero and one")
        if self.swipe_duration_per_letter_ms <= 0:
            raise ConfigurationError("swipe_duration_per_letter_ms must be greater than zero")
        if not 0.0 < self.swipe_maximum_step_fraction <= 1.0:
            raise ConfigurationError(
                "swipe_maximum_step_fraction must be above zero and at most one"
            )
        if self.ad_initial_wait_seconds < 0.0:
            raise ConfigurationError("ad_initial_wait_seconds cannot be negative")
        if self.ad_retry_delay_seconds <= 0.0:
            raise ConfigurationError("ad_retry_delay_seconds must be greater than zero")
        if self.ad_timeout_seconds <= 0.0:
            raise ConfigurationError("ad_timeout_seconds must be greater than zero")
        if self.ad_max_attempts <= 0:
            raise ConfigurationError("ad_max_attempts must be greater than zero")
        if not 0.0 <= self.ad_minimum_confidence <= 1.0:
            raise ConfigurationError("ad_minimum_confidence must be between zero and one")
        if self.ad_back_key_code < 0:
            raise ConfigurationError("ad_back_key_code cannot be negative")
        if self.decision_max_retries <= 0:
            raise ConfigurationError("decision_max_retries must be greater than zero")
        if self.decision_retry_delay_seconds <= 0.0:
            raise ConfigurationError("decision_retry_delay_seconds must be greater than zero")
        if self.word_max_attempts <= 0:
            raise ConfigurationError("word_max_attempts must be greater than zero")
        if self.run_interval_seconds <= 0.0:
            raise ConfigurationError("run_interval_seconds must be greater than zero")
        if self.artifact_maximum_files <= 0 or self.artifact_maximum_bytes <= 0:
            raise ConfigurationError("artifact retention limits must be greater than zero")
        if self.health_stale_after_seconds <= 0.0:
            raise ConfigurationError("health_stale_after_seconds must be greater than zero")
        serial = self.device_serial.strip() if self.device_serial else None
        object.__setattr__(self, "device_serial", serial or None)

    @property
    def database_directory(self) -> Path:
        """Return the configured database directory without creating it."""

        return self.project_root / "database"

    @property
    def level_database_file(self) -> Path:
        """Return the configured JSON level database path."""

        return self.database_directory / "levels.json"

    @property
    def debug_directory(self) -> Path:
        """Return the configured debug-artifact directory without creating it."""

        return self.project_root / "debug"

    @property
    def log_directory(self) -> Path:
        """Return the configured log directory without creating it."""

        return self.project_root / "logs"

    @property
    def screenshot_directory(self) -> Path:
        """Return the configured screenshot directory without creating it."""

        return self.project_root / "screenshots"

    @property
    def template_directory(self) -> Path:
        """Return the configured template directory without creating it."""

        return self.project_root / "templates"

    @property
    def diagnostics_directory(self) -> Path:
        """Return the configured diagnostics report directory without creating it."""

        return self.project_root / "diagnostics"

    @classmethod
    def from_environment(cls, environ: Mapping[str, str] | None = None) -> "Settings":
        """Build settings from a supplied mapping or the process environment."""

        values = os.environ if environ is None else environ
        root_value = values.get(f"{_PREFIX}PROJECT_ROOT")
        return cls(
            project_root=Path(root_value) if root_value else _default_project_root(),
            log_level=values.get(f"{_PREFIX}LOG_LEVEL", "INFO"),
            debug=_parse_bool(f"{_PREFIX}DEBUG", values.get(f"{_PREFIX}DEBUG", "false")),
            save_screenshots=_parse_bool(
                f"{_PREFIX}SAVE_SCREENSHOTS",
                values.get(f"{_PREFIX}SAVE_SCREENSHOTS", "false"),
            ),
            save_debug_images=_parse_bool(
                f"{_PREFIX}SAVE_DEBUG_IMAGES",
                values.get(f"{_PREFIX}SAVE_DEBUG_IMAGES", "false"),
            ),
            adb_command=values.get(f"{_PREFIX}ADB_COMMAND", "adb"),
            adb_timeout_seconds=_parse_positive_float(
                f"{_PREFIX}ADB_TIMEOUT_SECONDS",
                values.get(f"{_PREFIX}ADB_TIMEOUT_SECONDS", "15"),
            ),
            device_serial=values.get(f"{_PREFIX}DEVICE_SERIAL") or None,
            state_minimum_confidence=_parse_probability(
                f"{_PREFIX}STATE_MINIMUM_CONFIDENCE",
                values.get(f"{_PREFIX}STATE_MINIMUM_CONFIDENCE", "0.65"),
            ),
            state_conflict_margin=_parse_probability(
                f"{_PREFIX}STATE_CONFLICT_MARGIN",
                values.get(f"{_PREFIX}STATE_CONFLICT_MARGIN", "0.10"),
            ),
            state_stable_frames=_parse_positive_int(
                f"{_PREFIX}STATE_STABLE_FRAMES",
                values.get(f"{_PREFIX}STATE_STABLE_FRAMES", "2"),
            ),
            swipe_interpolation_points=_parse_nonnegative_int(
                f"{_PREFIX}SWIPE_INTERPOLATION_POINTS",
                values.get(f"{_PREFIX}SWIPE_INTERPOLATION_POINTS", "4"),
            ),
            swipe_smoothing_strength=_parse_probability(
                f"{_PREFIX}SWIPE_SMOOTHING_STRENGTH",
                values.get(f"{_PREFIX}SWIPE_SMOOTHING_STRENGTH", "0.5"),
            ),
            swipe_duration_per_letter_ms=_parse_positive_int(
                f"{_PREFIX}SWIPE_DURATION_PER_LETTER_MS",
                values.get(f"{_PREFIX}SWIPE_DURATION_PER_LETTER_MS", "120"),
            ),
            swipe_maximum_step_fraction=_parse_probability(
                f"{_PREFIX}SWIPE_MAXIMUM_STEP_FRACTION",
                values.get(f"{_PREFIX}SWIPE_MAXIMUM_STEP_FRACTION", "0.25"),
            ),
            ad_initial_wait_seconds=_parse_nonnegative_float(
                f"{_PREFIX}AD_INITIAL_WAIT_SECONDS",
                values.get(f"{_PREFIX}AD_INITIAL_WAIT_SECONDS", "3.0"),
            ),
            ad_retry_delay_seconds=_parse_positive_float(
                f"{_PREFIX}AD_RETRY_DELAY_SECONDS",
                values.get(f"{_PREFIX}AD_RETRY_DELAY_SECONDS", "1.0"),
            ),
            ad_timeout_seconds=_parse_positive_float(
                f"{_PREFIX}AD_TIMEOUT_SECONDS",
                values.get(f"{_PREFIX}AD_TIMEOUT_SECONDS", "30.0"),
            ),
            ad_max_attempts=_parse_positive_int(
                f"{_PREFIX}AD_MAX_ATTEMPTS",
                values.get(f"{_PREFIX}AD_MAX_ATTEMPTS", "4"),
            ),
            ad_minimum_confidence=_parse_probability(
                f"{_PREFIX}AD_MINIMUM_CONFIDENCE",
                values.get(f"{_PREFIX}AD_MINIMUM_CONFIDENCE", "0.75"),
            ),
            ad_allow_back_fallback=_parse_bool(
                f"{_PREFIX}AD_ALLOW_BACK_FALLBACK",
                values.get(f"{_PREFIX}AD_ALLOW_BACK_FALLBACK", "true"),
            ),
            ad_back_key_code=_parse_nonnegative_int(
                f"{_PREFIX}AD_BACK_KEY_CODE",
                values.get(f"{_PREFIX}AD_BACK_KEY_CODE", "4"),
            ),
            decision_max_retries=_parse_positive_int(
                f"{_PREFIX}DECISION_MAX_RETRIES",
                values.get(f"{_PREFIX}DECISION_MAX_RETRIES", "3"),
            ),
            decision_retry_delay_seconds=_parse_positive_float(
                f"{_PREFIX}DECISION_RETRY_DELAY_SECONDS",
                values.get(f"{_PREFIX}DECISION_RETRY_DELAY_SECONDS", "1.0"),
            ),
            word_max_attempts=_parse_positive_int(
                f"{_PREFIX}WORD_MAX_ATTEMPTS",
                values.get(f"{_PREFIX}WORD_MAX_ATTEMPTS", "2"),
            ),
            run_interval_seconds=_parse_positive_float(
                f"{_PREFIX}RUN_INTERVAL_SECONDS",
                values.get(f"{_PREFIX}RUN_INTERVAL_SECONDS", "1.0"),
            ),
            metrics_enabled=_parse_bool(
                f"{_PREFIX}METRICS_ENABLED",
                values.get(f"{_PREFIX}METRICS_ENABLED", "true"),
            ),
            diagnostics_enabled=_parse_bool(
                f"{_PREFIX}DIAGNOSTICS_ENABLED",
                values.get(f"{_PREFIX}DIAGNOSTICS_ENABLED", "false"),
            ),
            diagnostic_artifacts_enabled=_parse_bool(
                f"{_PREFIX}DIAGNOSTIC_ARTIFACTS_ENABLED",
                values.get(f"{_PREFIX}DIAGNOSTIC_ARTIFACTS_ENABLED", "false"),
            ),
            artifact_maximum_files=_parse_positive_int(
                f"{_PREFIX}ARTIFACT_MAXIMUM_FILES",
                values.get(f"{_PREFIX}ARTIFACT_MAXIMUM_FILES", "100"),
            ),
            artifact_maximum_bytes=_parse_positive_int(
                f"{_PREFIX}ARTIFACT_MAXIMUM_BYTES",
                values.get(f"{_PREFIX}ARTIFACT_MAXIMUM_BYTES", "100000000"),
            ),
            health_stale_after_seconds=_parse_positive_float(
                f"{_PREFIX}HEALTH_STALE_AFTER_SECONDS",
                values.get(f"{_PREFIX}HEALTH_STALE_AFTER_SECONDS", "30.0"),
            ),
        )
