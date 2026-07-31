"""Unit tests for bounded path interpolation and smoothing."""

from word_madness_bot.domain.models import NormalizedPoint
from word_madness_bot.swipe.path_smoother import PathSmoother


def test_interpolation_preserves_every_letter_anchor() -> None:
    """Smoothing adds points but never moves required letter coordinates."""

    anchors = (
        NormalizedPoint(0.1, 0.2),
        NormalizedPoint(0.8, 0.3),
        NormalizedPoint(0.4, 0.9),
    )

    points = PathSmoother().smooth(
        anchors,
        interpolation_points=2,
        smoothing_strength=0.75,
    )

    assert len(points) == 7
    assert (points[0], points[3], points[6]) == anchors
    assert all(0.0 <= point.x <= 1.0 and 0.0 <= point.y <= 1.0 for point in points)


def test_zero_smoothing_uses_linear_interpolation() -> None:
    """A zero smoothing policy produces evenly spaced segment points."""

    points = PathSmoother().smooth(
        (NormalizedPoint(0.0, 0.0), NormalizedPoint(1.0, 1.0)),
        interpolation_points=3,
        smoothing_strength=0.0,
    )

    assert points == (
        NormalizedPoint(0.0, 0.0),
        NormalizedPoint(0.25, 0.25),
        NormalizedPoint(0.5, 0.5),
        NormalizedPoint(0.75, 0.75),
        NormalizedPoint(1.0, 1.0),
    )
