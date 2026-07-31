"""Immutable, framework-independent value objects used between layers."""

from collections.abc import Mapping
from dataclasses import dataclass, field
from datetime import datetime
from math import isfinite
from typing import Any

from word_madness_bot.domain.enums import GameState, StateReasonCode


def _validate_confidence(value: float) -> None:
    if not 0.0 <= value <= 1.0:
        raise ValueError("confidence must be between 0.0 and 1.0")


@dataclass(frozen=True, slots=True)
class Point:
    """An absolute pixel coordinate."""

    x: int
    y: int

    def __post_init__(self) -> None:
        if self.x < 0 or self.y < 0:
            raise ValueError("pixel coordinates cannot be negative")


@dataclass(frozen=True, slots=True)
class NormalizedPoint:
    """A resolution-independent coordinate in the inclusive range zero to one."""

    x: float
    y: float

    def __post_init__(self) -> None:
        if not isfinite(self.x) or not isfinite(self.y):
            raise ValueError("normalized coordinates must be finite")
        if not 0.0 <= self.x <= 1.0 or not 0.0 <= self.y <= 1.0:
            raise ValueError("normalized coordinates must be between 0.0 and 1.0")


@dataclass(frozen=True, slots=True)
class BoundingBox:
    """An absolute rectangular image region."""

    left: int
    top: int
    right: int
    bottom: int

    def __post_init__(self) -> None:
        if self.left < 0 or self.top < 0:
            raise ValueError("bounding box origin cannot be negative")
        if self.right <= self.left or self.bottom <= self.top:
            raise ValueError("bounding box must have positive width and height")

    @property
    def width(self) -> int:
        """Return the box width in pixels."""

        return self.right - self.left

    @property
    def height(self) -> int:
        """Return the box height in pixels."""

        return self.bottom - self.top


@dataclass(frozen=True, slots=True)
class ScreenGeometry:
    """Physical properties needed for resolution-independent calculations."""

    width: int
    height: int
    density_dpi: int

    def __post_init__(self) -> None:
        if self.width <= 0 or self.height <= 0 or self.density_dpi <= 0:
            raise ValueError("screen dimensions and density must be positive")


@dataclass(frozen=True, slots=True)
class DeviceInfo:
    """Stable metadata describing one connected Android device."""

    serial: str
    model: str
    android_version: str
    screen: ScreenGeometry

    def __post_init__(self) -> None:
        if not self.serial.strip():
            raise ValueError("device serial cannot be empty")


@dataclass(frozen=True, slots=True)
class CapturedFrame:
    """Encoded screenshot data and acquisition metadata."""

    data: bytes
    geometry: ScreenGeometry
    captured_at: datetime
    media_type: str = "image/png"

    def __post_init__(self) -> None:
        if not self.data:
            raise ValueError("captured frame cannot be empty")
        if not self.media_type.startswith("image/"):
            raise ValueError("captured frame media type must be an image")


@dataclass(frozen=True, slots=True)
class VisionEvidence:
    """One confidence-bearing observation produced by the vision layer."""

    kind: str
    confidence: float
    region: BoundingBox | None = None
    value: str | int | float | None = None
    normalized_location: NormalizedPoint | None = None
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not self.kind.strip():
            raise ValueError("vision evidence kind cannot be empty")
        _validate_confidence(self.confidence)


@dataclass(frozen=True, slots=True)
class AdvertisementContext:
    """Caller-owned progress required for safe advertisement policy decisions."""

    observation_revision: int
    attempt_count: int = 0
    elapsed_seconds: float = 0.0
    last_action_revision: int | None = None

    def __post_init__(self) -> None:
        if self.observation_revision < 0:
            raise ValueError("observation revision cannot be negative")
        if self.attempt_count < 0:
            raise ValueError("advertisement attempt count cannot be negative")
        if not isfinite(self.elapsed_seconds) or self.elapsed_seconds < 0.0:
            raise ValueError("advertisement elapsed time must be finite and nonnegative")
        if self.last_action_revision is not None and self.last_action_revision < 0:
            raise ValueError("last action revision cannot be negative")


@dataclass(frozen=True, slots=True)
class OcrResult:
    """Text recognized by an interchangeable OCR engine."""

    text: str
    confidence: float

    def __post_init__(self) -> None:
        _validate_confidence(self.confidence)


