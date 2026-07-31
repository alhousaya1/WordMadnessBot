"""Subprocess-backed implementation of the Android ADB port."""

from __future__ import annotations

import re
import subprocess
import time
from collections.abc import Callable, Sequence

from word_madness_bot.application.ports.android import AndroidPort
from word_madness_bot.config.logging import StructuredLogger
from word_madness_bot.config.settings import Settings
from word_madness_bot.domain.errors import (
    AdbCommandError,
    AdbExecutableNotFoundError,
    AdbTimeoutError,
    DeviceConnectionError,
    DeviceSelectionError,
    ScreenshotError,
)
from word_madness_bot.domain.geometry import PixelPoint, ScreenSize
from word_madness_bot.domain.models import (
    DeviceDescriptor,
    DeviceState,
    DisplayMetrics,
    ScreenCapture,
    SwipePath,
)
from word_madness_bot.infrastructure.adb.screenshot import parse_png_size

Runner = Callable[..., subprocess.CompletedProcess[str] | subprocess.CompletedProcess[bytes]]
Sleeper = Callable[[float], None]


class AdbClient(AndroidPort):
    """ADB adapter with bounded retries for idempotent operations only."""

    def __init__(
        self,
        settings: Settings,
        logger: StructuredLogger,
        *,
        runner: Runner = subprocess.run,
        sleeper: Sleeper = time.sleep,
    ) -> None:
        self._settings = settings
        self._logger = logger
        self._runner = runner
        self._sleeper = sleeper
        self._device: DeviceDescriptor | None = None

    def discover_devices(self) -> tuple[DeviceDescriptor, ...]:
        output = self._run_text(["devices", "-l"], retry=True)
        devices = _parse_devices(output)
        self._logger.info("adb.devices.discovered", count=len(devices))
        return devices

    def select_device(self, serial: str | None = None) -> DeviceDescriptor:
        devices = self.discover_devices()
        if serial is not None:
            matches = [device for device in devices if device.serial == serial]
            if not matches:
                raise DeviceSelectionError(f"ADB device {serial!r} was not found")
            selected = matches[0]
        else:
            online = [device for device in devices if device.state is DeviceState.ONLINE]
            if len(online) != 1:
                raise DeviceSelectionError(
                    f"Automatic selection requires exactly one online device; found {len(online)}"
                )
            selected = online[0]
        if selected.state is not DeviceState.ONLINE:
            raise DeviceConnectionError(selected.serial, selected.state.value)
        self._device = selected
        self._logger.info("adb.device.selected", serial=selected.serial)
        return selected

    def verify_connection(self) -> bool:
        serial = self._selected_serial()
        state = self._run_text(["get-state"], serial=serial, retry=True).strip()
        if state != "device":
            raise DeviceConnectionError(serial, state or "unknown")
        return True

    def get_display_metrics(self) -> DisplayMetrics:
        size_output = self.execute_shell(["wm", "size"])
        density_output = self.execute_shell(["wm", "density"])
        return DisplayMetrics(
            size=_parse_size(size_output), density_dpi=_parse_density(density_output)
        )

    def capture_screenshot(self) -> ScreenCapture:
        data = self._run_binary(["exec-out", "screencap", "-p"], retry=True)
        try:
            size = parse_png_size(data)
        except ScreenshotError:
            self._logger.error("adb.screenshot.invalid", bytes=len(data))
            raise
        self._logger.info("adb.screenshot.captured", bytes=len(data))
        return ScreenCapture(data=data, size=size)

    def tap(self, point: PixelPoint) -> None:
        self._run_text(["shell", "input", "tap", str(point.x), str(point.y)], retry=False)

    def swipe(self, path: SwipePath) -> None:
        start, end = path.points[0], path.points[-1]
        self._run_text(
            [
                "shell",
                "input",
                "swipe",
                str(start.x),
                str(start.y),
                str(end.x),
                str(end.y),
                str(path.duration_ms),
            ],
            retry=False,
        )

    def press_back(self) -> None:
        self._run_text(["shell", "input", "keyevent", "BACK"], retry=False)

    def press_home(self) -> None:
        self._run_text(["shell", "input", "keyevent", "HOME"], retry=False)

    def execute_shell(self, command: Sequence[str], *, timeout_seconds: float | None = None) -> str:
        if not command or any(not argument for argument in command):
            raise ValueError("Shell command arguments cannot be empty")
        return self._run_text(["shell", *command], timeout=timeout_seconds, retry=True)

    def _selected_serial(self) -> str:
        if self._device is None:
            raise DeviceSelectionError("No ADB device has been selected")
        return self._device.serial

    def _command(self, arguments: Sequence[str], serial: str | None = None) -> list[str]:
        chosen = serial
        if chosen is None and arguments[0] not in {"devices"}:
            chosen = self._selected_serial()
        return [
            self._settings.adb_executable,
            *([] if chosen is None else ["-s", chosen]),
            *arguments,
        ]

    def _run_text(
        self,
        arguments: Sequence[str],
        *,
        serial: str | None = None,
        timeout: float | None = None,
        retry: bool,
    ) -> str:
        result = self._run(arguments, serial=serial, timeout=timeout, retry=retry, text=True)
        assert isinstance(result.stdout, str)
        return result.stdout

    def _run_binary(self, arguments: Sequence[str], *, retry: bool) -> bytes:
        result = self._run(arguments, timeout=None, retry=retry, text=False)
        assert isinstance(result.stdout, bytes)
        return result.stdout

    def _run(
        self,
        arguments: Sequence[str],
        *,
        serial: str | None = None,
        timeout: float | None,
        retry: bool,
        text: bool,
    ) -> subprocess.CompletedProcess[str] | subprocess.CompletedProcess[bytes]:
        command = self._command(arguments, serial)
        attempts = self._settings.adb_retries + 1 if retry else 1
        for attempt in range(1, attempts + 1):
            try:
                result = self._runner(
                    command,
                    capture_output=True,
                    check=False,
                    text=text,
                    timeout=timeout or self._settings.adb_timeout_seconds,
                )
            except FileNotFoundError as error:
                raise AdbExecutableNotFoundError(self._settings.adb_executable) from error
            except subprocess.TimeoutExpired as error:
                failure: AdbCommandError = AdbTimeoutError(command, error.timeout)
            else:
                if result.returncode == 0:
                    return result
                stderr = (
                    result.stderr
                    if isinstance(result.stderr, str)
                    else result.stderr.decode(errors="replace")
                )
                failure = AdbCommandError(command, result.returncode, stderr.strip())
            self._logger.warning(
                "adb.command.failed", command=command, attempt=attempt, retrying=attempt < attempts
            )
            if attempt < attempts:
                self._sleeper(min(0.1 * (2 ** (attempt - 1)), 1.0))
        raise failure


