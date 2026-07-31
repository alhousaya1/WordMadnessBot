"""Reliable Android Debug Bridge adapter for device I/O."""

from __future__ import annotations

import re
import shlex
import subprocess
import time
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Literal, overload

from config.config import ADB_COMMAND, ADB_TIMEOUT, SCREENSHOT_FOLDER
from config.logger import logger

_PNG_SIGNATURE = b"\x89PNG\r\n\x1a\n"
_SIZE_PATTERN = re.compile(r"(?:Physical|Override) size:\s*(\d+)x(\d+)")
_DENSITY_PATTERN = re.compile(r"(?:Physical|Override) density:\s*(\d+)")
_TRANSIENT_MESSAGES = (
    "device offline",
    "device not found",
    "device still authorizing",
    "protocol fault",
    "transport error",
    "connection reset",
    "closed",
)


class ADBError(RuntimeError):
    """Base class for failures produced by the ADB adapter."""


class ADBNotFoundError(ADBError):
    """Raised when the ADB executable cannot be started."""


class ADBTimeoutError(ADBError):
    """Raised when an ADB process exceeds its configured timeout."""


class ADBCommandError(ADBError):
    """Raised when ADB exits unsuccessfully."""

    def __init__(self, command: Sequence[str], return_code: int, stderr: str) -> None:
        self.command = tuple(command)
        self.return_code = return_code
        self.stderr = stderr
        detail = stderr or "ADB returned no error output"
        super().__init__(f"ADB command failed ({return_code}): {detail}")


class ADBDeviceError(ADBError):
    """Raised when no usable Android device is available."""


class ADBScreenshotError(ADBError):
    """Raised when screenshot acquisition returns invalid image data."""


@dataclass(frozen=True, slots=True)
class ADBDevice:
    """A device entry reported by ``adb devices -l``."""

    serial: str
    state: str
    details: dict[str, str]


Runner = Callable[..., subprocess.CompletedProcess[Any]]


