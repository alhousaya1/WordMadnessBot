"""Tests for validated, side-effect-free settings."""

from pathlib import Path

import pytest

from word_madness_bot.config.settings import Settings
from word_madness_bot.domain.errors import ConfigurationError


def test_environment_values_are_parsed(tmp_path: Path) -> None:
    """Environment overrides are normalized into typed settings."""

    settings = Settings.from_environment(
        {
            "WORD_MADNESS_PROJECT_ROOT": str(tmp_path),
            "WORD_MADNESS_LOG_LEVEL": "debug",
            "WORD_MADNESS_DEBUG": "yes",
            "WORD_MADNESS_SAVE_SCREENSHOTS": "1",
            "WORD_MADNESS_ADB_COMMAND": "custom-adb",
            "WORD_MADNESS_ADB_TIMEOUT_SECONDS": "2.5",
            "WORD_MADNESS_DEVICE_SERIAL": " serial-1 ",
        }
    )

    assert settings.project_root == tmp_path.resolve()
    assert settings.log_level == "DEBUG"
    assert settings.debug is True
    assert settings.save_screenshots is True
    assert settings.adb_command == "custom-adb"
    assert settings.adb_timeout_seconds == 2.5
    assert settings.device_serial == "serial-1"


@pytest.mark.parametrize("value", ["", "sometimes", "2"])
def test_invalid_boolean_is_rejected(value: str) -> None:
    """Ambiguous boolean settings fail with a configuration error."""

    with pytest.raises(ConfigurationError, match="must be a boolean"):
        Settings.from_environment({"WORD_MADNESS_DEBUG": value})


def test_settings_do_not_create_runtime_directories(tmp_path: Path) -> None:
    """Constructing settings has no filesystem side effects."""

    root = tmp_path / "application"
    settings = Settings(project_root=root)

    assert settings.log_directory == root.resolve() / "logs"
    assert not root.exists()
