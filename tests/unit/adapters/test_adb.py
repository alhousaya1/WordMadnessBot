"""Unit tests for serialized ADB command and input execution."""

import subprocess
from unittest.mock import patch

import pytest

from word_madness_bot.adapters.adb import AdbCommandExecutor, AdbInputExecutor
from word_madness_bot.domain.errors import DeviceError, InputExecutionError
from word_madness_bot.domain.models import (
    DeviceInfo,
    NormalizedPoint,
    Point,
    ScreenGeometry,
    SwipePath,
)


class RecordingCommands:
    def __init__(self) -> None:
        self.calls: list[tuple[tuple[str, ...], str | None]] = []

    def execute(self, arguments: tuple[str, ...], *, serial: str | None = None) -> bytes:
        self.calls.append((arguments, serial))
        return b""


class Device:
    def get_device_info(self, serial: str) -> DeviceInfo:
        return DeviceInfo(serial, "model", "14", ScreenGeometry(100, 200, 320))


def test_command_executor_builds_serial_scoped_process() -> None:
    completed = subprocess.CompletedProcess([], 0, stdout=b"ok", stderr=b"")
    with patch("word_madness_bot.adapters.adb.subprocess.run", return_value=completed) as run:
        output = AdbCommandExecutor("adb-custom", 4.0).execute(
            ("shell", "echo", "ok"), serial="serial-1"
        )
    assert output == b"ok"
    assert run.call_args.args[0] == [
        "adb-custom",
        "-s",
        "serial-1",
        "shell",
        "echo",
        "ok",
    ]


def test_command_executor_reports_stderr() -> None:
    completed = subprocess.CompletedProcess([], 1, stdout=b"", stderr=b"offline")
    with (
        patch("word_madness_bot.adapters.adb.subprocess.run", return_value=completed),
        pytest.raises(DeviceError, match="offline"),
    ):
        AdbCommandExecutor().execute(("devices",))


def test_input_executor_runs_tap_back_and_complete_swipe_path() -> None:
    commands = RecordingCommands()
    inputs = AdbInputExecutor(commands, Device())  # type: ignore[arg-type]
    inputs.tap("serial-1", Point(50, 100))
    inputs.key_event("serial-1", 4)
    inputs.swipe(
        "serial-1",
        SwipePath(
            (NormalizedPoint(0.1, 0.2), NormalizedPoint(0.5, 0.5), NormalizedPoint(0.9, 0.8)),
            1,
        ),
    )
    assert commands.calls[:2] == [
        (("shell", "input", "tap", "50", "100"), "serial-1"),
        (("shell", "input", "keyevent", "4"), "serial-1"),
    ]
    motion_actions = [call[0][4] for call in commands.calls[2:]]
    assert motion_actions == ["DOWN", "MOVE", "MOVE", "UP"]


def test_tap_outside_current_screen_is_rejected_without_adb() -> None:
    commands = RecordingCommands()
    inputs = AdbInputExecutor(commands, Device())  # type: ignore[arg-type]
    with pytest.raises(InputExecutionError, match="outside"):
        inputs.tap("serial-1", Point(100, 10))
    assert commands.calls == []
