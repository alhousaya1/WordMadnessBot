"""Tests for resolution-independent geometry conversion."""

import pytest

from word_madness_bot.domain.models import NormalizedPoint, Point, ScreenGeometry
from word_madness_bot.vision.geometry import (
    NormalizedBox,
    scale_length,
    to_pixel_box,
    to_pixel_point,
)


@pytest.mark.parametrize(
    ("geometry", "expected"),
    [
        (ScreenGeometry(1000, 2000, 400), Point(250, 1500)),
        (ScreenGeometry(2000, 1000, 400), Point(500, 750)),
    ],
)
def test_normalized_point_scales_with_each_resolution(
    geometry: ScreenGeometry,
    expected: Point,
) -> None:
    """Identical normalized coordinates adapt to distinct screen shapes."""

    assert to_pixel_point(NormalizedPoint(0.25, 0.75), geometry) == expected


def test_normalized_box_is_bounded_at_screen_edges() -> None:
    """A full normalized region produces a valid full-screen pixel box."""

    geometry = ScreenGeometry(1080, 2400, 420)

    assert to_pixel_box(NormalizedBox(0.0, 0.0, 1.0, 1.0), geometry).right == 1080
    assert scale_length(0.25, geometry) == 270


def test_invalid_normalized_box_is_rejected() -> None:
    """Inverted or out-of-range normalized regions fail immediately."""

    with pytest.raises(ValueError, match="positive width"):
        NormalizedBox(0.5, 0.1, 0.4, 0.9)
