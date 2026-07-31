"""Resolution-independent geometry value objects."""

from __future__ import annotations

from dataclasses import dataclass

from word_madness_bot.domain.errors import DomainValidationError


@dataclass(frozen=True, slots=True)
class ScreenSize:
    """Positive device screen dimensions in pixels."""

    width: int
    height: int

    def __post_init__(self) -> None:
        if self.width <= 0 or self.height <= 0:
            raise DomainValidationError("Screen dimensions must be positive")


@dataclass(frozen=True, slots=True)
class PixelPoint:
    """A non-negative point in device pixels."""

    x: int
    y: int

    def __post_init__(self) -> None:
        if self.x < 0 or self.y < 0:
            raise DomainValidationError("Pixel coordinates cannot be negative")

    def is_within(self, size: ScreenSize) -> bool:
        """Return whether the point lies inside the screen bounds."""
        return self.x < size.width and self.y < size.height


@dataclass(frozen=True, slots=True)
class NormalizedPoint:
    """A point normalized to the inclusive range from zero to one."""

    x: float
    y: float

    def __post_init__(self) -> None:
        if not 0.0 <= self.x <= 1.0 or not 0.0 <= self.y <= 1.0:
            raise DomainValidationError("Normalized coordinates must be between zero and one")

    def to_pixels(self, size: ScreenSize) -> PixelPoint:
        """Scale this point to a concrete screen without exceeding its bounds."""
        return PixelPoint(
            x=round(self.x * (size.width - 1)),
            y=round(self.y * (size.height - 1)),
        )


@dataclass(frozen=True, slots=True)
class PixelRect:
    """A positive rectangular pixel region."""

    left: int
    top: int
    width: int
    height: int

    def __post_init__(self) -> None:
        if self.left < 0 or self.top < 0:
            raise DomainValidationError("Rectangle origin cannot be negative")
        if self.width <= 0 or self.height <= 0:
            raise DomainValidationError("Rectangle dimensions must be positive")

    @property
    def right(self) -> int:
        """Return the exclusive right edge."""
        return self.left + self.width

    @property
    def bottom(self) -> int:
        """Return the exclusive bottom edge."""
        return self.top + self.height

    def is_within(self, size: ScreenSize) -> bool:
        """Return whether the entire rectangle lies inside the screen."""
        return self.right <= size.width and self.bottom <= size.height
