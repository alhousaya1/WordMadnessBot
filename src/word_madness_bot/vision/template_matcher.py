"""Resolution-independent normalized template matching."""

import logging

import numpy as np

from word_madness_bot.domain.models import BoundingBox, TemplateMatch
from word_madness_bot.vision.preprocessing import ImageArray, crop, grayscale

_LOGGER = logging.getLogger(__name__)


class TemplateMatcher:
    """Locate a template inside an explicitly scaled search region."""

    def match(
        self,
        image: ImageArray,
        template: ImageArray,
        search_region: BoundingBox,
        *,
        minimum_confidence: float = 0.8,
    ) -> TemplateMatch | None:
        """Return the highest normalized match at or above the confidence threshold."""

        if not 0.0 <= minimum_confidence <= 1.0:
            raise ValueError("minimum confidence must be between 0.0 and 1.0")
        source = grayscale(crop(image, search_region)).astype(np.float32)
        target = grayscale(template).astype(np.float32)
        target_height, target_width = target.shape
        source_height, source_width = source.shape
        if target_height > source_height or target_width > source_width:
            return None

        target_centered = target - float(target.mean())
        target_norm = float(np.linalg.norm(target_centered))
        best_score = -1.0
        best_position = (0, 0)
        step = max(1, min(target_width, target_height) // 12)
        x_positions = self._positions(source_width - target_width, step)
        y_positions = self._positions(source_height - target_height, step)
        for y in y_positions:
            for x in x_positions:
                candidate = source[y : y + target_height, x : x + target_width]
                score = self._confidence(candidate, target, target_centered, target_norm)
                if score > best_score:
                    best_score = score
                    best_position = (x, y)

        coarse_x, coarse_y = best_position
        for y in range(
            max(0, coarse_y - step), min(source_height - target_height, coarse_y + step) + 1
        ):
            for x in range(
                max(0, coarse_x - step),
                min(source_width - target_width, coarse_x + step) + 1,
            ):
                candidate = source[y : y + target_height, x : x + target_width]
                score = self._confidence(candidate, target, target_centered, target_norm)
                if score > best_score:
                    best_score = score
                    best_position = (x, y)

        if best_score < minimum_confidence:
            _LOGGER.debug("Template not found; best confidence %.3f", best_score)
            return None
        x, y = best_position
        match_region = BoundingBox(
            left=search_region.left + x,
            top=search_region.top + y,
            right=search_region.left + x + target_width,
            bottom=search_region.top + y + target_height,
        )
        return TemplateMatch(region=match_region, confidence=best_score)

    @staticmethod
    def _positions(limit: int, step: int) -> tuple[int, ...]:
        positions = list(range(0, limit + 1, step))
        if positions[-1] != limit:
            positions.append(limit)
        return tuple(positions)

    @staticmethod
    def _confidence(
        candidate: np.ndarray[tuple[int, int], np.dtype[np.float32]],
        target: np.ndarray[tuple[int, int], np.dtype[np.float32]],
        target_centered: np.ndarray[tuple[int, int], np.dtype[np.float32]],
        target_norm: float,
    ) -> float:
        if target_norm < 1e-6:
            difference = float(np.mean(np.abs(candidate - target)))
            return max(0.0, 1.0 - difference / 255.0)
        candidate_centered = candidate - float(candidate.mean())
        denominator = float(np.linalg.norm(candidate_centered)) * target_norm
        if denominator < 1e-6:
            return 0.0
        correlation = float(np.sum(candidate_centered * target_centered) / denominator)
        return max(0.0, min(1.0, correlation))
