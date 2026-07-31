"""Tests for framework-independent domain invariants."""

from datetime import UTC, datetime

import pytest

from word_madness_bot.domain.models import (
    BoundingBox,
    CapturedFrame,
    NormalizedPoint,
    Point,
    ScreenGeometry,
    SwipePath,
)


def test_bounding_box_exposes_dimensions() -> None:
    """Bounding boxes calculate their dimensions from valid edges."""

    box = BoundingBox(left=10, top=20, right=50, bottom=80)

    assert box.width == 40
    assert box.height == 60


@pytest.mark.parametrize("x,y", [(-0.1, 0.5), (0.5, 1.1)])
def test_normalized_point_rejects_out_of_range_coordinates(x: float, y: float) -> None:
    """Normalized coordinates cannot escape the screen range."""

    with pytest.raises(ValueError, match=r"between 0\.0 and 1\.0"):
        NormalizedPoint(x=x, y=y)


def test_captured_frame_requires_image_data() -> None:
    """Empty screenshot payloads are rejected at the boundary."""

    with pytest.raises(ValueError, match="cannot be empty"):
        CapturedFrame(
            data=b"",
            geometry=ScreenGeometry(width=1080, height=2400, density_dpi=420),
            captured_at=datetime.now(UTC),
        )


def test_swipe_path_requires_two_points() -> None:
    """A single point cannot represent a completed swipe."""

    with pytest.raises(ValueError, match="at least two"):
        SwipePath(points=(Point(1, 1),), duration_ms=100)
