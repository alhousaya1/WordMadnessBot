"""Tests for foundational geometry invariants."""

import pytest

from word_madness_bot.domain.errors import DomainValidationError
from word_madness_bot.domain.geometry import NormalizedPoint, PixelPoint, PixelRect, ScreenSize


def test_normalized_points_scale_to_screen_edges() -> None:
    size = ScreenSize(width=1080, height=2400)

    assert NormalizedPoint(0.0, 0.0).to_pixels(size) == PixelPoint(0, 0)
    assert NormalizedPoint(1.0, 1.0).to_pixels(size) == PixelPoint(1079, 2399)
    assert NormalizedPoint(0.5, 0.5).to_pixels(size).is_within(size)


def test_rectangle_uses_exclusive_edges() -> None:
    size = ScreenSize(width=100, height=200)
    rectangle = PixelRect(left=10, top=20, width=90, height=180)

    assert rectangle.right == 100
    assert rectangle.bottom == 200
    assert rectangle.is_within(size)


@pytest.mark.parametrize(
    "factory",
    [
        lambda: ScreenSize(0, 1),
        lambda: ScreenSize(1, -1),
        lambda: PixelPoint(-1, 0),
        lambda: NormalizedPoint(-0.1, 0.5),
        lambda: NormalizedPoint(0.5, 1.1),
        lambda: PixelRect(0, 0, 0, 1),
        lambda: PixelRect(-1, 0, 1, 1),
    ],
)
def test_invalid_geometry_is_rejected(factory: object) -> None:
    with pytest.raises(DomainValidationError):
        factory()  # type: ignore[operator]
