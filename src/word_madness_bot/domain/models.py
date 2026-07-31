"""Immutable values exchanged through application ports."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum

from word_madness_bot.domain.errors import DomainValidationError
from word_madness_bot.domain.geometry import PixelPoint, ScreenSize
from word_madness_bot.domain.states import GameState


class DeviceState(StrEnum):
    """Connection states exposed by an Android transport."""

    ONLINE = "online"
    OFFLINE = "offline"
    UNAUTHORIZED = "unauthorized"
    UNKNOWN = "unknown"


@dataclass(frozen=True, slots=True)
class DeviceDescriptor:
    """Transport-neutral identity and state for one Android device."""

    serial: str
    state: DeviceState
    attributes: tuple[tuple[str, str], ...] = field(default_factory=tuple)

    def __post_init__(self) -> None:
        if not self.serial.strip():
            raise DomainValidationError("Device serial cannot be empty")


@dataclass(frozen=True, slots=True)
class DisplayMetrics:
    """Detected screen size and density for one device."""

    size: ScreenSize
    density_dpi: int

    def __post_init__(self) -> None:
        if self.density_dpi <= 0:
            raise DomainValidationError("Display density must be positive")


@dataclass(frozen=True, slots=True)
class ScreenCapture:
    """Encoded screenshot bytes and the size at which they were captured."""

    data: bytes
    size: ScreenSize
    media_type: str = "image/png"

    def __post_init__(self) -> None:
        if not self.data:
            raise DomainValidationError("Screen capture data cannot be empty")
        if not self.media_type.strip():
            raise DomainValidationError("Screen capture media type cannot be empty")


@dataclass(frozen=True, slots=True)
class SwipePath:
    """A completed device input path supplied to the Android boundary."""

    points: tuple[PixelPoint, ...]
    duration_ms: int

    def __post_init__(self) -> None:
        if len(self.points) < 2:
            raise DomainValidationError("A swipe path requires at least two points")
        if self.duration_ms <= 0:
            raise DomainValidationError("Swipe duration must be positive")


@dataclass(frozen=True, slots=True)
class Level:
    """Validated data-driven words for one game level."""

    number: int
    words: tuple[str, ...]

    def __post_init__(self) -> None:
        if self.number <= 0:
            raise DomainValidationError("Level number must be positive")
        if not self.words or any(not word.strip() for word in self.words):
            raise DomainValidationError("A level requires non-empty words")


@dataclass(frozen=True, slots=True)
class VisionObservation:
    """Transport-neutral result produced by a future vision implementation."""

    state: GameState
    confidence: float
    evidence: tuple[tuple[str, str], ...] = field(default_factory=tuple)

    def __post_init__(self) -> None:
        if not 0.0 <= self.confidence <= 1.0:
            raise DomainValidationError("Vision confidence must be between zero and one")