@dataclass(frozen=True, slots=True)
class LevelReading:
    """A confidence-bearing level-number observation."""

    number: int
    confidence: float
    raw_text: str

    def __post_init__(self) -> None:
        if self.number <= 0:
            raise ValueError("level reading number must be positive")
        _validate_confidence(self.confidence)


@dataclass(frozen=True, slots=True)
class CircleDetection:
    """A detected circle expressed in absolute image coordinates."""

    center: Point
    radius: int
    confidence: float

    def __post_init__(self) -> None:
        if self.radius <= 0:
            raise ValueError("circle radius must be positive")
        _validate_confidence(self.confidence)


@dataclass(frozen=True, slots=True)
class TemplateMatch:
    """A confidence-bearing template location within a source image."""

    region: BoundingBox
    confidence: float

    def __post_init__(self) -> None:
        _validate_confidence(self.confidence)


@dataclass(frozen=True, slots=True)
class DetectedLetter:
    """A recognized wheel letter and its center coordinate."""

    character: str
    center: Point
    confidence: float

    def __post_init__(self) -> None:
        if len(self.character) != 1 or not self.character.isalpha():
            raise ValueError("detected letter must be one alphabetic character")
        _validate_confidence(self.confidence)


@dataclass(frozen=True, slots=True)
class LetterWheel:
    """Detected wheel geometry and letters in stable circular order."""

    center: Point
    radius: int
    letters: tuple[DetectedLetter, ...]
    confidence: float

    def __post_init__(self) -> None:
        if self.radius <= 0:
            raise ValueError("letter wheel radius must be positive")
        if not self.letters:
            raise ValueError("letter wheel must contain at least one letter")
        _validate_confidence(self.confidence)


@dataclass(frozen=True, slots=True)
class LevelDefinition:
    """Data-driven solution data for one game level."""

    number: int
    letters: tuple[str, ...]
    words: tuple[str, ...]

    def __post_init__(self) -> None:
        if self.number <= 0:
            raise ValueError("level number must be positive")
        if not self.letters or not self.words:
            raise ValueError("level letters and words cannot be empty")
        normalized_letters = tuple(letter.strip().upper() for letter in self.letters)
        normalized_words = tuple(word.strip().upper() for word in self.words)
        if any(len(letter) != 1 or not letter.isalpha() for letter in normalized_letters):
            raise ValueError("level letters must be single alphabetic characters")
        if any(len(word) < 2 or not word.isalpha() for word in normalized_words):
            raise ValueError("level words must contain at least two alphabetic characters")
        if len(set(normalized_words)) != len(normalized_words):
            raise ValueError("level words must be unique")
        object.__setattr__(self, "letters", normalized_letters)
        object.__setattr__(self, "words", normalized_words)


@dataclass(frozen=True, slots=True)
class SwipeLetter:
    """A detected wheel letter at a resolution-independent screen coordinate."""

    character: str
    coordinate: NormalizedPoint

    def __post_init__(self) -> None:
        normalized = self.character.strip().upper()
        if len(normalized) != 1 or not normalized.isascii() or not normalized.isalpha():
            raise ValueError("swipe letter must be one ASCII alphabetic character")
        object.__setattr__(self, "character", normalized)


@dataclass(frozen=True, slots=True)
class SwipePath:
    """A complete resolution-independent path ready for input execution."""

    points: tuple[NormalizedPoint, ...]
    duration_ms: int

    def __post_init__(self) -> None:
        if len(self.points) < 2:
            raise ValueError("swipe path requires at least two points")
        if self.duration_ms <= 0:
            raise ValueError("swipe duration must be positive")


@dataclass(frozen=True, slots=True)
class StateObservation:
    """A classified game state with the evidence supporting it."""

    state: GameState
    confidence: float
    evidence: tuple[VisionEvidence, ...] = ()
    reason_codes: tuple[StateReasonCode, ...] = ()

    def __post_init__(self) -> None:
        _validate_confidence(self.confidence)
        if not self.reason_codes:
            raise ValueError("state observation requires at least one reason code")


@dataclass(frozen=True, slots=True)
class RuntimeObservation:
    """State output plus already-produced level and wheel Vision results."""

    revision: int
    state: StateObservation
    level: LevelReading | None = None
    letters: tuple[SwipeLetter, ...] = ()
    elapsed_seconds: float = 0.0

    def __post_init__(self) -> None:
        if self.revision < 0:
            raise ValueError("observation revision cannot be negative")
        if not isfinite(self.elapsed_seconds) or self.elapsed_seconds < 0.0:
            raise ValueError("observation elapsed time must be finite and nonnegative")
