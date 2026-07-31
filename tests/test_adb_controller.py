"""Unit tests for the ADB transport adapter."""

from __future__ import annotations

import subprocess
from collections.abc import Sequence
from pathlib import Path
from typing import Any

import pytest

from core.adb_controller import (
    ADBCommandError,
    ADBController,
    ADBDeviceError,
    ADBNotFoundError,
    ADBScreenshotError,
    ADBTimeoutError,
)

PNG = b"\x89PNG\r\n\x1a\ncontent"


class FakeRunner:
    """Record subprocess calls and return queued results or exceptions."""

    def __init__(self, *responses: object) -> None:
        self.responses = list(responses)
        self.calls: list[tuple[list[str], dict[str, Any]]] = []

    def __call__(self, command: Sequence[str], **kwargs: Any) -> Any:
        self.calls.append((list(command), kwargs))
        response = self.responses.pop(0)
        if isinstance(response, BaseException):
            raise response
        return response


def result(
    stdout: str | bytes = "",
    *,
    stderr: str | bytes = "",
    returncode: int = 0,
) -> subprocess.CompletedProcess[Any]:
    return subprocess.CompletedProcess([], returncode, stdout, stderr)


def controller(runner: FakeRunner, **kwargs: Any) -> ADBController:
    adb = ADBController(runner=runner, retry_delay=0, **kwargs)
    adb.device = "serial-1"
    return adb


def test_discover_devices_parses_states_and_details() -> None:
    runner = FakeRunner(
        result(
            "List of devices attached\n"
            "serial-1\tdevice product:p model:Pixel_9 transport_id:1\n"
            "serial-2\tunauthorized usb:2-1\n"
        )
    )
    adb = ADBController(runner=runner, retry_delay=0)
    devices = adb.discover_devices()
    assert [(device.serial, device.state) for device in devices] == [
        ("serial-1", "device"),
        ("serial-2", "unauthorized"),
    ]
    assert devices[0].details["model"] == "Pixel_9"
    assert runner.calls[0][0] == ["adb", "devices", "-l"]


def test_connect_selects_first_online_device_and_verifies_it() -> None:
    runner = FakeRunner(
        result("List of devices attached\noffline-1\toffline\nserial-1\tdevice\n"),
        result("device\n"),
    )
    adb = ADBController(runner=runner, retry_delay=0)
    assert adb.connect() is True
    assert adb.device == "serial-1"
    assert runner.calls[1][0] == ["adb", "-s", "serial-1", "get-state"]


@pytest.mark.parametrize("state", ["offline", "unauthorized"])
def test_connect_rejects_explicit_device_that_is_not_ready(state: str) -> None:
    runner = FakeRunner(result(f"List of devices attached\nserial-1\t{state}\n"))
    adb = ADBController(runner=runner, retry_delay=0)
    with pytest.raises(ADBDeviceError, match="not ready"):
        adb.connect("serial-1")


def test_connect_reports_when_no_devices_exist() -> None:
    adb = ADBController(
        runner=FakeRunner(result("List of devices attached\n")), retry_delay=0
    )
    with pytest.raises(ADBDeviceError, match="No online Android device"):
        adb.connect()


def test_connection_failure_clears_selected_device() -> None:
    runner = FakeRunner(
        result("List of devices attached\nserial-1\tdevice\n"), result("offline")
    )
    adb = ADBController(runner=runner, retry_delay=0)
    with pytest.raises(ADBDeviceError, match="not connected"):
        adb.connect()
    assert adb.device is None


def test_screen_resolution_prefers_override_size() -> None:
    runner = FakeRunner(result("Physical size: 1440x3120\nOverride size: 1080x2340\n"))
    adb = controller(runner)
    assert adb.get_screen_resolution() == (1080, 2340)
    assert (adb.width, adb.height) == (1080, 2340)


def test_screen_resolution_rejects_unexpected_output() -> None:
    adb = controller(FakeRunner(result("unknown")))
    with pytest.raises(ADBDeviceError, match="Could not parse"):
        adb.get_screen_resolution()


def test_read_phone_information_populates_all_fields() -> None:
    runner = FakeRunner(
        result("Pixel 9"),
        result("16"),
        result("Physical size: 1080x2400"),
        result("Physical density: 420\nOverride density: 400"),
    )
    adb = controller(runner)
    adb.read_phone_information()
    assert (adb.model, adb.android_version) == ("Pixel 9", "16")
    assert (adb.width, adb.height, adb.density) == (1080, 2400, 400)


