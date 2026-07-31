"""Contract for logical game-state classification."""

from collections.abc import Sequence
from typing import Protocol

from word_madness_bot.domain.models import StateObservation, VisionEvidence


class GameStateDetector(Protocol):
    """Convert vision evidence into a logical state observation."""

    def classify(self, evidence: Sequence[VisionEvidence]) -> StateObservation:
        """Classify Vision evidence without invoking OCR or input layers."""

        ...
