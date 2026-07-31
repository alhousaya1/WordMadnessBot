"""Resolution-independent coordinate and region conversions."""

from dataclasses import dataclass

from word_madness_bot.domain.models import BoundingBox, NormalizedPoint, Point, ScreenGeometry


@dataclass(frozen=True, slots=True)
class NormalizedBox:
    """A rectangular region represented as fractions of image width and height."""

    left: float
    top: float
    right: float
    bottom: float

    def __post_init__(self) -> None:
        values = (self.left, self.top, self.right, self.bottom)
        if any(value < 0.0 or value > 1.0 for value in values):
            raise ValueError("normalized box coordinates must be between 0.0 and 1.0")
        if self.right <= self.left or self.bottom <= self.top:
            raise ValueError("normalized box must have positive width and height")


def to_pixel_point(point: NormalizedPoint, geometry: ScreenGeometry) -> Point:
    """Scale a normalized point into a bounded absolute pixel coordinate."""

    return Point(
        x=min(round(point.x * geometry.width), geometry.width - 1),
        y=min(round(point.y * geometry.height), geometry.height - 1),
    )


def to_normalized_point(point: Point, geometry: ScreenGeometry) -> NormalizedPoint:
    """Convert a valid absolute pixel point to a normalized coordinate."""

    if point.x >= geometry.width or point.y >= geometry.height:
        raise ValueError("point lies outside screen geometry")
    return NormalizedPoint(x=point.x / geometry.width, y=point.y / geometry.height)


def to_pixel_box(box: NormalizedBox, geometry: ScreenGeometry) -> BoundingBox:
    """Scale a normalized box into a non-empty, bounded pixel region."""

    left = min(round(box.left * geometry.width), geometry.width - 1)
    top = min(round(box.top * geometry.height), geometry.height - 1)
    right = max(left + 1, min(round(box.right * geometry.width), geometry.width))
    bottom = max(top + 1, min(round(box.bottom * geometry.height), geometry.height))
    return BoundingBox(left=left, top=top, right=right, bottom=bottom)


def scale_length(fraction: float, geometry: ScreenGeometry) -> int:
    """Scale a positive fraction against the shorter screen dimension."""

    if fraction <= 0.0:
        raise ValueError("length fraction must be positive")
    return max(1, round(fraction * min(geometry.width, geometry.height)))
