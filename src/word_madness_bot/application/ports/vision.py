"""Contract for image analysis without a vision implementation."""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from word_madness_bot.domain.models import ScreenCapture, VisionObservation


@runtime_checkable
class VisionPort(Protocol):
    """Replaceable boundary that converts captures into observations."""

    def analyze(self, capture: ScreenCapture) -> VisionObservation:
        """Analyze a capture without generating device input."""
        ...
