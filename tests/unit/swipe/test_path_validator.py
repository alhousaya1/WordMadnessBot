"""Unit tests for normalized swipe path safety validation."""

import pytest

from word_madness_bot.domain.errors import SwipePlanningError
from word_madness_bot.domain.models import NormalizedPoint, SwipePath
from word_madness_bot.swipe.path_validator import PathValidator


def test_valid_path_is_returned_unchanged() -> None:
    """Validation preserves the exact typed path object when all invariants pass."""

    path = SwipePath(
        (NormalizedPoint(0.1, 0.1), NormalizedPoint(0.2, 0.2)),
        duration_ms=200,
    )

    assert PathValidator(maximum_step_fraction=0.2).validate(path) is path


def test_stationary_segment_is_rejected() -> None:
    """Two consecutive identical points cannot represent safe movement."""

    point = NormalizedPoint(0.5, 0.5)
    path = SwipePath((point, point), duration_ms=200)

    with pytest.raises(SwipePlanningError, match="stationary"):
        PathValidator().validate(path)


def test_discontinuous_segment_is_rejected() -> None:
    """An under-interpolated path cannot exceed the configured step limit."""

    path = SwipePath(
        (NormalizedPoint(0.0, 0.0), NormalizedPoint(1.0, 1.0)),
        duration_ms=200,
    )

    with pytest.raises(SwipePlanningError, match="exceeds maximum"):
        PathValidator(maximum_step_fraction=0.25).validate(path)


@pytest.mark.parametrize(("x", "y"), [(float("nan"), 0.5), (0.5, float("inf"))])
def test_nonfinite_normalized_points_are_rejected(x: float, y: float) -> None:
    """NaN and infinity cannot bypass normalized screen-bound validation."""

    with pytest.raises(ValueError, match="finite"):
        NormalizedPoint(x, y)
