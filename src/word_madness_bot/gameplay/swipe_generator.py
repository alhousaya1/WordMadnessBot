"""Pure, resolution-independent swipe path planning."""

from __future__ import annotations

import itertools
import math
import unicodedata

from word_madness_bot.domain.errors import SwipePlanningError
from word_madness_bot.domain.geometry import NormalizedPoint, ScreenSize
from word_madness_bot.domain.models import LetterPosition, NormalizedSwipePath, SwipePath


class SwipePathPlanner:
    """Map words to deterministic, smoothed paths without performing input."""

    def __init__(
        self,
        *,
        duration_per_letter_ms: int | None = None,
        minimum_duration_ms: int | None = None,
        maximum_step: float = 0.08,
    ) -> None:
        if (duration_per_letter_ms is None) != (minimum_duration_ms is None):
            raise ValueError("Custom swipe timing requires both duration values")
        if (
            duration_per_letter_ms is not None
            and minimum_duration_ms is not None
            and (duration_per_letter_ms <= 0 or minimum_duration_ms <= 0)
        ):
            raise ValueError("Swipe durations must be positive")
        if not 0 < maximum_step <= 1:
            raise ValueError("maximum_step must be between zero and one")
        self.duration_per_letter_ms = duration_per_letter_ms
        self.minimum_duration_ms = minimum_duration_ms
        self.maximum_step = maximum_step

    def plan_normalized(
        self,
        letters: tuple[LetterPosition, ...],
        word: str,
        *,
        interpolate: bool = True,
    ) -> NormalizedSwipePath:
        """Plan a normalized path for a word using each wheel position once."""
        normalized_word = unicodedata.normalize("NFC", word.strip()).upper()
        if len(normalized_word) < 2:
            raise SwipePlanningError("A swipe word requires at least two letters")
        indices = _map_letters(letters, normalized_word)
        control_points = tuple(letters[index].position for index in indices)
        points = (
            _interpolate(control_points, self.maximum_step)
            if interpolate
            else control_points
        )
        duration = self._duration(len(normalized_word))
        return NormalizedSwipePath(points, duration, normalized_word)

    def plan(
        self,
        letters: tuple[LetterPosition, ...],
        word: str,
        screen: ScreenSize,
        *,
        interpolate: bool = True,
    ) -> SwipePath:
        """Plan and convert a word path to bounded device pixels."""
        path = self.plan_normalized(letters, word, interpolate=interpolate)
        return SwipePath(
            tuple(point.to_pixels(screen) for point in path.points),
            path.duration_ms,
        )

    def _duration(self, length: int) -> int:
        if self.duration_per_letter_ms is not None and self.minimum_duration_ms is not None:
            return max(self.minimum_duration_ms, length * self.duration_per_letter_ms)
        if length <= 2:
            return 120
        if length == 3:
            return 150
        if length == 4:
            return 180
        return 220 + (length - 5) * 40


def _map_letters(letters: tuple[LetterPosition, ...], word: str) -> tuple[int, ...]:
    if not letters:
        raise SwipePlanningError("No detected letters are available")

    def search(offset: int, used: frozenset[int]) -> tuple[int, ...] | None:
        if offset == len(word):
            return ()
        for index, letter in enumerate(letters):
            if index not in used and letter.character == word[offset]:
                remainder = search(offset + 1, used | {index})
                if remainder is not None:
                    return (index, *remainder)
        return None

    result = search(0, frozenset())
    if result is None:
        raise SwipePlanningError(f"Word cannot be mapped to detected letters: {word}")
    return result


def _interpolate(
    points: tuple[NormalizedPoint, ...], maximum_step: float
) -> tuple[NormalizedPoint, ...]:
    output = [points[0]]
    for start, end in itertools.pairwise(points):
        distance = math.hypot(end.x - start.x, end.y - start.y)
        segments = max(1, math.ceil(distance / maximum_step))
        for step in range(1, segments + 1):
            fraction = step / segments
            output.append(
                NormalizedPoint(
                    start.x + (end.x - start.x) * fraction, start.y + (end.y - start.y) * fraction
                )
            )
    return tuple(output)
