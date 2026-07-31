"""Extract and recognize letters positioned inside a detected wheel."""

import logging
import math
from collections import deque

import numpy as np

from word_madness_bot.domain.models import CircleDetection, DetectedLetter, Point
from word_madness_bot.vision.ocr import OcrEngine
from word_madness_bot.vision.preprocessing import ImageArray, grayscale, resize, threshold

_LOGGER = logging.getLogger(__name__)


class LetterExtractor:
    """Find dark glyph components and recognize them through an injected OCR engine."""

    def __init__(self, ocr_engine: OcrEngine, *, minimum_ocr_confidence: float = 0.35) -> None:
        if not 0.0 <= minimum_ocr_confidence <= 1.0:
            raise ValueError("minimum OCR confidence must be between 0.0 and 1.0")
        self._ocr_engine = ocr_engine
        self._minimum_ocr_confidence = minimum_ocr_confidence

    def extract(
        self,
        image: ImageArray,
        circle: CircleDetection,
    ) -> tuple[DetectedLetter, ...]:
        """Return recognized letters ordered clockwise from the top of the wheel."""

        height, width = image.shape[:2]
        radius = circle.radius
        left = max(0, circle.center.x - radius)
        top = max(0, circle.center.y - radius)
        right = min(width, circle.center.x + radius + 1)
        bottom = min(height, circle.center.y + radius + 1)
        wheel_image = image[top:bottom, left:right]
        gray = grayscale(wheel_image)
        local_center_x = circle.center.x - left
        local_center_y = circle.center.y - top
        yy, xx = np.ogrid[: gray.shape[0], : gray.shape[1]]
        inside = (xx - local_center_x) ** 2 + (yy - local_center_y) ** 2 <= (radius * 0.82) ** 2
        dark_mask = (gray <= 82) & inside
        components = self._components(dark_mask)

        detected: list[DetectedLetter] = []
        for count, component_left, component_top, component_right, component_bottom in components:
            component_width = component_right - component_left + 1
            component_height = component_bottom - component_top + 1
            if not 0.03 * radius <= component_width <= 0.36 * radius:
                continue
            if not 0.10 * radius <= component_height <= 0.40 * radius:
                continue
            if count < 0.0015 * radius * radius:
                continue
            padding = max(2, round(radius * 0.035))
            glyph_left = max(0, component_left - padding)
            glyph_top = max(0, component_top - padding)
            glyph_right = min(gray.shape[1], component_right + padding + 1)
            glyph_bottom = min(gray.shape[0], component_bottom + padding + 1)
            glyph = gray[glyph_top:glyph_bottom, glyph_left:glyph_right]
            glyph = resize(glyph, max(40, glyph.shape[1] * 3), max(40, glyph.shape[0] * 3))
            glyph = threshold(glyph, 128)
            result = self._ocr_engine.recognize(glyph, whitelist="ABCDEFGHIJKLMNOPQRSTUVWXYZ")
            if result is None or result.confidence < self._minimum_ocr_confidence:
                continue
            characters = [character for character in result.text.upper() if character.isalpha()]
            if len(characters) != 1 or not characters[0].isascii():
                continue
            center_x = left + round((component_left + component_right) / 2)
            center_y = top + round((component_top + component_bottom) / 2)
            size_score = max(0.0, 1.0 - abs(component_height / radius - 0.25))
            confidence = min(1.0, result.confidence * 0.85 + size_score * 0.15)
            detected.append(
                DetectedLetter(
                    character=characters[0],
                    center=Point(center_x, center_y),
                    confidence=confidence,
                )
            )

        detected.sort(
            key=lambda letter: (
                math.atan2(
                    letter.center.x - circle.center.x,
                    -(letter.center.y - circle.center.y),
                )
                % (2 * math.pi)
            )
        )
        _LOGGER.debug("Recognized %d wheel letters", len(detected))
        return tuple(detected)

    @staticmethod
    def _components(
        mask: np.ndarray[tuple[int, int], np.dtype[np.bool_]],
    ) -> tuple[tuple[int, int, int, int, int], ...]:
        height, width = mask.shape
        visited = np.zeros_like(mask, dtype=np.bool_)
        components: list[tuple[int, int, int, int, int]] = []
        for start_y, start_x in zip(*np.nonzero(mask), strict=True):
            if visited[start_y, start_x]:
                continue
            queue: deque[tuple[int, int]] = deque([(int(start_x), int(start_y))])
            visited[start_y, start_x] = True
            count = 0
            left = right = int(start_x)
            top = bottom = int(start_y)
            while queue:
                x, y = queue.popleft()
                count += 1
                left, right = min(left, x), max(right, x)
                top, bottom = min(top, y), max(bottom, y)
                for next_x, next_y in ((x - 1, y), (x + 1, y), (x, y - 1), (x, y + 1)):
                    if (
                        0 <= next_x < width
                        and 0 <= next_y < height
                        and mask[next_y, next_x]
                        and not visited[next_y, next_x]
                    ):
                        visited[next_y, next_x] = True
                        queue.append((next_x, next_y))
            components.append((count, left, top, right, bottom))
        return tuple(components)
