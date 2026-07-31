from __future__ import annotations

import io

import pytest

from word_madness_bot.cli import create_parser, main
from word_madness_bot.config.settings import Settings


class FakeRuntime:
    def __init__(self, *, interrupt: bool = False) -> None:
        self.interrupt = interrupt
        self.started_with: bool | None = None
        self.shutdowns = 0

    def start(self, *, dry_run: bool = False) -> None:
        self.started_with = dry_run
        if self.interrupt:
            raise KeyboardInterrupt

    def shutdown(self) -> None:
        self.shutdowns += 1


def test_parser_help_and_version(capsys: pytest.CaptureFixture[str]) -> None:
    with pytest.raises(SystemExit) as help_exit:
        create_parser().parse_args(["--help"])
    assert help_exit.value.code == 0
    assert "--dry-run" in capsys.readouterr().out
    with pytest.raises(SystemExit) as version_exit:
        create_parser().parse_args(["--version"])
    assert version_exit.value.code == 0


def test_cli_dry_run_loads_settings_and_shuts_down() -> None:
    runtime = FakeRuntime()
    received: list[Settings] = []

    def build(settings: Settings) -> FakeRuntime:
        received.append(settings)
        return runtime

    assert main(["--dry-run"], environ={"WMB_LOG_LEVEL": "debug"}, runtime_builder=build) == 0
    assert received[0].log_level == "DEBUG"
    assert runtime.started_with is True
    assert runtime.shutdowns == 1


def test_cli_reports_invalid_configuration_without_building() -> None:
    errors = io.StringIO()
    built = False

    def build(settings: Settings) -> FakeRuntime:
        nonlocal built
        built = True
        return FakeRuntime()

    assert main([], environ={"WMB_ADB_RETRIES": "bad"}, runtime_builder=build, stderr=errors) == 2
    assert not built
    assert "configuration error" in errors.getvalue()


def test_cli_gracefully_handles_keyboard_interrupt() -> None:
    runtime = FakeRuntime(interrupt=True)
    result = main([], environ={}, runtime_builder=lambda settings: runtime, stderr=io.StringIO())
    assert result == 130
    assert runtime.shutdowns == 1
