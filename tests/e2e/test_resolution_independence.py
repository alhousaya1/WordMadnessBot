"""Release smoke test for normalized coordinate invariance."""

from word_madness_bot.domain.models import NormalizedPoint, ScreenGeometry
from word_madness_bot.vision.geometry import to_pixel_point


def test_normalized_coordinates_scale_without_source_changes() -> None:
    point = NormalizedPoint(0.25, 0.75)
    assert to_pixel_point(point, ScreenGeometry(1080, 2400, 420)).x == 270
    assert to_pixel_point(point, ScreenGeometry(1440, 3120, 600)).x == 360
