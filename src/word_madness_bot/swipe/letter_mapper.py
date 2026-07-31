"""Deterministic mapping from word characters to normalized wheel coordinates."""

import logging
from collections import Counter
from collections.abc import Sequence

from word_madness_bot.domain.errors import SwipePlanningError
from word_madness_bot.domain.models import NormalizedPoint, SwipeLetter

_LOGGER = logging.getLogger(__name__)


class LetterMapper:
    """Map each word occurrence to one distinct matching wheel letter."""

    def map_word(
        self,
        word: str,
        letters: Sequence[SwipeLetter],
    ) -> tuple[NormalizedPoint, ...]:
        """Return deterministic coordinates while consuming duplicate letters once each."""

        normalized_word = word.strip().upper()
        if (
            len(normalized_word) < 2
            or not normalized_word.isascii()
            or not normalized_word.isalpha()
        ):
            raise SwipePlanningError("target word must contain at least two ASCII letters")
        if not letters:
            raise SwipePlanningError("detected wheel letters cannot be empty")

        positions: dict[str, list[NormalizedPoint]] = {}
        for letter in letters:
            positions.setdefault(letter.character, []).append(letter.coordinate)
        for coordinates in positions.values():
            coordinates.sort(key=lambda point: (point.y, point.x))

        required = Counter(normalized_word)
        available = {character: len(coordinates) for character, coordinates in positions.items()}
        shortages = {
            character: count - available.get(character, 0)
            for character, count in sorted(required.items())
            if count > available.get(character, 0)
        }
        if shortages:
            details = ", ".join(f"{character}:{count}" for character, count in shortages.items())
            raise SwipePlanningError(
                f"word cannot be mapped; missing letter occurrences: {details}"
            )

        consumed: Counter[str] = Counter()
        path: list[NormalizedPoint] = []
        for character in normalized_word:
            occurrence = consumed[character]
            path.append(positions[character][occurrence])
            consumed[character] += 1
        _LOGGER.debug(
            "Mapped target word to wheel coordinates",
            extra={
                "event": "swipe_letters_mapped",
                "word_length": len(normalized_word),
                "path_anchor_count": len(path),
            },
        )
        return tuple(path)
