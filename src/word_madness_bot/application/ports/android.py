"""Contract for Android communication without an ADB implementation."""

from __future__ import annotations

from collections.abc import Sequence
from typing import Protocol, runtime_checkable

from word_madness_bot.domain.geometry import PixelPoint
from word_madness_bot.domain.models import (
    DeviceDescriptor,
    DisplayMetrics,
    ScreenCapture,
    SwipePath,
)


@runtime_checkable
class AndroidPort(Protocol):
    """Replaceable Android device boundary required by application services."""

    def discover_devices(self) -> tuple[DeviceDescriptor, ...]:
        """Return every device visible to the transport."""
        ...

    def select_device(self, serial: str | None = None) -> DeviceDescriptor:
        """Select one usable device explicitly or by policy."""
        ...

    def verify_connection(self) -> bool:
        """Return whether the selected device transport is responsive."""
        ...

    def get_display_metrics(self) -> DisplayMetrics:
        """Return detected size and density for the selected device."""
        ...

    def capture_screenshot(self) -> ScreenCapture:
        """Acquire a screenshot without interpreting it."""
        ...

    def tap(self, point: PixelPoint) -> None:
        """Execute one tap at a completed device coordinate."""
        ...

    def swipe(self, path: SwipePath) -> None:
        """Execute one completed swipe path."""
        ...

    def press_back(self) -> None:
        """Press the Android Back key once."""
        ...

    def press_home(self) -> None:
        """Press the Android Home key once."""
        ...

    def execute_shell(
        self,
        command: Sequence[str],
        *,
        timeout_seconds: float | None = None,
    ) -> str:
        """Execute one shell command and return text output."""
        ...
