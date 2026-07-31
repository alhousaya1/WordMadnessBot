"""Tests for resolution-independent screen geometry."""

from __future__ import annotations

import pytest

from word_madness_bot.domain.errors import DomainValidationError
from word_madness_bot.domain.geometry import PixelPoint, PixelRect, ScreenSize
from word_madness_bot.domain.models import DisplayMetrics, SwipePath
from word_madness_bot.gameplay.geometry import ScreenGeometry


def metrics(width: int, height: int, density: int = 420) -> DisplayMetrics:
    return DisplayMetrics(ScreenSize(width, height), density)


def scaler(
    reference: tuple[int, int, int] = (1440, 3120, 560),
    target: tuple[int, int, int] = (1080, 2400, 420),
) -> ScreenGeometry:
    return ScreenGeometry(
        metrics(reference[0], reference[1], reference[2]),
        metrics(target[0], target[1], target[2]),
    )


def test_point_endpoints_scale_to_target_endpoints() -> None:
    geometry = scaler()
    assert geometry.scale_point(PixelPoint(0, 0)) == PixelPoint(0, 0)
    assert geometry.scale_point(PixelPoint(1439, 3119)) == PixelPoint(1079, 2399)


def test_point_scaling_supports_different_portrait_aspect_ratios() -> None:
    geometry = scaler(target=(720, 1600, 320))
    point = geometry.scale_point(PixelPoint(720, 1560))
    assert point == PixelPoint(360, 800)


def test_rectangle_uses_independent_axis_scales() -> None:
    geometry = scaler(reference=(100, 200, 400), target=(200, 300, 400))
    assert geometry.scale_rect(PixelRect(10, 20, 30, 40)) == PixelRect(20, 30, 60, 60)


def test_radius_uses_smaller_axis_scale() -> None:
    geometry = scaler(reference=(100, 200, 400), target=(200, 300, 400))
    assert geometry.scale_radius(10) == 15


def test_duration_uses_density_ratio() -> None:
    geometry = scaler(reference=(100, 200, 400), target=(200, 300, 600))
    assert geometry.scale_duration(200) == 300


def test_path_scales_points_and_duration() -> None:
    geometry = scaler(reference=(100, 200, 400), target=(200, 400, 600))
    path = SwipePath((PixelPoint(0, 0), PixelPoint(99, 199)), 200)
    assert geometry.scale_path(path) == SwipePath((PixelPoint(0, 0), PixelPoint(199, 399)), 300)


def test_out_of_bounds_point_and_rectangle_are_rejected() -> None:
    geometry = scaler(reference=(100, 200, 400), target=(200, 400, 400))
    with pytest.raises(DomainValidationError, match="Point"):
        geometry.scale_point(PixelPoint(100, 0))
    with pytest.raises(DomainValidationError, match="Rectangle"):
        geometry.scale_rect(PixelRect(90, 190, 20, 20))


def test_out_of_bounds_values_can_be_explicitly_clamped() -> None:
    geometry = scaler(reference=(100, 200, 400), target=(200, 400, 400))
    assert geometry.scale_point(PixelPoint(150, 250), clamp=True) == PixelPoint(199, 399)
    assert geometry.scale_rect(PixelRect(90, 190, 20, 20), clamp=True) == PixelRect(
        180, 380, 20, 20
    )


@pytest.mark.parametrize("value", [0, -1])
def test_invalid_radius_and_duration_are_rejected(value: int) -> None:
    geometry = scaler()
    with pytest.raises(DomainValidationError):
        geometry.scale_radius(value)
    with pytest.raises(DomainValidationError):
        geometry.scale_duration(value)


def test_normalization_round_trip_is_within_one_pixel() -> None:
    geometry = scaler(reference=(1080, 2400, 420), target=(720, 1600, 320))
    original = PixelPoint(537, 1197)
    normalized = geometry.normalize_point(original)
    round_trip = normalized.to_pixels(geometry.reference.size)
    assert abs(round_trip.x - original.x) <= 1
    assert abs(round_trip.y - original.y) <= 1


def test_single_pixel_screen_normalizes_without_division_by_zero() -> None:
    geometry = scaler(reference=(1, 1, 160), target=(1, 1, 160))
    assert geometry.normalize_point(PixelPoint(0, 0)).x == 0.0
    assert geometry.scale_point(PixelPoint(0, 0)) == PixelPoint(0, 0)


@pytest.mark.parametrize(
    ("width", "height", "density"),
    [(0, 100, 420), (100, 0, 420), (-1, 100, 420), (100, 100, 0)],
)
def test_invalid_display_metrics_are_rejected(width: int, height: int, density: int) -> None:
    with pytest.raises(DomainValidationError):
        metrics(width, height, density)


def test_geometry_module_has_no_adb_or_vision_dependency() -> None:
    import word_madness_bot.gameplay.geometry as module

    names = set(module.__dict__)
    assert not any("adb" in name.lower() or "vision" in name.lower() for name in names)