def test_screenshot_captures_png_atomically(tmp_path: Path) -> None:
    runner = FakeRunner(result(PNG))
    adb = controller(runner, screenshot_folder=tmp_path)
    path = adb.screenshot()
    assert path == tmp_path / "latest.png"
    assert path.read_bytes() == PNG
    assert not (tmp_path / "latest.png.tmp").exists()
    assert runner.calls[0][0] == [
        "adb", "-s", "serial-1", "exec-out", "screencap", "-p"
    ]
    assert runner.calls[0][1]["text"] is False


def test_screenshot_rejects_invalid_png(tmp_path: Path) -> None:
    adb = controller(FakeRunner(result(b"ADB error")), screenshot_folder=tmp_path)
    with pytest.raises(ADBScreenshotError, match="invalid PNG"):
        adb.screenshot()
    assert not (tmp_path / "latest.png").exists()


@pytest.mark.parametrize(
    ("method", "expected"),
    [
        (lambda adb: adb.tap(10, 20), ["input", "tap", "10", "20"]),
        (
            lambda adb: adb.swipe(1, 2, 3, 4, 250),
            ["input", "swipe", "1", "2", "3", "4", "250"],
        ),
        (lambda adb: adb.back(), ["input", "keyevent", "KEYCODE_BACK"]),
        (lambda adb: adb.home(), ["input", "keyevent", "KEYCODE_HOME"]),
    ],
)
def test_input_commands_are_device_scoped(method: Any, expected: list[str]) -> None:
    runner = FakeRunner(result())
    adb = controller(runner)
    method(adb)
    assert runner.calls[0][0] == ["adb", "-s", "serial-1", "shell", *expected]


def test_shell_uses_quoted_arguments_and_custom_timeout() -> None:
    runner = FakeRunner(result("hello world\n"))
    adb = controller(runner)
    output = adb.shell('echo "hello world"', timeout=3)
    assert output == "hello world"
    assert runner.calls[0][0][-2:] == ["echo", "hello world"]
    assert runner.calls[0][1]["timeout"] == 3


def test_input_validation_prevents_invalid_events() -> None:
    runner = FakeRunner()
    adb = controller(runner)
    with pytest.raises(ValueError, match="non-negative"):
        adb.tap(-1, 2)
    with pytest.raises(ValueError, match="positive"):
        adb.swipe(1, 2, 3, 4, 0)
    assert runner.calls == []


def test_idempotent_command_retries_timeout_with_backoff() -> None:
    timeout = subprocess.TimeoutExpired(["adb", "devices"], 1)
    runner = FakeRunner(timeout, result("List of devices attached\n"))
    sleeps: list[float] = []
    adb = ADBController(
        runner=runner, retries=2, retry_delay=0.5, sleeper=sleeps.append
    )
    assert adb.discover_devices() == ()
    assert len(runner.calls) == 2
    assert sleeps == [0.5]


def test_timeout_raises_typed_error_after_retry_budget() -> None:
    timeout = subprocess.TimeoutExpired(["adb", "devices"], 1)
    runner = FakeRunner(timeout, timeout, timeout)
    adb = ADBController(runner=runner, retries=2, retry_delay=0)
    with pytest.raises(ADBTimeoutError, match="timed out"):
        adb.discover_devices()
    assert len(runner.calls) == 3


def test_transient_command_failure_is_retried() -> None:
    runner = FakeRunner(
        result(stderr="error: device offline", returncode=1), result("device")
    )
    adb = controller(runner, retries=1)
    assert adb.verify_connection() is True
    assert len(runner.calls) == 2


def test_non_transient_failure_is_not_retried() -> None:
    runner = FakeRunner(result(stderr="unknown command", returncode=1))
    adb = controller(runner, retries=2)
    with pytest.raises(ADBCommandError) as raised:
        adb.verify_connection()
    assert raised.value.return_code == 1
    assert len(runner.calls) == 1


def test_missing_adb_executable_raises_typed_error() -> None:
    adb = ADBController(runner=FakeRunner(FileNotFoundError("adb")), retry_delay=0)
    with pytest.raises(ADBNotFoundError, match="not found"):
        adb.discover_devices()


def test_mutating_input_is_not_retried() -> None:
    timeout = subprocess.TimeoutExpired(["adb", "shell", "input"], 1)
    runner = FakeRunner(timeout, result())
    adb = controller(runner, retries=3)
    with pytest.raises(ADBTimeoutError):
        adb.tap(1, 2)
    assert len(runner.calls) == 1


def test_controller_validates_configuration() -> None:
    with pytest.raises(ValueError, match="timeout"):
        ADBController(timeout=0)
    with pytest.raises(ValueError, match="retries"):
        ADBController(retries=-1)
    with pytest.raises(ValueError, match="retry_delay"):
        ADBController(retry_delay=-1)
