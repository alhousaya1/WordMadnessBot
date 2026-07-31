"""Integration coverage from typed detected letters to device path."""

from word_madness_bot.domain.geometry import NormalizedPoint, ScreenSize
from word_madness_bot.domain.models import LetterPosition, SwipePath
from word_madness_bot.gameplay.swipe_generator import SwipePathPlanner


def test_typed_letter_wheel_produces_android_port_path() -> None:
    letters = (
        LetterPosition("C", NormalizedPoint(0.2, 0.5)),
        LetterPosition("A", NormalizedPoint(0.5, 0.2)),
        LetterPosition("T", NormalizedPoint(0.8, 0.5)),
    )
    path = SwipePathPlanner().plan(letters, "CAT", ScreenSize(1080, 2400))
    assert isinstance(path, SwipePath)
    assert path.points[0].x < path.points[-1].x
