"""Contract for image analysis services."""

from typing import Protocol

from word_madness_bot.domain.models import CapturedFrame, LetterWheel, LevelReading, VisionEvidence


class VisionEvidenceProvider(Protocol):
    """Narrow Vision boundary required by state evidence collection."""

    def collect_evidence(self, frame: CapturedFrame) -> tuple[VisionEvidence, ...]:
        """Return confidence-bearing evidence without classifying game state."""

        ...


class VisionEngine(VisionEvidenceProvider, Protocol):
    """Analyze captured frames without generating device input."""

    def read_level_number(self, frame: CapturedFrame) -> LevelReading | None:
        """Return a confidence-bearing level observation, or ``None`` when unreadable."""

        ...

    def read_letter_wheel(self, frame: CapturedFrame) -> LetterWheel | None:
        """Return the detected letter wheel, or ``None`` when uncertain."""

        ...
