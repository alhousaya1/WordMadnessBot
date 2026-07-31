"""Resolution-independent detection of the low-saturation letter wheel."""

import logging
import math
from collections import deque

import numpy as np

from word_madness_bot.domain.models import CircleDetection, Point, ScreenGeometry
from word_madness_bot.vision.geometry import NormalizedBox, scale_length, to_pixel_box
from word_madness_bot.vision.preprocessing import ImageArray, crop, resize

_LOGGER = logging.getLogger(__name__)
_DEFAULT_SEARCH_REGION = NormalizedBox(0.08, 0.55, 0.92, 0.98)


class CircleDetector:
    """Detect a circular wheel using scaled color and connected-component evidence."""

    def __init__(
        self,
        search_region: NormalizedBox = _DEFAULT_SEARCH_REGION,
        *,
        minimum_radius_fraction: float = 0.18,
        maximum_radius_fraction: float = 0.45,
        analysis_max_dimension: int = 640,
    ) -> None:
        if minimum_radius_fraction <= 0 or maximum_radius_fraction <= minimum_radius_fraction:
            raise ValueError("circle radius fractions are invalid")
        self._search_region = search_region
        self._minimum_radius_fraction = minimum_radius_fraction
        self._maximum_radius_fraction = maximum_radius_fraction
        self._analysis_max_dimension = analysis_max_dimension

    def detect(self, image: ImageArray, geometry: ScreenGeometry) -> CircleDetection | None:
        """Return the most circle-like wheel candidate with a normalized confidence."""

        region = to_pixel_box(self._search_region, geometry)
        search = crop(image, region)
        original_height, original_width = search.shape[:2]
        reduction = min(1.0, self._analysis_max_dimension / max(original_width, original_height))
        analysis_width = max(1, round(original_width * reduction))
        analysis_height = max(1, round(original_height * reduction))
        analysis = resize(search, analysis_width, analysis_height)
        channels = analysis.astype(np.int16)
        saturation = channels.max(axis=2) - channels.min(axis=2)
        brightness = channels.mean(axis=2)
        mask = (saturation <= 52) & (brightness >= 118)

        components = self._connected_components(mask)
        if not components:
            _LOGGER.debug("No wheel-colored components found")
            return None

        minimum_radius = scale_length(self._minimum_radius_fraction, geometry) * reduction
        maximum_radius = scale_length(self._maximum_radius_fraction, geometry) * reduction
        best: tuple[float, tuple[int, int, int, int, int]] | None = None
        for component in components:
            count, left, top, right, bottom = component
            width = right - left + 1
            height = bottom - top + 1
            radius = (width + height) / 4.0
            if not minimum_radius <= radius <= maximum_radius:
                continue
            aspect_score = min(width, height) / max(width, height)
            fill_ratio = count / (math.pi * radius * radius)
            fill_score = max(0.0, 1.0 - abs(1.0 - fill_ratio))
            boundary_penalty = 0.65 if left == 0 or right == analysis_width - 1 else 1.0
            confidence = max(0.0, min(1.0, 0.65 * aspect_score + 0.35 * fill_score))
            rank = confidence * count * boundary_penalty
            if best is None or rank > best[0]:
                best = (rank, component)
        if best is None:
            _LOGGER.debug("No component satisfied scaled wheel-radius constraints")
            return None

        count, left, top, right, bottom = best[1]
        width = right - left + 1
        height = bottom - top + 1
        radius_analysis = (width + height) / 4.0
        aspect_score = min(width, height) / max(width, height)
        fill_ratio = count / (math.pi * radius_analysis * radius_analysis)
        fill_score = max(0.0, 1.0 - abs(1.0 - fill_ratio))
        confidence = max(0.0, min(1.0, 0.65 * aspect_score + 0.35 * fill_score))
        center_x = region.left + round(((left + right) / 2.0) / reduction)
        center_y = region.top + round(((top + bottom) / 2.0) / reduction)
        radius = max(1, round(radius_analysis / reduction))
        detection = CircleDetection(Point(center_x, center_y), radius, confidence)
        _LOGGER.debug(
            "Wheel circle candidate center=(%d,%d) radius=%d confidence=%.3f",
            center_x,
            center_y,
            radius,
            confidence,
        )
        return detection

    @staticmethod
    def _connected_components(
        mask: np.ndarray[tuple[int, int], np.dtype[np.bool_]],
    ) -> tuple[tuple[int, int, int, int, int], ...]:
        height, width = mask.shape
        visited = np.zeros_like(mask, dtype=np.bool_)
        components: list[tuple[int, int, int, int, int]] = []
        for start_y, start_x in zip(*np.nonzero(mask & ~visited), strict=True):
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
            if count >= 16:
                components.append((count, left, top, right, bottom))
        return tuple(components)
