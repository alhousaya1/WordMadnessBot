"""Unit tests for CLI dispatch and exit codes."""

import pytest

from word_madness_bot.cli import build_parser, run_cli


class FakeApplication:
    def __init__(self) -> None:
        self.calls: list[str] = []

    def validate_configuration(self) -> None:
        self.calls.append("config")

    def validate_database(self) -> int:
        self.calls.append("database")
        return 1

    def check_device(self) -> str:
        self.calls.append("device")
        return "serial"

    def capture_diagnostic(self) -> str:
        self.calls.append("capture")
        return "diagnostic.png"

    def observe_once(self) -> object:
        self.calls.append("observe")
        raise RuntimeError("test observation failure")

    def run_continuous(self) -> int:
        self.calls.append("run")
        return 0

    def request_shutdown(self) -> None:
        self.calls.append("shutdown")


@pytest.mark.parametrize(
    ("arguments", "expected"),
    [
        (["validate-config"], "config"),
        (["validate-database"], "database"),
        (["check-device"], "device"),
        (["capture-screenshot"], "capture"),
    ],
)
def test_cli_dispatches_lifecycle_only(arguments: list[str], expected: str) -> None:
    app = FakeApplication()
    assert run_cli(arguments, app) == 0  # type: ignore[arg-type]
    assert app.calls == [expected]


def test_cli_returns_nonzero_on_application_error() -> None:
    app = FakeApplication()
    assert run_cli(["observe", "--dry-run"], app) == 1  # type: ignore[arg-type]
    assert app.calls == ["observe"]


def test_observe_requires_explicit_dry_run_flag() -> None:
    with pytest.raises(SystemExit):
        build_parser().parse_args(["observe"])
