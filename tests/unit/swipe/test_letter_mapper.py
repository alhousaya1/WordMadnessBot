"""Unit tests for deterministic word-to-letter coordinate mapping."""

import pytest

from word_madness_bot.domain.errors import SwipePlanningError
from word_madness_bot.domain.models import NormalizedPoint, SwipeLetter
from word_madness_bot.swipe.letter_mapper import LetterMapper


def _letter(character: str, x: float, y: float) -> SwipeLetter:
    return SwipeLetter(character, NormalizedPoint(x, y))


def test_duplicate_letters_are_consumed_in_coordinate_order() -> None:
    """Repeated word characters map to distinct duplicate wheel positions deterministically."""

    letters = (
        _letter("A", 0.8, 0.7),
        _letter("B", 0.5, 0.2),
        _letter("A", 0.2, 0.3),
    )

    points = LetterMapper().map_word("aba", letters)

    assert points == (
        NormalizedPoint(0.2, 0.3),
        NormalizedPoint(0.5, 0.2),
        NormalizedPoint(0.8, 0.7),
    )


def test_input_order_does_not_change_duplicate_mapping() -> None:
    """Equivalent detected wheels produce identical paths regardless of sequence order."""

    letters = (
        _letter("O", 0.8, 0.7),
        _letter("O", 0.2, 0.3),
        _letter("T", 0.5, 0.2),
        _letter("L", 0.5, 0.8),
    )
    mapper = LetterMapper()

    assert mapper.map_word("TOOL", letters) == mapper.map_word("TOOL", tuple(reversed(letters)))


def test_impossible_word_reports_missing_occurrences() -> None:
    """A letter cannot be reused more often than it appears on the detected wheel."""

    with pytest.raises(SwipePlanningError, match=r"missing letter occurrences: O:1"):
        LetterMapper().map_word(
            "TOO",
            (_letter("T", 0.3, 0.3), _letter("O", 0.7, 0.7)),
        )


@pytest.mark.parametrize("word", ["", "A", "A-", "ÉT"])
def test_invalid_target_word_is_rejected(word: str) -> None:
    """Only multi-letter ASCII words are accepted by path planning."""

    with pytest.raises(SwipePlanningError, match="target word"):
        LetterMapper().map_word(word, (_letter("A", 0.5, 0.5),))
