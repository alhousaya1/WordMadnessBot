"""Unit tests for the subprocess-backed ADB client."""

from __future__ import annotations

import io
import struct
import subprocess
from collections.abc import Callable
from typing import Any, cast

import pytest

from word_madness_bot.config.logging import configure_logging
from word_madness_bot.config.settings import Settings
from word_madness_bot.domain.errors import (
    AdbCommandError,
    AdbExecutableNotFoundError,
    AdbTimeoutError,
    DeviceConnectionError,
    DeviceSelectionError,
    ScreenshotError,
)
from word_madness_bot.domain.geometry import PixelPoint
from word_madness_bot.domain.models import DeviceState, SwipePath
from word_madness_bot.infrastructure.adb.client import (
    AdbClient,
    _parse_density,
    _parse_devices,
    _parse_size,
)


def result(stdout: str | bytes = "", stderr: str | bytes = "", code: int = 0) -> Any:
    return cast(Any, subprocess.CompletedProcess([], code, stdout, stderr))


def client(runner: Callable[..., Any], *, retries: int = 0) -> AdbClient:
    return AdbClient(
        Settings(adb_retries=retries),
        configure_logging(stream=io.StringIO()),
        runner=runner,
        sleeper=lambda _: None,
    )


@pytest.mark.parametrize(
    ("output", "states"),
    [
        ("List of devices attached\n", ()),
        ("List of devices attached\na\tdevice product:x model:y\n", (DeviceState.ONLINE,)),
        (
            "List of devices attached\na offline\nb unauthorized\nc mystery\n",
            (DeviceState.OFFLINE, DeviceState.UNAUTHORIZED, DeviceState.UNKNOWN),
        ),
        ("List of devices attached\nmalformed\n", ()),
    ],
)
def test_device_parsing(output: str, states: tuple[DeviceState, ...]) -> None:
    assert tuple(device.state for device in _parse_devices(output)) == states


def test_explicit_and_automatic_selection() -> None:
    def runner(*args: object, **kwargs: object) -> Any:
        return result("List of devices attached\na device\n")

    adapter = client(runner)
    assert adapter.select_device().serial == "a"
    assert adapter.select_device("a").serial == "a"


def test_automatic_selection_rejects_zero_or_multiple_devices() -> None:
    for output in ("List of devices attached\n", "List of devices attached\na device\nb device\n"):
        with pytest.raises(DeviceSelectionError):
            client(lambda *args, **kwargs: result(output)).select_device()  # noqa: B023


def test_offline_explicit_device_is_rejected() -> None:
    with pytest.raises(DeviceConnectionError):
        client(
            lambda *args, **kwargs: result("List of devices attached\na offline\n")
        ).select_device("a")


def test_connection_and_shell_use_selected_serial() -> None:
    calls: list[list[str]] = []

    def runner(command: list[str], **kwargs: object) -> Any:
        calls.append(command)
        return result(
            "List of devices attached\na device\n" if "devices" in command else "device\n"
        )

    adapter = client(runner)
    adapter.select_device()
    assert adapter.verify_connection()
    assert calls[-1] == ["adb", "-s", "a", "get-state"]


def test_display_physical_and_override_values() -> None:
    assert _parse_size("Physical size: 1080x2400\nOverride size: 720x1600").width == 720
    assert _parse_density("Physical density: 420\nOverride density: 320") == 320


@pytest.mark.parametrize("parser", [_parse_size, _parse_density])
def test_malformed_display_value_is_rejected(parser: Callable[[str], object]) -> None:
    with pytest.raises(AdbCommandError):
        parser("garbage")


def test_screenshot_capture_returns_binary_png() -> None:
    png = b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR" + struct.pack(">II", 3, 4)
    calls = 0

    def runner(*args: object, **kwargs: object) -> Any:
        nonlocal calls
        calls += 1
        return result("List of devices attached\na device\n") if calls == 1 else result(png, b"")

    adapter = client(runner)
    adapter.select_device()
    assert adapter.capture_screenshot().size.height == 4


def test_empty_or_corrupt_screenshot_is_rejected() -> None:
    responses = iter([result("List of devices attached\na device\n"), result(b"", b"")])
    adapter = client(lambda *args, **kwargs: next(responses))
    adapter.select_device()
    with pytest.raises(ScreenshotError):
        adapter.capture_screenshot()


def test_input_commands_are_constructed_and_never_retried() -> None:
    calls: list[list[str]] = []

    def runner(command: list[str], **kwargs: object) -> Any:
        calls.append(command)
        if "devices" in command:
            return result("List of devices attached\na device\n")
        return result("", "failure", 1)

    adapter = client(runner, retries=3)
    adapter.select_device()
    actions = [
        lambda: adapter.tap(PixelPoint(1, 2)),
        lambda: adapter.swipe(SwipePath((PixelPoint(1, 2), PixelPoint(3, 4)), 500)),
        adapter.press_back,
        adapter.press_home,
    ]
    for action in actions:
        before = len(calls)
        with pytest.raises(AdbCommandError):
            action()
        assert len(calls) == before + 1
    assert calls[1][-5:] == ["shell", "input", "tap", "1", "2"]


def test_safe_command_retries_then_succeeds() -> None:
    calls = 0

    def runner(*args: object, **kwargs: object) -> Any:
        nonlocal calls
        calls += 1
        return result("", "failure", 1) if calls == 1 else result("List of devices attached\n")

    assert client(runner, retries=1).discover_devices() == ()
    assert calls == 2


def test_timeout_exhaustion_is_typed() -> None:
    def runner(command: list[str], **kwargs: object) -> object:
        raise subprocess.TimeoutExpired(command, 1.0)

    with pytest.raises(AdbTimeoutError):
        client(runner, retries=1).discover_devices()


def test_missing_executable_is_typed_without_retry() -> None:
    calls = 0

    def runner(*args: object, **kwargs: object) -> object:
        nonlocal calls
        calls += 1
        raise FileNotFoundError

    with pytest.raises(AdbExecutableNotFoundError):
        client(runner, retries=3).discover_devices()
    assert calls == 1

def test_swipe_emits_one_continuous_multi_point_motion_gesture() -> None:
    calls: list[list[str]] = []

    def runner(command: list[str], **kwargs: object) -> Any:
        calls.append(command)
        if "devices" in command:
            return result("List of devices attached\na device\n")
        return result()

    adapter = client(runner)
    adapter.select_device()
    receipt = adapter.swipe(
        SwipePath(
            (PixelPoint(10, 20), PixelPoint(30, 40), PixelPoint(50, 60)),
            180,
        )
    )
    assert len(calls) == 2
    assert calls[1][-4:-1] == ["shell", "sh", "-c"]
    assert calls[1][-1] == (
        "input motionevent DOWN 10 20; sleep 0.090; "
        "input motionevent MOVE 30 40; sleep 0.090; "
        "input motionevent UP 50 60"
    )
    assert receipt.backend_command == tuple(calls[1][-4:])
    assert receipt.timestamps_ms == (0, 90, 180)