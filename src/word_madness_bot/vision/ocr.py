"""Replaceable OCR abstraction and validation facade."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

from PIL import Image

from word_madness_bot.domain.errors import OcrError


@dataclass(frozen=True, slots=True)
class OcrResult:
    text: str
    confidence: float


class OcrEngine(Protocol):
    def recognize(self, image: Image.Image) -> OcrResult: ...


def recognize(engine: OcrEngine, image: Image.Image) -> OcrResult:
    """Run an OCR backend and validate its transport-neutral result."""
    try:
        result = engine.recognize(image)
    except Exception as error:
        raise OcrError("OCR engine failed") from error
    if (
        not isinstance(result, OcrResult)
        or not result.text.strip()
        or not 0 <= result.confidence <= 1
    ):
        raise OcrError("OCR engine returned an invalid result")
    return OcrResult(result.text.strip(), result.confidence)
