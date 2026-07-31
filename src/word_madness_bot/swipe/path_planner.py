"""Composition of mapping, interpolation, validation, and typed path creation."""

import logging
from collections.abc import Sequence

from word_madness_bot.config.settings import Settings
from word_madness_bot.domain.models import SwipeLetter, SwipePath
from word_madness_bot.swipe.letter_mapper import LetterMapper
from word_madness_bot.swipe.path_smoother import PathSmoother
from word_madness_bot.swipe.path_validator import PathValidator

_LOGGER = logging.getLogger(__name__)


class PathPlanner:
    """Generate deterministic validated paths without executing device input."""

    def __init__(
        self,
        letter_mapper: LetterMapper,
        path_smoother: PathSmoother,
        path_validator: PathValidator,
        *,
        interpolation_points: int = 4,
        smoothing_strength: float = 0.5,
        duration_per_letter_ms: int = 120,
    ) -> None:
        if interpolation_points < 0:
            raise ValueError("interpolation point count cannot be negative")
        if not 0.0 <= smoothing_strength <= 1.0:
            raise ValueError("smoothing strength must be between zero and one")
        if duration_per_letter_ms <= 0:
            raise ValueError("duration per letter must be positive")
        self._letter_mapper = letter_mapper
        self._path_smoother = path_smoother
        self._path_validator = path_validator
        self._interpolation_points = interpolation_points
        self._smoothing_strength = smoothing_strength
        self._duration_per_letter_ms = duration_per_letter_ms

    @classmethod
    def from_settings(cls, settings: Settings) -> "PathPlanner":
        """Construct a planner whose complete policy comes from validated settings."""

        return cls(
            LetterMapper(),
            PathSmoother(),
            PathValidator(settings.swipe_maximum_step_fraction),
            interpolation_points=settings.swipe_interpolation_points,
            smoothing_strength=settings.swipe_smoothing_strength,
            duration_per_letter_ms=settings.swipe_duration_per_letter_ms,
        )

    def generate(self, word: str, letters: Sequence[SwipeLetter]) -> SwipePath:
        """Generate, validate, log, and return one resolution-independent path."""

        anchors = self._letter_mapper.map_word(word, letters)
        points = self._path_smoother.smooth(
            anchors,
            interpolation_points=self._interpolation_points,
            smoothing_strength=self._smoothing_strength,
        )
        path = SwipePath(
            points=points,
            duration_ms=len(word.strip()) * self._duration_per_letter_ms,
        )
        validated = self._path_validator.validate(path)
        _LOGGER.debug(
            "Generated validated swipe path",
            extra={
                "event": "swipe_path_generated",
                "word_length": len(word.strip()),
                "anchor_count": len(anchors),
                "point_count": len(validated.points),
                "duration_ms": validated.duration_ms,
            },
        )
        return validated