class ADBController:
    """Production ADB adapter with bounded retries and typed failures."""

    def __init__(
        self,
        *,
        adb_command: str = ADB_COMMAND,
        timeout: float = ADB_TIMEOUT,
        retries: int = 2,
        retry_delay: float = 0.25,
        screenshot_folder: Path = SCREENSHOT_FOLDER,
        runner: Runner = subprocess.run,
        sleeper: Callable[[float], None] = time.sleep,
    ) -> None:
        if timeout <= 0:
            raise ValueError("timeout must be greater than zero")
        if retries < 0:
            raise ValueError("retries cannot be negative")
        if retry_delay < 0:
            raise ValueError("retry_delay cannot be negative")
        self.adb_command = adb_command
        self.timeout = timeout
        self.retries = retries
        self.retry_delay = retry_delay
        self.screenshot_folder = Path(screenshot_folder)
        self._runner = runner
        self._sleeper = sleeper
        self.device: str | None = None
        self.model = ""
        self.android_version = ""
        self.width = 0
        self.height = 0
        self.density = 0

    def _log(self, level: str, event: str, **fields: object) -> None:
        """Emit stable key/value fields through the project's logger."""
        context = " ".join(f"{key}={value!r}" for key, value in sorted(fields.items()))
        message = f"event={event}" + (f" {context}" if context else "")
        getattr(logger, level)(message)

    def _command(self, arguments: Sequence[str], use_device: bool) -> list[str]:
        command = [self.adb_command]
        if use_device:
            if self.device is None:
                raise ADBDeviceError("No Android device has been selected.")
            command.extend(("-s", self.device))
        command.extend(str(argument) for argument in arguments)
        return command

    @overload
    def _execute(
        self,
        arguments: Sequence[str],
        *,
        binary: Literal[False] = False,
        timeout: float | None = None,
        retries: int = 0,
        use_device: bool = False,
    ) -> str: ...

    @overload
    def _execute(
        self,
        arguments: Sequence[str],
        *,
        binary: Literal[True],
        timeout: float | None = None,
        retries: int = 0,
        use_device: bool = False,
    ) -> bytes: ...

    def _execute(
        self,
        arguments: Sequence[str],
        *,
        binary: bool = False,
        timeout: float | None = None,
        retries: int = 0,
        use_device: bool = False,
    ) -> str | bytes:
        effective_timeout = self.timeout if timeout is None else timeout
        if effective_timeout <= 0:
            raise ValueError("timeout must be greater than zero")
        if retries < 0:
            raise ValueError("retries cannot be negative")
        command = self._command(arguments, use_device)
        for attempt in range(retries + 1):
            self._log(
                "info",
                "adb.command.start",
                attempt=attempt + 1,
                command=command,
                timeout=effective_timeout,
            )
            try:
                completed = self._runner(
                    command,
                    capture_output=True,
                    text=not binary,
                    timeout=effective_timeout,
                    check=False,
                )
            except FileNotFoundError as error:
                self._log("error", "adb.executable.missing", command=self.adb_command)
                raise ADBNotFoundError(
                    f"ADB executable was not found: {self.adb_command}"
                ) from error
            except subprocess.TimeoutExpired as error:
                if attempt < retries:
                    self._retry_wait(attempt, "timeout")
                    continue
                self._log("error", "adb.command.timeout", command=command)
                raise ADBTimeoutError(
                    f"ADB command timed out after {effective_timeout:g} seconds"
                ) from error
            except OSError as error:
                if attempt < retries:
                    self._retry_wait(attempt, type(error).__name__)
                    continue
                self._log("error", "adb.command.os_error", error=str(error))
                raise ADBError(f"Unable to execute ADB: {error}") from error

            stdout = completed.stdout or (b"" if binary else "")
            stderr_value = completed.stderr or (b"" if binary else "")
            stderr = (
                stderr_value.decode(errors="replace")
                if isinstance(stderr_value, bytes)
                else str(stderr_value)
            ).strip()
            if completed.returncode == 0:
                self._log(
                    "info", "adb.command.success", attempt=attempt + 1, command=command
                )
                if binary:
                    return stdout if isinstance(stdout, bytes) else str(stdout).encode()
                return str(stdout).strip()

            is_transient = any(
                marker in stderr.lower() for marker in _TRANSIENT_MESSAGES
            )
            if attempt < retries and is_transient:
                self._retry_wait(attempt, stderr or "transient ADB failure")
                continue
            self._log(
                "error",
                "adb.command.failed",
                command=command,
                return_code=completed.returncode,
                stderr=stderr,
            )
            raise ADBCommandError(command, completed.returncode, stderr)
        raise AssertionError("ADB retry loop exited unexpectedly")

    def _retry_wait(self, attempt: int, reason: str) -> None:
        delay = self.retry_delay * (2**attempt)
        self._log("warning", "adb.command.retry", delay=delay, reason=reason)
        self._sleeper(delay)

    def run(
        self,
        command: Sequence[str],
        *,
        timeout: float | None = None,
        retry: bool = False,
    ) -> str:
        """Execute a host-level ADB command and return standard output."""
        return self._execute(
            command, timeout=timeout, retries=self.retries if retry else 0
        )

    def execute_shell(
        self,
        command: str | Sequence[str],
        *,
        timeout: float | None = None,
        retry: bool = False,
    ) -> str:
        """Execute a command in the selected device's Android shell."""
        arguments = shlex.split(command) if isinstance(command, str) else list(command)
        if not arguments:
            raise ValueError("shell command cannot be empty")
        return self._execute(
            ["shell", *arguments],
            timeout=timeout,
            retries=self.retries if retry else 0,
            use_device=True,
        )

    def shell(
        self,
        command: str | Sequence[str],
        *,
        timeout: float | None = None,
        retry: bool = False,
    ) -> str:
        """Backward-compatible alias for :meth:`execute_shell`."""
        return self.execute_shell(command, timeout=timeout, retry=retry)

    def discover_devices(self) -> tuple[ADBDevice, ...]:
        """Return all devices and their connection states."""
        output = self.run(["devices", "-l"], retry=True)
        devices: list[ADBDevice] = []
        for raw_line in output.splitlines():
            line = raw_line.strip()
            if not line or line.startswith(("List of devices", "*")):
                continue
            parts = line.split()
            if len(parts) < 2:
                continue
            details = {
                key: value
                for item in parts[2:]
                if ":" in item
                for key, value in (item.split(":", 1),)
            }
            devices.append(ADBDevice(parts[0], parts[1], details))
        self._log("info", "adb.devices.discovered", count=len(devices))
        return tuple(devices)

    def connect(self, serial: str | None = None) -> bool:
        """Select an online device and verify that its transport responds."""
        devices = self.discover_devices()
        if serial is not None:
            matching = [device for device in devices if device.serial == serial]
            if not matching:
                raise ADBDeviceError(f"Android device was not found: {serial}")
            selected = matching[0]
            if selected.state != "device":
                raise ADBDeviceError(
                    f"Android device {serial} is not ready (state={selected.state})."
                )
        else:
            online = [device for device in devices if device.state == "device"]
            if not online:
                states = ", ".join(
                    f"{device.serial}:{device.state}" for device in devices
                )
                detail = f" Reported devices: {states}." if states else ""
                raise ADBDeviceError(f"No online Android device is available.{detail}")
            selected = online[0]
            if len(online) > 1:
                self._log(
                    "warning",
                    "adb.device.multiple",
                    selected=selected.serial,
                    total=len(online),
                )
        self.device = selected.serial
        try:
            self.verify_connection()
        except ADBError:
            self.device = None
            raise
        self._log("success", "adb.device.connected", serial=selected.serial)
        return True

    def verify_connection(self) -> bool:
        """Verify that the selected device is in the online state."""
        state = self._execute(
            ["get-state"], retries=self.retries, use_device=True
        )
        if state.strip() != "device":
            raise ADBDeviceError(
                f"Android device {self.device} is not connected (state={state!r})."
            )
        self._log("info", "adb.device.verified", serial=self.device)
        return True

    def get_screen_resolution(self) -> tuple[int, int]:
        """Detect and cache the device's active screen resolution."""
        output = self.shell(["wm", "size"], retry=True)
        matches = _SIZE_PATTERN.findall(output)
        if not matches:
            raise ADBDeviceError(f"Could not parse screen resolution from: {output!r}")
        width, height = (int(value) for value in matches[-1])
        if width <= 0 or height <= 0:
            raise ADBDeviceError(f"Invalid screen resolution: {width}x{height}")
        self.width, self.height = width, height
        self._log("info", "adb.screen.resolution", width=width, height=height)
        return width, height

    def read_phone_information(self) -> None:
        """Populate model, Android version, resolution, and display density."""
        self.model = self.shell(["getprop", "ro.product.model"], retry=True)
        self.android_version = self.shell(
            ["getprop", "ro.build.version.release"], retry=True
        )
        self.get_screen_resolution()
        density_output = self.shell(["wm", "density"], retry=True)
        densities = _DENSITY_PATTERN.findall(density_output)
        if not densities:
            raise ADBDeviceError(
                f"Could not parse display density from: {density_output!r}"
            )
        self.density = int(densities[-1])
        self._log(
            "success",
            "adb.device.info",
            android=self.android_version,
            density=self.density,
            height=self.height,
            model=self.model,
            width=self.width,
        )

    def screenshot(self, destination: Path | None = None) -> Path:
        """Capture a PNG screenshot atomically and return its local path."""
        filename = (
            Path(destination) if destination else self.screenshot_folder / "latest.png"
        )
        data = self._execute(
            ["exec-out", "screencap", "-p"],
            binary=True,
            retries=self.retries,
            use_device=True,
        )
        if not data.startswith(_PNG_SIGNATURE):
            raise ADBScreenshotError("ADB returned invalid PNG screenshot data.")
        filename.parent.mkdir(parents=True, exist_ok=True)
        temporary = filename.with_suffix(f"{filename.suffix}.tmp")
        try:
            temporary.write_bytes(data)
            temporary.replace(filename)
        except OSError as error:
            temporary.unlink(missing_ok=True)
            raise ADBScreenshotError(
                f"Could not save screenshot to {filename}: {error}"
            ) from error
        self._log("success", "adb.screenshot.saved", path=str(filename), size=len(data))
        return filename

    @staticmethod
    def _coordinate(value: int, name: str) -> str:
        if isinstance(value, bool) or not isinstance(value, int) or value < 0:
            raise ValueError(f"{name} must be a non-negative integer")
        return str(value)

    def tap(self, x: int, y: int) -> None:
        """Tap a screen coordinate once; input events are never retried."""
        coordinates = [self._coordinate(x, "x"), self._coordinate(y, "y")]
        self._log("info", "adb.input.tap", x=x, y=y)
        self.shell(["input", "tap", *coordinates])

    def swipe(
        self,
        x1: int,
        y1: int,
        x2: int,
        y2: int,
        duration: int = 150,
    ) -> None:
        """Swipe between coordinates once; input events are never retried."""
        if isinstance(duration, bool) or not isinstance(duration, int) or duration <= 0:
            raise ValueError("duration must be a positive integer")
        arguments = [
            self._coordinate(x1, "x1"),
            self._coordinate(y1, "y1"),
            self._coordinate(x2, "x2"),
            self._coordinate(y2, "y2"),
            str(duration),
        ]
        self._log(
            "info",
            "adb.input.swipe",
            duration=duration,
            x1=x1,
            x2=x2,
            y1=y1,
            y2=y2,
        )
        self.shell(["input", "swipe", *arguments])

    def back(self) -> None:
        """Press the Android Back button once."""
        self._log("info", "adb.input.key", key="BACK")
        self.shell(["input", "keyevent", "KEYCODE_BACK"])

    def home(self) -> None:
        """Press the Android Home button once."""
        self._log("info", "adb.input.key", key="HOME")
        self.shell(["input", "keyevent", "KEYCODE_HOME"])

    def sleep(self, seconds: float) -> None:
        """Sleep through the injected clock for compatibility and testing."""
        if seconds < 0:
            raise ValueError("seconds cannot be negative")
        self._sleeper(seconds)
