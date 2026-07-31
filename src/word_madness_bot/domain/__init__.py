"""Framework-independent domain types for Word Madness Bot."""

from word_madness_bot.domain.enums import GameState, InputActionKind
from word_madness_bot.domain.models import (
    BoundingBox,
    CapturedFrame,
    DetectedLetter,
    DeviceInfo,
    LetterWheel,
    LevelDefinition,
    NormalizedPoint,
    Point,
    ScreenGeometry,
    StateObservation,
    SwipePath,
    VisionEvidence,
)

__all__ = [
    "BoundingBox",
    "CapturedFrame",
    "DetectedLetter",
    "DeviceInfo",
    "GameState",
    "InputActionKind",
    "LetterWheel",
    "LevelDefinition",
    "NormalizedPoint",
    "Point",
    "ScreenGeometry",
    "StateObservation",
    "SwipePath",
    "VisionEvidence",
]