def _parse_devices(output: str) -> tuple[DeviceDescriptor, ...]:
    devices: list[DeviceDescriptor] = []
    lines = output.splitlines()
    if lines and lines[0].startswith("List of devices"):
        lines = lines[1:]
    for line in lines:
        stripped = line.strip()
        if not stripped or stripped.startswith("*"):
            continue
        fields = stripped.split()
        if len(fields) < 2:
            continue
        serial, raw_state = fields[:2]
        state = {
            "device": DeviceState.ONLINE,
            "offline": DeviceState.OFFLINE,
            "unauthorized": DeviceState.UNAUTHORIZED,
        }.get(raw_state, DeviceState.UNKNOWN)
        attributes = tuple(
            (field.split(":", 1)[0], field.split(":", 1)[1]) for field in fields[2:] if ":" in field
        )
        devices.append(DeviceDescriptor(serial, state, attributes))
    return tuple(devices)


def _parse_size(output: str) -> ScreenSize:
    matches = re.findall(r"(?:Override|Physical) size:\s*(\d+)x(\d+)", output)
    if not matches:
        raise AdbCommandError(["wm", "size"], 0, "Unrecognized display size")
    width, height = matches[-1]
    return ScreenSize(int(width), int(height))


def _parse_density(output: str) -> int:
    matches = re.findall(r"(?:Override|Physical) density:\s*(\d+)", output)
    if not matches:
        raise AdbCommandError(["wm", "density"], 0, "Unrecognized display density")
    return int(matches[-1])
