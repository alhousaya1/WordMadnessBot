"""Resolution-independent conversion between reference and device geometry."""

from __future__ import annotations

from dataclasses import dataclass

from word_madness_bot.domain.errors import DomainValidationError
from word_madness_bot.domain.geometry import NormalizedPoint, PixelPoint, PixelRect
from word_madness_bot.domain.models import DisplayMetrics, SwipePath


@dataclass(frozen=True, slots=True)
class ScreenGeometry:
    """Scale completed geometry from reference display metrics to a target.

    Points use inclusive screen endpoints, rectangles use exclusive edges,
    radii use the smaller axis scale to remain circular, and durations use the
    density ratio so physical gesture timing remains proportional.
    """

    reference: DisplayMetrics
    target: DisplayMetrics

    @property
    def width_scale(self) -> float:
        """Return the horizontal rectangle scale."""
        return self.target.size.width / self.reference.size.width

    @property
    def height_scale(self) -> float:
        """Return the vertical rectangle scale."""
        return self.target.size.height / self.reference.size.height

    @property
    def density_scale(self) -> float:
        """Return the target-to-reference density ratio."""
        return self.target.density_dpi / self.reference.density_dpi

    def scale_point(self, point: PixelPoint, *, clamp: bool = False) -> PixelPoint:
        """Scale a reference point, optionally clamping out-of-bounds input."""
        source = self.clamp_reference_point(point) if clamp else point
        if not source.is_within(self.reference.size):
            raise DomainValidationError("Point lies outside the reference screen")
        return self.normalize_point(source).to_pixels(self.target.size)

    def normalize_point(self, point: PixelPoint) -> NormalizedPoint:
        """Convert an in-bounds reference pixel point to normalized space."""
        if not point.is_within(self.reference.size):
            raise DomainValidationError("Point lies outside the reference screen")
        return NormalizedPoint(
            x=_normalize_axis(point.x, self.reference.size.width),
            y=_normalize_axis(point.y, self.reference.size.height),
        )

    def target_to_normalized(self, point: PixelPoint) -> NormalizedPoint:
        """Convert an in-bounds target pixel point to normalized space."""
        if not point.is_within(self.target.size):
            raise DomainValidationError("Point lies outside the target screen")
        return NormalizedPoint(
            x=_normalize_axis(point.x, self.target.size.width),
            y=_normalize_axis(point.y, self.target.size.height),
        )

    def clamp_reference_point(self, point: PixelPoint) -> PixelPoint:
        """Clamp a point to the nearest valid reference pixel."""
        return PixelPoint(
            x=min(point.x, self.reference.size.width - 1),
            y=min(point.y, self.reference.size.height - 1),
        )

    def scale_rect(self, rect: PixelRect, *, clamp: bool = False) -> PixelRect:
        """Scale a reference rectangle using exclusive-edge arithmetic."""
        source = self._clamp_reference_rect(rect) if clamp else rect
        if not source.is_within(self.reference.size):
            raise DomainValidationError("Rectangle lies outside the reference screen")
        left = round(source.left * self.width_scale)
        top = round(source.top * self.height_scale)
        right = round(source.right * self.width_scale)
        bottom = round(source.bottom * self.height_scale)
        return PixelRect(left, top, max(1, right - left), max(1, bottom - top))

    def scale_radius(self, radius: int) -> int:
        """Scale a positive radius without turning circles into ellipses."""
        if radius <= 0:
            raise DomainValidationError("Radius must be positive")
        return max(1, round(radius * min(self.width_scale, self.height_scale)))

    def scale_duration(self, duration_ms: int) -> int:
        """Scale a positive gesture duration by display-density ratio."""
        if duration_ms <= 0:
            raise DomainValidationError("Duration must be positive")
        return max(1, round(duration_ms * self.density_scale))

    def scale_path(self, path: SwipePath, *, clamp: bool = False) -> SwipePath:
        """Scale every point and the duration of a completed path."""
        return SwipePath(
            points=tuple(self.scale_point(point, clamp=clamp) for point in path.points),
            duration_ms=self.scale_duration(path.duration_ms),
        )

    def _clamp_reference_rect(self, rect: PixelRect) -> PixelRect:
        left = min(rect.left, self.reference.size.width - 1)
        top = min(rect.top, self.reference.size.height - 1)
        right = min(max(rect.right, left + 1), self.reference.size.width)
        bottom = min(max(rect.bottom, top + 1), self.reference.size.height)
        return PixelRect(left, top, right - left, bottom - top)


def _normalize_axis(value: int, extent: int) -> float:
    """Normalize an inclusive pixel axis, including one-pixel displays."""
    return 0.0 if extent == 1 else value / (extent - 1)
