"""Unit tests for deterministic swipe path planning."""

from itertools import pairwise

import pytest

from word_madness_bot.domain.errors import SwipePlanningError
from word_madness_bot.domain.geometry import NormalizedPoint, ScreenSize
from word_madness_bot.domain.models import LetterPosition
from word_madness_bot.gameplay.swipe_generator import SwipePathPlanner


def wheel() -> tuple[LetterPosition, ...]:
    return (
        LetterPosition("A", NormalizedPoint(0.2, 0.5)),
        LetterPosition("B", NormalizedPoint(0.5, 0.2)),
        LetterPosition("A", NormalizedPoint(0.8, 0.5)),
        LetterPosition("C", NormalizedPoint(0.5, 0.8)),
    )


def test_repeated_letters_use_distinct_positions_deterministically() -> None:
    planner = SwipePathPlanner(maximum_step=1)
    path = planner.plan_normalized(wheel(), "ABA")
    assert path.points == (
        NormalizedPoint(0.2, 0.5),
        NormalizedPoint(0.5, 0.2),
        NormalizedPoint(0.8, 0.5),
    )
    assert planner.plan_normalized(wheel(), "ABA") == path


@pytest.mark.parametrize("word", ["ZOO", "AAA", "", "A"])
def test_impossible_or_invalid_words_are_typed(word: str) -> None:
    with pytest.raises(SwipePlanningError):
        SwipePathPlanner().plan_normalized(wheel(), word)


def test_interpolation_limits_segment_length_and_preserves_endpoints() -> None:
    path = SwipePathPlanner(maximum_step=0.1).plan_normalized(wheel(), "AC")
    assert path.points[0] == NormalizedPoint(0.2, 0.5)
    assert path.points[-1] == NormalizedPoint(0.5, 0.8)
    assert all(
        ((b.x - a.x) ** 2 + (b.y - a.y) ** 2) ** 0.5 <= 0.100001 for a, b in pairwise(path.points)
    )


def test_pixel_path_is_resolution_independent_and_bounded() -> None:
    planner = SwipePathPlanner(maximum_step=1)
    small = planner.plan(wheel(), "AC", ScreenSize(100, 200))
    large = planner.plan(wheel(), "AC", ScreenSize(1000, 2000))
    assert small.points[0].is_within(ScreenSize(100, 200))
    assert large.points[0].is_within(ScreenSize(1000, 2000))
    assert large.points[0].x > small.points[0].x


def test_segment_duration_is_configurable() -> None:
    assert (
        SwipePathPlanner(segment_duration_ms=200)
        .plan_normalized(wheel(), "ABA", interpolate=False)
        .duration_ms
        == 400
    )


def test_planner_has_no_adb_dependency() -> None:
    import word_madness_bot.gameplay.swipe_generator as module

    assert not any("adb" in name.lower() for name in module.__dict__)


def test_exact_control_point_mode_does_not_interpolate() -> None:
    path = SwipePathPlanner().plan_normalized(wheel(), "ABA", interpolate=False)
    assert path.points == (
        NormalizedPoint(0.2, 0.5),
        NormalizedPoint(0.5, 0.2),
        NormalizedPoint(0.8, 0.5),
    )


@pytest.mark.parametrize(
    ("word", "expected_duration"),
    [("ABC", 400), ("ABCD", 600), ("ABCDE", 800), ("ABCDEF", 1000), ("ABCDEFG", 1200)],
)
def test_duration_is_200_ms_per_letter_transition(word: str, expected_duration: int) -> None:
    letters = tuple(
        LetterPosition(character, NormalizedPoint((index + 1) / 8, 0.5))
        for index, character in enumerate("ABCDEFG")
    )
    assert (
        SwipePathPlanner().plan_normalized(letters, word, interpolate=False).duration_ms
        == expected_duration
    )
