"""Unit tests for complete deterministic swipe path planning."""

import pytest

from word_madness_bot.config import Settings
from word_madness_bot.domain.errors import SwipePlanningError
from word_madness_bot.domain.models import NormalizedPoint, SwipeLetter, SwipePath
from word_madness_bot.swipe.path_planner import PathPlanner


def _letters() -> tuple[SwipeLetter, ...]:
    return (
        SwipeLetter("C", NormalizedPoint(0.3, 0.7)),
        SwipeLetter("A", NormalizedPoint(0.5, 0.5)),
        SwipeLetter("T", NormalizedPoint(0.7, 0.7)),
    )


def test_planner_from_settings_returns_validated_typed_path() -> None:
    """Configured composition emits a normalized SwipePath and deterministic duration."""

    planner = PathPlanner.from_settings(
        Settings(
            swipe_interpolation_points=3,
            swipe_smoothing_strength=0.5,
            swipe_duration_per_letter_ms=100,
            swipe_maximum_step_fraction=0.25,
        )
    )

    path = planner.generate("CAT", _letters())

    assert isinstance(path, SwipePath)
    assert path.duration_ms == 300
    assert path.points[0] == NormalizedPoint(0.3, 0.7)
    assert path.points[-1] == NormalizedPoint(0.7, 0.7)
    assert all(0.0 <= point.x <= 1.0 and 0.0 <= point.y <= 1.0 for point in path.points)


def test_planner_is_deterministic() -> None:
    """Identical semantic inputs always return exactly equal paths."""

    planner = PathPlanner.from_settings(Settings())

    assert planner.generate("CAT", _letters()) == planner.generate(
        " cat ", tuple(reversed(_letters()))
    )


def test_planner_validates_before_returning() -> None:
    """A policy with insufficient interpolation cannot return a discontinuous path."""

    planner = PathPlanner.from_settings(
        Settings(
            swipe_interpolation_points=0,
            swipe_maximum_step_fraction=0.1,
        )
    )

    with pytest.raises(SwipePlanningError, match="exceeds maximum"):
        planner.generate("CAT", _letters())
