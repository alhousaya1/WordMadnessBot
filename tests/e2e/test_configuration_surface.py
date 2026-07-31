"""Release checks for the documented environment configuration surface."""

from pathlib import Path

from word_madness_bot.config import Settings


def test_every_example_environment_option_is_accepted() -> None:
    example = Path(__file__).resolve().parents[2] / ".env.example"
    environment: dict[str, str] = {}
    for line in example.read_text(encoding="utf-8").splitlines():
        if line.startswith("WORD_MADNESS_"):
            key, value = line.split("=", maxsplit=1)
            environment[key] = value
    settings = Settings.from_environment(environment)
    assert settings.log_level == "INFO"
    assert settings.adb_timeout_seconds == 15.0
    assert settings.metrics_enabled is True
    assert settings.diagnostics_enabled is False
