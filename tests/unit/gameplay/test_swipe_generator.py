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
        ((b.x - a.x) ** 2 + (b.y - a.y) ** 2) ** 0.5 <= 0.100001
        for a, b in pairwise(path.points)
    )


def test_pixel_path_is_resolution_independent_and_bounded() -> None:
    planner = SwipePathPlanner(maximum_step=1)
    small = planner.plan(wheel(), "AC", ScreenSize(100, 200))
    large = planner.plan(wheel(), "AC", ScreenSize(1000, 2000))
    assert small.points[0].is_within(ScreenSize(100, 200))
    assert large.points[0].is_within(ScreenSize(1000, 2000))
    assert large.points[0].x > small.points[0].x


def test_duration_has_documented_minimum() -> None:
    assert (
        SwipePathPlanner(duration_per_letter_ms=10, minimum_duration_ms=300)
        .plan_normalized(wheel(), "AB")
        .duration_ms
        == 300
    )


def test_planner_has_no_adb_dependency() -> None:
    import word_madness_bot.gameplay.swipe_generator as module

    assert not any("adb" in name.lower() for name in module.__dict__)
