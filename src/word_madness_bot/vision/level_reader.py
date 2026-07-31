"""Resolution-independent OCR reader for the visible level number."""

import logging
import re

from word_madness_bot.domain.models import LevelReading, ScreenGeometry
from word_madness_bot.vision.geometry import NormalizedBox, to_pixel_box
from word_madness_bot.vision.ocr import OcrEngine
from word_madness_bot.vision.preprocessing import (
    ImageArray,
    autocontrast,
    crop,
    resize,
    threshold,
)

_LOGGER = logging.getLogger(__name__)
_LEVEL_PATTERN = re.compile(r"\d+")
_DEFAULT_LEVEL_REGION = NormalizedBox(0.20, 0.02, 0.62, 0.12)


class LevelReader:
    """Read a level number from a normalized header region using injected OCR."""

    def __init__(
        self,
        ocr_engine: OcrEngine,
        region: NormalizedBox = _DEFAULT_LEVEL_REGION,
        *,
        minimum_confidence: float = 0.45,
    ) -> None:
        if not 0.0 <= minimum_confidence <= 1.0:
            raise ValueError("minimum confidence must be between 0.0 and 1.0")
        self._ocr_engine = ocr_engine
        self._region = region
        self._minimum_confidence = minimum_confidence

    def read(self, image: ImageArray, geometry: ScreenGeometry) -> LevelReading | None:
        """Return the first positive OCR number meeting the confidence threshold."""

        level_region = to_pixel_box(self._region, geometry)
        prepared = autocontrast(crop(image, level_region))
        prepared = resize(prepared, prepared.shape[1] * 2, prepared.shape[0] * 2)
        prepared = threshold(prepared, 150)
        result = self._ocr_engine.recognize(prepared, whitelist="0123456789")
        if result is None or result.confidence < self._minimum_confidence:
            _LOGGER.debug("Level OCR returned no sufficiently confident result")
            return None
        match = _LEVEL_PATTERN.search(result.text)
        if match is None:
            _LOGGER.debug("Level OCR text contains no number: %r", result.text)
            return None
        number = int(match.group())
        if number <= 0:
            return None
        return LevelReading(number=number, confidence=result.confidence, raw_text=result.text)
