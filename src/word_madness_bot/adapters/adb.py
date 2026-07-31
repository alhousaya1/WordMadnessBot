"""Production Android Debug Bridge command, capture, and input adapters."""

import logging
import subprocess
import threading
from collections.abc import Sequence
from contextlib import suppress
from datetime import UTC, datetime
from io import BytesIO
from time import sleep

from PIL import Image

from word_madness_bot.config import Settings
from word_madness_bot.domain.errors import CaptureError, DeviceError, InputExecutionError
from word_madness_bot.domain.models import (
    CapturedFrame,
    DeviceInfo,
    Point,
    ScreenGeometry,
    SwipePath,
)
from word_madness_bot.vision.geometry import to_pixel_point

_LOGGER = logging.getLogger(__name__)


class AdbCommandExecutor:
    """Execute one bounded ADB process at a time and surface deterministic failures."""

    def __init__(self, command: str = "adb", timeout_seconds: float = 15.0) -> None:
        if not command.strip() or timeout_seconds <= 0.0:
            raise ValueError("ADB command and timeout must be valid")
        self._command = command
        self._timeout_seconds = timeout_seconds
        self._lock = threading.Lock()

    def execute(self, arguments: Sequence[str], *, serial: str | None = None) -> bytes:
        """Run one ADB invocation, blocking concurrent invocations until it completes."""

        command = [self._command]
        if serial is not None:
            command.extend(("-s", serial))
        command.extend(arguments)
        _LOGGER.debug("Executing ADB command", extra={"event": "adb.execute", "args": command[1:]})
        try:
            with self._lock:
                result = subprocess.run(
                    command,
                    capture_output=True,
                    timeout=self._timeout_seconds,
                    check=False,
                )
        except (FileNotFoundError, subprocess.TimeoutExpired) as error:
            raise DeviceError(f"ADB command failed: {error}") from error
        if result.returncode != 0:
            detail = result.stderr.decode("utf-8", errors="replace").strip()
            raise DeviceError(f"ADB command returned {result.returncode}: {detail}")
        return result.stdout


class AdbRuntimeAdapter:
    """Implement device discovery and screenshot capture through an ADB executor."""

    def __init__(self, executor: AdbCommandExecutor) -> None:
        self._executor = executor

    @classmethod
    def from_settings(cls, settings: Settings) -> "AdbRuntimeAdapter":
        """Construct the adapter from validated runtime settings."""

        return cls(AdbCommandExecutor(settings.adb_command, settings.adb_timeout_seconds))

    def list_devices(self) -> tuple[str, ...]:
        """Return authorized device serials in deterministic order."""

        lines = self._executor.execute(("devices",)).decode().splitlines()[1:]
        return tuple(sorted(line.split()[0] for line in lines if line.endswith("\tdevice")))

    def get_device_info(self, serial: str) -> DeviceInfo:
        """Read device metadata and physical screen geometry."""

        model = self._shell(serial, "getprop", "ro.product.model")
        version = self._shell(serial, "getprop", "ro.build.version.release")
        size_text = self._shell(serial, "wm", "size").split(":")[-1].strip()
        density_text = self._shell(serial, "wm", "density").split(":")[-1].strip()
        try:
            width_text, height_text = size_text.split("x", maxsplit=1)
            geometry = ScreenGeometry(int(width_text), int(height_text), int(density_text))
        except ValueError as error:
            raise DeviceError("ADB returned malformed screen geometry") from error
        return DeviceInfo(serial, model, version, geometry)

    def is_available(self, serial: str) -> bool:
        """Return whether a device remains authorized."""

        return serial in self.list_devices()

    def capture(self, serial: str) -> CapturedFrame:
        """Capture and validate one PNG screenshot without image analysis."""

        data = self._executor.execute(("exec-out", "screencap", "-p"), serial=serial)
        try:
            with Image.open(BytesIO(data)) as image:
                width, height = image.size
                image.verify()
        except OSError as error:
            raise CaptureError("ADB returned an invalid screenshot") from error
        density = self.get_device_info(serial).screen.density_dpi
        return CapturedFrame(
            data,
            ScreenGeometry(width, height, density),
            datetime.now(UTC),
        )

    def _shell(self, serial: str, *arguments: str) -> str:
        return self._executor.execute(("shell", *arguments), serial=serial).decode().strip()


class AdbInputExecutor:
    """Execute completed absolute taps and normalized paths without gameplay decisions."""

    def __init__(self, executor: AdbCommandExecutor, devices: AdbRuntimeAdapter) -> None:
        self._executor = executor
        self._devices = devices
        self._lock = threading.Lock()

    def tap(self, serial: str, point: Point) -> None:
        """Execute one absolute tap after validating it against current screen bounds."""

        geometry = self._devices.get_device_info(serial).screen
        if point.x >= geometry.width or point.y >= geometry.height:
            raise InputExecutionError("tap lies outside current screen bounds")
        self._execute_input(serial, "tap", str(point.x), str(point.y))

    def swipe(self, serial: str, path: SwipePath) -> None:
        """Trace every normalized path point using Android motion events."""

        geometry = self._devices.get_device_info(serial).screen
        points = tuple(to_pixel_point(point, geometry) for point in path.points)
        delay = path.duration_ms / 1000.0 / (len(points) - 1)
        with self._lock:
            pointer_down = False
            try:
                self._motion_event(serial, "DOWN", points[0])
                pointer_down = True
                for point in points[1:]:
                    sleep(delay)
                    self._motion_event(serial, "MOVE", point)
                self._motion_event(serial, "UP", points[-1])
            except DeviceError as error:
                # Best-effort release prevents a failed gesture from leaving a held pointer.
                if pointer_down:
                    with suppress(DeviceError):
                        self._motion_event(serial, "UP", points[-1])
                raise InputExecutionError(f"swipe execution failed: {error}") from error

    def key_event(self, serial: str, key_code: int) -> None:
        """Execute one Android key event, including the configured Back key."""

        if key_code < 0:
            raise InputExecutionError("key code cannot be negative")
        self._execute_input(serial, "keyevent", str(key_code))

    def _execute_input(self, serial: str, *arguments: str) -> None:
        try:
            with self._lock:
                self._executor.execute(("shell", "input", *arguments), serial=serial)
        except DeviceError as error:
            raise InputExecutionError(f"input execution failed: {error}") from error

    def _motion_event(self, serial: str, action: str, point: Point) -> None:
        self._executor.execute(
            ("shell", "input", "touchscreen", "motionevent", action, str(point.x), str(point.y)),
            serial=serial,
        )
