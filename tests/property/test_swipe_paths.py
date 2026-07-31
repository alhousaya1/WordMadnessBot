"""Invariant tests over representative valid wheels and resolutions."""

import pytest

from word_madness_bot.domain.geometry import NormalizedPoint, ScreenSize
from word_madness_bot.domain.models import LetterPosition
from word_madness_bot.gameplay.swipe_generator import SwipePathPlanner


@pytest.mark.parametrize(
    "size",
    [ScreenSize(1, 1), ScreenSize(720, 1600), ScreenSize(1080, 2400), ScreenSize(1440, 3120)],
)
def test_planned_paths_are_bounded_ordered_and_positive(size: ScreenSize) -> None:
    letters = tuple(
        LetterPosition(character, point)
        for character, point in zip(
            "WORD",
            (
                NormalizedPoint(0, 0),
                NormalizedPoint(1, 0),
                NormalizedPoint(1, 1),
                NormalizedPoint(0, 1),
            ),
            strict=True,
        )
    )
    path = SwipePathPlanner().plan(letters, "WORD", size)
    assert path.duration_ms > 0
    assert all(point.is_within(size) for point in path.points)
    assert path.points[0] == NormalizedPoint(0, 0).to_pixels(size)
    assert path.points[-1] == NormalizedPoint(0, 1).to_pixels(size)
