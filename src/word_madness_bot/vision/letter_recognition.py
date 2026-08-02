"""Wheel-letter cropping, normalization, and embedded OpenCV OCR."""

from __future__ import annotations

import io
import json
import string
import time
from collections.abc import Callable
from dataclasses import dataclass
from importlib import import_module
from importlib.resources import files
from pathlib import Path
from typing import Any, Protocol

from PIL import Image

from word_madness_bot.domain.errors import OcrError
from word_madness_bot.domain.models import ScreenCapture
from word_madness_bot.vision.ocr import OcrEngine, OcrResult, recognize
from word_madness_bot.vision.wheel_geometry import LetterWheelGeometry

cv2: Any = import_module("cv2")
np: Any = import_module("numpy")
Clock = Callable[[], float]


@dataclass(frozen=True, slots=True)
class RecognizedLetter:
    """One indexed wheel character and its OCR evidence."""

    index: int
    character: str
    confidence: float
    elapsed_seconds: float
    crop_path: Path


@dataclass(frozen=True, slots=True)
class WheelLetterRecognition:
    """Recognition output for one wheel, without solving semantics."""

    letters: tuple[RecognizedLetter, ...]
    level: int | None = None

    def to_dict(self) -> dict[str, object]:
        """Return the stable public JSON representation."""
        return {
            "level": self.level,
            "letters": [
                {
                    "index": item.index,
                    "character": item.character,
                    "confidence": item.confidence,
                }
                for item in self.letters
            ],
        }


class WheelLetterRecognitionPort(Protocol):
    """Runtime boundary for crop extraction and character recognition."""

    def recognize(
        self,
        capture: ScreenCapture,
        geometry: LetterWheelGeometry,
        debug_directory: Path,
    ) -> WheelLetterRecognition: ...


class OpenCvTemplateOcrEngine:
    """Recognize one normalized uppercase glyph using packaged A-Z templates."""

    def __init__(self) -> None:
        package = files("word_madness_bot.resources.glyphs")
        self._templates = {
            character: _normalize_mask(
                Image.open(io.BytesIO(package.joinpath(f"{character}.png").read_bytes()))
            )
            for character in string.ascii_uppercase
        }

    def recognize(self, image: Image.Image) -> OcrResult:
        """Return the strongest normalized correlation across uppercase templates."""
        source = _normalize_mask(image)
        scores = {
            character: float(cv2.matchTemplate(source, template, cv2.TM_CCOEFF_NORMED)[0, 0])
            for character, template in self._templates.items()
        }
        character, score = max(scores.items(), key=lambda item: (item[1], item[0]))
        confidence = min(1.0, max(0.0, (score + 1.0) / 2.0))
        return OcrResult(character, confidence)


class WheelLetterRecognizer:
    """Crop, normalize, recognize, and persist every indexed wheel glyph."""

    def __init__(
        self,
        engine: OcrEngine | None = None,
        *,
        clock: Clock = time.monotonic,
    ) -> None:
        self.engine = engine or OpenCvTemplateOcrEngine()
        self.clock = clock

    def recognize(
        self,
        capture: ScreenCapture,
        geometry: LetterWheelGeometry,
        debug_directory: Path,
    ) -> WheelLetterRecognition:
        """Recognize all geometry positions and save normalized crops plus JSON."""
        try:
            source = Image.open(io.BytesIO(capture.data)).convert("L")
        except (OSError, ValueError) as error:
            raise OcrError("Unable to decode screenshot for letter recognition") from error

        letters_directory = debug_directory / "letters"
        json_path = debug_directory / "letters.json"
        try:
            letters_directory.mkdir(parents=True, exist_ok=True)
            for stale in letters_directory.glob("letter-*.png"):
                stale.unlink()
        except OSError as error:
            raise OcrError("Unable to prepare letter debug directory") from error

        side = max(32, round(geometry.radius * 0.46))
        recognized: list[RecognizedLetter] = []
        for position in geometry.letters:
            crop = _crop_square(source, position.point.x, position.point.y, side)
            normalized = _normalized_crop(crop)
            crop_path = letters_directory / f"letter-{position.index}.png"
            started = self.clock()
            result = recognize(self.engine, normalized)
            elapsed = self.clock() - started
            character = result.text.upper()
            if len(character) != 1 or character not in string.ascii_uppercase:
                raise OcrError("OCR engine did not return one uppercase letter")
            try:
                normalized.save(crop_path, format="PNG")
            except OSError as error:
                raise OcrError(f"Unable to save letter crop: {crop_path}") from error
            recognized.append(
                RecognizedLetter(
                    index=position.index,
                    character=character,
                    confidence=result.confidence,
                    elapsed_seconds=elapsed,
                    crop_path=crop_path,
                )
            )

        output = WheelLetterRecognition(tuple(recognized))
        try:
            json_path.write_text(
                json.dumps(output.to_dict(), indent=2, sort_keys=True) + "\n",
                encoding="utf-8",
            )
        except OSError as error:
            raise OcrError(f"Unable to save letter recognition JSON: {json_path}") from error
        return output


def _crop_square(image: Image.Image, center_x: int, center_y: int, side: int) -> Image.Image:
    half = side // 2
    left = center_x - half
    top = center_y - half
    right = left + side
    bottom = top + side
    output = Image.new("L", (side, side), 255)
    source_box = (
        max(0, left),
        max(0, top),
        min(image.width, right),
        min(image.height, bottom),
    )
    if source_box[0] >= source_box[2] or source_box[1] >= source_box[3]:
        raise OcrError("Letter position lies outside the screenshot")
    patch = image.crop(source_box)
    output.paste(patch, (source_box[0] - left, source_box[1] - top))
    return output


def _normalized_crop(image: Image.Image) -> Image.Image:
    mask = _normalize_mask(image)
    return Image.fromarray(255 - mask, mode="L")


def _normalize_mask(image: Image.Image) -> Any:
    gray = np.asarray(image.convert("L"), dtype=np.uint8)
    _, binary = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU)
    contours, _ = cv2.findContours(binary, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    contours = [contour for contour in contours if cv2.contourArea(contour) > 4]
    if not contours:
        raise OcrError("No glyph foreground was detected")
    contour = max(contours, key=cv2.contourArea)
    left, top, width, height = cv2.boundingRect(contour)
    glyph = binary[top : top + height, left : left + width]
    scale = 48 / max(width, height)
    resized = cv2.resize(
        glyph,
        (max(1, round(width * scale)), max(1, round(height * scale))),
        interpolation=cv2.INTER_AREA,
    )
    normalized = np.zeros((64, 64), dtype=np.uint8)
    offset_y = (64 - resized.shape[0]) // 2
    offset_x = (64 - resized.shape[1]) // 2
    normalized[
        offset_y : offset_y + resized.shape[0],
        offset_x : offset_x + resized.shape[1],
    ] = resized
    return normalized
