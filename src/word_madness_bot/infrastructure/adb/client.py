"""Subprocess-backed implementation of the Android ADB port."""

from __future__ import annotations

import re
import socket
import subprocess
import time
from collections.abc import Callable, Sequence
from typing import Protocol

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
    SwipeExecutionReceipt,
    SwipePath,
)
from word_madness_bot.infrastructure.adb.screenshot import parse_png_size

Runner = Callable[..., subprocess.CompletedProcess[str] | subprocess.CompletedProcess[bytes]]
Sleeper = Callable[[float], None]
Launcher = Callable[..., subprocess.Popen[bytes]]
Connector = Callable[[tuple[str, int], float], socket.socket]


class MonkeyStream(Protocol):
    """Binary stream exposed by the Monkey network socket."""

    def write(self, data: bytes) -> int: ...

    def flush(self) -> None: ...

    def readline(self) -> bytes: ...
_MONKEY_DEVICE_PORT = 1080


class AdbClient(AndroidPort):
    """ADB adapter with bounded retries for idempotent operations only."""

    def __init__(
        self,
        settings: Settings,
        logger: StructuredLogger,
        *,
        runner: Runner = subprocess.run,
        sleeper: Sleeper = time.sleep,
        launcher: Launcher = subprocess.Popen,
        connector: Connector = socket.create_connection,
    ) -> None:
        self._settings = settings
        self._logger = logger
        self._runner = runner
        self._sleeper = sleeper
        self._launcher = launcher
        self._connector = connector
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

    def swipe(self, path: SwipePath) -> SwipeExecutionReceipt:
        timestamps = tuple(
            round(index * path.duration_ms / (len(path.points) - 1))
            for index in range(len(path.points))
        )
        commands = _build_monkey_touch_commands(path)
        script = "\n".join(commands) + "\n"
        debug_script_path = self._settings.debug_directory / "swipe_script.txt"
        debug_script_path.parent.mkdir(parents=True, exist_ok=True)
        debug_script_path.write_text(script, encoding="utf-8", newline="\n")
        self._logger.info(
            "adb.swipe.script.saved", output_filename=str(debug_script_path)
        )
        host_port = int(
            self._run_text(
                ["forward", "tcp:0", f"tcp:{_MONKEY_DEVICE_PORT}"], retry=False
            ).strip()
        )
        server_command = tuple(
            self._command(["shell", "monkey", "--port", str(_MONKEY_DEVICE_PORT)])
        )
        self._logger.info(
            "adb.swipe.backend_selected",
            backend="monkey_network_touch",
            backend_command=list(server_command),
            host_port=host_port,
            device_port=_MONKEY_DEVICE_PORT,
        )
        process: subprocess.Popen[bytes] | None = None
        try:
            process = self._launcher(
                list(server_command),
                stdin=subprocess.DEVNULL,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
            connection = self._connect_monkey(host_port, server_command)
            with connection, connection.makefile("rwb") as stream:
                self._send_touch_sequence(stream, commands, timestamps)
        finally:
            if process is not None and process.poll() is None:
                process.terminate()
                try:
                    process.wait(timeout=1.0)
                except subprocess.TimeoutExpired:
                    process.kill()
                    process.wait(timeout=1.0)
            try:
                self._run_text(
                    ["forward", "--remove", f"tcp:{host_port}"], retry=False
                )
            except AdbCommandError:
                self._logger.warning("adb.swipe.forward_cleanup_failed", host_port=host_port)
        self._logger.info(
            "adb.swipe.executed",
            duration_ms=path.duration_ms,
            point_count=len(path.points),
            backend="monkey_network_touch",
            backend_command=list(server_command),
            timestamps_ms=list(timestamps),
        )
        return SwipeExecutionReceipt(server_command, timestamps)

    def _connect_monkey(
        self, host_port: int, server_command: tuple[str, ...]
    ) -> socket.socket:
        for attempt in range(20):
            try:
                return self._connector(("127.0.0.1", host_port), 0.25)
            except OSError as error:
                if attempt == 19:
                    raise AdbCommandError(
                        server_command, 1, f"Monkey network server unavailable: {error}"
                    ) from error
                self._sleeper(0.05)
        raise AssertionError("unreachable")

    def _send_touch_sequence(
        self,
        stream: MonkeyStream,
        commands: tuple[str, ...],
        timestamps: tuple[int, ...],
    ) -> None:
        for index, command in enumerate(commands):
            if 0 < index < len(timestamps):
                self._sleeper((timestamps[index] - timestamps[index - 1]) / 1000)
            stream.write(f"{command}\n".encode())
            stream.flush()
            response = stream.readline().decode(errors="replace").strip()
            if not response.startswith("OK"):
                raise AdbCommandError(
                    ["monkey_network_touch", command], 1, response or "No response"
                )
        stream.write(b"quit\n")
        stream.flush()
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


def _build_monkey_touch_commands(path: SwipePath) -> tuple[str, ...]:
    commands = [f"touch down {path.points[0].x} {path.points[0].y}"]
    commands.extend(f"touch move {point.x} {point.y}" for point in path.points[1:])
    final_point = path.points[-1]
    commands.append(f"touch up {final_point.x} {final_point.y}")
    return tuple(commands)

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
