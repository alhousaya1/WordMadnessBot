"""Tests for immutable runtime settings."""

from pathlib import Path

import pytest

from word_madness_bot.config.settings import Settings
from word_madness_bot.domain.errors import ConfigurationError


def test_settings_have_safe_defaults() -> None:
    settings = Settings.from_environment({})

    assert settings.adb_executable == "adb"
    assert settings.adb_timeout_seconds == 15.0
    assert settings.adb_retries == 2
    assert settings.swipe_segment_duration_seconds == 0.150
    assert settings.inter_word_safety_delay_seconds == 0.0
    assert settings.log_level == "INFO"
    assert settings.data_directory == Path("data")


def test_settings_load_environment_overrides() -> None:
    settings = Settings.from_environment(
        {
            "WMB_ADB_EXECUTABLE": "platform-tools/adb",
            "WMB_ADB_TIMEOUT_SECONDS": "4.5",
            "WMB_ADB_RETRIES": "5",
            "WMB_SWIPE_SEGMENT_DURATION_SECONDS": "0.175",
            "WMB_INTER_WORD_SAFETY_DELAY_SECONDS": "0.075",
            "WMB_LOG_LEVEL": "debug",
            "WMB_DATA_DIRECTORY": "resources/levels",
            "WMB_LOG_DIRECTORY": "var/log",
            "WMB_SCREENSHOT_DIRECTORY": "var/screens",
            "WMB_TEMPLATE_DIRECTORY": "resources/templates",
            "WMB_DEBUG_DIRECTORY": "var/debug",
        }
    )

    assert settings.adb_executable == "platform-tools/adb"
    assert settings.adb_timeout_seconds == 4.5
    assert settings.adb_retries == 5
    assert settings.swipe_segment_duration_seconds == 0.175
    assert settings.inter_word_safety_delay_seconds == 0.075
    assert settings.log_level == "DEBUG"
    assert settings.template_directory == Path("resources/templates")
    assert settings.debug_directory == Path("var/debug")


@pytest.mark.parametrize(
    ("environment", "message"),
    [
        ({"WMB_ADB_TIMEOUT_SECONDS": "zero"}, "must be a number"),
        ({"WMB_ADB_TIMEOUT_SECONDS": "0"}, "greater than zero"),
        ({"WMB_ADB_RETRIES": "many"}, "must be an integer"),
        ({"WMB_ADB_RETRIES": "-1"}, "cannot be negative"),
        ({"WMB_SWIPE_SEGMENT_DURATION_SECONDS": "fast"}, "must be a number"),
        ({"WMB_SWIPE_SEGMENT_DURATION_SECONDS": "0"}, "greater than zero"),
        ({"WMB_INTER_WORD_SAFETY_DELAY_SECONDS": "0.101"}, "between zero"),
        ({"WMB_LOG_LEVEL": "verbose"}, "Unsupported log level"),
        ({"WMB_ADB_EXECUTABLE": "  "}, "cannot be empty"),
    ],
)
def test_settings_reject_invalid_values(
    environment: dict[str, str],
    message: str,
) -> None:
    with pytest.raises(ConfigurationError, match=message):
        Settings.from_environment(environment)
