"""Contract for screenshot acquisition."""

from typing import Protocol

from word_madness_bot.domain.models import CapturedFrame


class ScreenshotCapture(Protocol):
    """Acquire screenshots without performing any image analysis."""

    def capture(self, serial: str) -> CapturedFrame:
        """Capture and return one frame from the selected device."""

        ...
