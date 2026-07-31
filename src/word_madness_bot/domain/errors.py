"""Typed exceptions reported across production architecture boundaries."""

from __future__ import annotations

from collections.abc import Sequence


class WordMadnessError(Exception):
    """Base exception for expected production failures."""


class ConfigurationError(WordMadnessError):
    """Raised when runtime configuration is invalid."""


class DomainValidationError(WordMadnessError, ValueError):
    """Raised when a domain value violates an invariant."""


class PortError(WordMadnessError):
    """Base exception for replaceable boundary failures."""


class AdbError(PortError):
    """Base exception for ADB transport failures."""


class AdbExecutableNotFoundError(AdbError):
    """Raised when the configured ADB executable cannot be started."""

    def __init__(self, executable: str) -> None:
        super().__init__(f"ADB executable was not found: {executable}")


class AdbCommandError(AdbError):
    """Raised when an ADB command returns an unsuccessful result."""

    def __init__(self, command: Sequence[str], returncode: int, stderr: str) -> None:
        self.command = tuple(command)
        self.returncode = returncode
        self.stderr = stderr
        super().__init__(f"ADB command failed with exit code {returncode}: {stderr}")


class AdbTimeoutError(AdbCommandError):
    """Raised after a bounded ADB command exceeds its timeout."""

    def __init__(self, command: Sequence[str], timeout: float) -> None:
        self.timeout = timeout
        super().__init__(command, -1, f"Timed out after {timeout} seconds")


class DeviceSelectionError(AdbError):
    """Raised when a usable device cannot be selected unambiguously."""


class DeviceConnectionError(AdbError):
    """Raised when a selected device is not online."""

    def __init__(self, serial: str, state: str) -> None:
        self.serial = serial
        self.state = state
        super().__init__(f"ADB device {serial!r} is not connected: {state}")


class ScreenshotError(AdbError):
    """Raised when screenshot acquisition or validation fails."""
