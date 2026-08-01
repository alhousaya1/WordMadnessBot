"""Resolution-independent recognition of the level number in a level screenshot."""

from __future__ import annotations

import io
import itertools
from dataclasses import dataclass
from importlib import import_module
from importlib.resources import files
from typing import Any, Protocol

from PIL import Image

from word_madness_bot.domain.errors import OcrError
from word_madness_bot.domain.models import ScreenCapture

cv2: Any = import_module("cv2")
np: Any = import_module("numpy")


class LevelNumberRecognitionPort(Protocol):
    """Runtime boundary for extracting a level identifier from a screenshot."""

    def recognize(self, capture: ScreenCapture) -> int: ...


@dataclass(frozen=True, slots=True)
class _Glyph:
    left: int
    width: int
    height: int
    mask: Any

    @property
    def right(self) -> int:
        return self.left + self.width


class LevelNumberRecognizer:
    """Recognize the numeric suffix of the centered ``Level N`` title."""

    def __init__(self, *, minimum_confidence: float = 0.72) -> None:
        if not 0.0 <= minimum_confidence <= 1.0:
            raise ValueError("minimum_confidence must be between zero and one")
        package = files("word_madness_bot.resources.digits")
        self._templates = {
            digit: _normalize_mask(
                Image.open(io.BytesIO(package.joinpath(f"{digit}.png").read_bytes()))
            )
            for digit in "0123456789"
        }
        self.minimum_confidence = minimum_confidence

    def recognize(self, capture: ScreenCapture) -> int:
        """Return the positive level number displayed near the top center."""
        try:
            image = Image.open(io.BytesIO(capture.data)).convert("L")
        except (OSError, ValueError) as error:
            raise OcrError("Unable to decode screenshot for level recognition") from error
        gray = np.asarray(image, dtype=np.uint8)
        height, width = gray.shape
        top, bottom = round(height * 0.035), round(height * 0.105)
        left, right = round(width * 0.35), round(width * 0.65)
        roi = gray[top:bottom, left:right]
        _, binary = cv2.threshold(roi, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
        contours, _ = cv2.findContours(binary, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        glyphs: list[_Glyph] = []
        for contour in contours:
            x, y, glyph_width, glyph_height = cv2.boundingRect(contour)
            if not 0.12 * roi.shape[0] <= glyph_height <= 0.55 * roi.shape[0]:
                continue
            if glyph_width < 2 or glyph_width > glyph_height * 1.25:
                continue
            glyphs.append(
                _Glyph(
                    x,
                    glyph_width,
                    glyph_height,
                    binary[y : y + glyph_height, x : x + glyph_width],
                )
            )
        glyphs.sort(key=lambda item: item.left)
        numeric = _numeric_suffix(glyphs)
        if not numeric:
            raise OcrError("No level-number glyphs were detected")
        output: list[str] = []
        for glyph in numeric:
            source = _normalize_array(glyph.mask)
            scores = {
                digit: float(cv2.matchTemplate(source, template, cv2.TM_CCOEFF_NORMED)[0, 0])
                for digit, template in self._templates.items()
            }
            digit, score = max(scores.items(), key=lambda item: (item[1], item[0]))
            confidence = min(1.0, max(0.0, (score + 1.0) / 2.0))
            if confidence < self.minimum_confidence:
                raise OcrError(f"Level digit confidence is too low: {confidence:.3f}")
            output.append(digit)
        number = int("".join(output))
        if number <= 0:
            raise OcrError("Detected level number must be positive")
        return number


def _numeric_suffix(glyphs: list[_Glyph]) -> list[_Glyph]:
    if len(glyphs) < 2:
        return []
    gaps = [right.left - left.right for left, right in itertools.pairwise(glyphs)]
    split = max(range(len(gaps)), key=gaps.__getitem__)
    suffix = glyphs[split + 1 :]
    return suffix if gaps[split] > max(3, round(glyphs[split].height * 0.25)) else []


def _normalize_mask(image: Image.Image) -> Any:
    gray = np.asarray(image.convert("L"), dtype=np.uint8)
    _, mask = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
    return _normalize_array(mask)


def _normalize_array(mask: Any) -> Any:
    contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    if not contours:
        raise OcrError("No digit foreground was detected")
    left, top, width, height = cv2.boundingRect(max(contours, key=cv2.contourArea))
    glyph = mask[top : top + height, left : left + width]
    scale = 48 / max(width, height)
    resized = cv2.resize(
        glyph,
        (max(1, round(width * scale)), max(1, round(height * scale))),
        interpolation=cv2.INTER_AREA,
    )
    normalized = np.zeros((64, 64), dtype=np.uint8)
    y = (64 - resized.shape[0]) // 2
    x = (64 - resized.shape[1]) // 2
    normalized[y : y + resized.shape[0], x : x + resized.shape[1]] = resized
    return normalized
