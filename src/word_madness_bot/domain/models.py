"""Immutable values exchanged through application ports."""

from __future__ import annotations

import unicodedata
from dataclasses import dataclass, field
from enum import StrEnum

from word_madness_bot.domain.errors import DomainValidationError
from word_madness_bot.domain.geometry import NormalizedPoint, PixelPoint, ScreenSize
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
class SwipeExecutionReceipt:
    """Backend evidence for one continuous gesture command."""

    backend_command: tuple[str, ...]
    timestamps_ms: tuple[int, ...]

    def __post_init__(self) -> None:
        if not self.backend_command:
            raise DomainValidationError("Swipe backend command cannot be empty")
        if len(self.timestamps_ms) < 2:
            raise DomainValidationError("Swipe execution requires at least two timestamps")
        if self.timestamps_ms[0] != 0:
            raise DomainValidationError("Swipe timestamps must begin at zero")
        if any(
            current <= previous
            for previous, current in zip(self.timestamps_ms, self.timestamps_ms[1:], strict=False)
        ):
            raise DomainValidationError("Swipe timestamps must increase")


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


@dataclass(frozen=True, slots=True)
class StateObservation:
    """A confidence-bearing result from temporal game-state detection."""

    state: GameState
    confidence: float
    evidence: tuple[tuple[str, str], ...] = field(default_factory=tuple)
    stable: bool = False
    consecutive_observations: int = 1
    transition_valid: bool = True

    def __post_init__(self) -> None:
        if not 0.0 <= self.confidence <= 1.0:
            raise DomainValidationError("State confidence must be between zero and one")
        if self.consecutive_observations <= 0:
            raise DomainValidationError("Consecutive observations must be positive")


@dataclass(frozen=True, slots=True)
class LetterPosition:
    """One detected wheel letter at a resolution-independent position."""

    character: str
    position: NormalizedPoint

    def __post_init__(self) -> None:
        normalized = unicodedata.normalize("NFC", self.character.strip()).upper()
        if len(normalized) != 1 or not normalized.isalpha():
            raise DomainValidationError("A letter position requires one alphabetic character")
        object.__setattr__(self, "character", normalized)


@dataclass(frozen=True, slots=True)
class NormalizedSwipePath:
    """A validated input-free swipe plan in normalized coordinates."""

    points: tuple[NormalizedPoint, ...]
    duration_ms: int
    word: str

    def __post_init__(self) -> None:
        if len(self.points) < 2:
            raise DomainValidationError("A normalized swipe requires at least two points")
        if self.duration_ms <= 0:
            raise DomainValidationError("Swipe duration must be positive")
        if len(self.word) < 2 or not self.word.isalpha():
            raise DomainValidationError("A swipe path requires an alphabetic word")
