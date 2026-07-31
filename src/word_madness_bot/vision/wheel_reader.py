"""Composition of circle detection and OCR-backed letter extraction."""

import logging
from typing import Protocol

from word_madness_bot.domain.models import (
    CircleDetection,
    DetectedLetter,
    LetterWheel,
    ScreenGeometry,
)
from word_madness_bot.vision.debug_renderer import DebugRenderer
from word_madness_bot.vision.preprocessing import ImageArray

_LOGGER = logging.getLogger(__name__)


class CircleDetectionEngine(Protocol):
    """Structural boundary for a replaceable circle detector."""

    def detect(self, image: ImageArray, geometry: ScreenGeometry) -> CircleDetection | None:
        """Return a confidence-bearing circle or no result."""

        ...


class LetterExtractionEngine(Protocol):
    """Structural boundary for replaceable letter extraction."""

    def extract(
        self,
        image: ImageArray,
        circle: CircleDetection,
    ) -> tuple[DetectedLetter, ...]:
        """Return confidence-bearing letters in stable wheel order."""

        ...


class WheelReader:
    """Read a complete confidence-bearing letter wheel from an image."""

    def __init__(
        self,
        circle_detector: CircleDetectionEngine,
        letter_extractor: LetterExtractionEngine,
        debug_renderer: DebugRenderer | None = None,
        *,
        minimum_letters: int = 3,
        maximum_letters: int = 12,
    ) -> None:
        if minimum_letters <= 0 or maximum_letters < minimum_letters:
            raise ValueError("wheel letter-count bounds are invalid")
        self._circle_detector = circle_detector
        self._letter_extractor = letter_extractor
        self._debug_renderer = debug_renderer
        self._minimum_letters = minimum_letters
        self._maximum_letters = maximum_letters

    def read(self, image: ImageArray, geometry: ScreenGeometry) -> LetterWheel | None:
        """Return a wheel only when its geometry and letter count are credible."""

        circle = self._circle_detector.detect(image, geometry)
        if circle is None:
            return None
        letters = self._letter_extractor.extract(image, circle)
        if not self._minimum_letters <= len(letters) <= self._maximum_letters:
            _LOGGER.debug("Rejected wheel with %d letters", len(letters))
            if self._debug_renderer is not None:
                self._debug_renderer.render(
                    image, "wheel_rejected.png", circle=circle, letters=letters
                )
            return None
        mean_letter_confidence = sum(letter.confidence for letter in letters) / len(letters)
        confidence = min(circle.confidence, mean_letter_confidence)
        wheel = LetterWheel(
            center=circle.center,
            radius=circle.radius,
            letters=letters,
            confidence=confidence,
        )
        if self._debug_renderer is not None:
            self._debug_renderer.render(image, "wheel_detected.png", circle=circle, letters=letters)
        return wheel
