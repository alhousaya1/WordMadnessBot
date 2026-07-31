"""Integration scenarios for mapping, smoothing, and validation composition."""

import pytest

from word_madness_bot.config import Settings
from word_madness_bot.domain.errors import SwipePlanningError
from word_madness_bot.domain.models import NormalizedPoint, SwipeLetter, SwipePath
from word_madness_bot.swipe.path_planner import PathPlanner


def _letter(character: str, x: float, y: float) -> SwipeLetter:
    return SwipeLetter(character, NormalizedPoint(x, y))


def _planner() -> PathPlanner:
    return PathPlanner.from_settings(
        Settings(
            swipe_interpolation_points=5,
            swipe_smoothing_strength=0.6,
            swipe_maximum_step_fraction=0.2,
        )
    )


def test_repeated_letter_word_uses_distinct_duplicate_wheel_letters() -> None:
    """A repeated-letter word traverses each matching wheel coordinate once."""

    letters = (
        _letter("T", 0.5, 0.2),
        _letter("O", 0.8, 0.5),
        _letter("O", 0.5, 0.8),
        _letter("L", 0.2, 0.5),
    )

    path = _planner().generate("TOOL", letters)

    assert isinstance(path, SwipePath)
    assert NormalizedPoint(0.8, 0.5) in path.points
    assert NormalizedPoint(0.5, 0.8) in path.points
    assert all(0.0 <= point.x <= 1.0 and 0.0 <= point.y <= 1.0 for point in path.points)


def test_duplicate_wheel_letter_selection_is_deterministic() -> None:
    """Duplicate positions select in normalized coordinate order, not detection order."""

    letters = (
        _letter("A", 0.8, 0.7),
        _letter("B", 0.5, 0.2),
        _letter("A", 0.2, 0.3),
    )

    assert _planner().generate("ABA", letters) == _planner().generate(
        "ABA", tuple(reversed(letters))
    )


def test_impossible_repeated_letter_word_fails_before_path_creation() -> None:
    """Missing duplicate occurrences produce a planning error, never a partial path."""

    with pytest.raises(SwipePlanningError, match="O:1"):
        _planner().generate(
            "TOO",
            (_letter("T", 0.3, 0.3), _letter("O", 0.7, 0.7)),
        )


def test_path_validation_rejects_duplicate_coordinates() -> None:
    """Distinct detected letters at the same coordinate cannot yield a stationary segment."""

    coordinate = NormalizedPoint(0.5, 0.5)
    with pytest.raises(SwipePlanningError, match="stationary"):
        _planner().generate(
            "AB",
            (SwipeLetter("A", coordinate), SwipeLetter("B", coordinate)),
        )
