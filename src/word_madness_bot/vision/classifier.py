"""Generic visual-evidence classifier with no game-state knowledge."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class Classification:
    """Neutral visual label and confidence."""

    label: str
    confidence: float


class VisionClassifier:
    """Select the strongest visual label above a configured confidence."""

    def __init__(self, *, minimum_confidence: float = 0.7, unknown_label: str = "unknown") -> None:
        if not 0 <= minimum_confidence <= 1 or not unknown_label.strip():
            raise ValueError("Invalid classifier configuration")
        self.minimum_confidence = minimum_confidence
        self.unknown_label = unknown_label

    def classify(self, evidence: Mapping[str, float]) -> Classification:
        """Classify generic evidence without interpreting game state."""
        if any(
            not label.strip() or not 0 <= confidence <= 1 for label, confidence in evidence.items()
        ):
            raise ValueError("Invalid classification evidence")
        if not evidence:
            return Classification(self.unknown_label, 0.0)
        label, confidence = max(evidence.items(), key=lambda item: (item[1], item[0]))
        if confidence < self.minimum_confidence:
            return Classification(self.unknown_label, confidence)
        return Classification(label, confidence)
