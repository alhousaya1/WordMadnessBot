"""State-layer access to confidence-bearing Vision evidence."""

import logging

from word_madness_bot.contracts.vision import VisionEvidenceProvider
from word_madness_bot.domain.models import CapturedFrame, VisionEvidence

_LOGGER = logging.getLogger(__name__)


class EvidenceCollector:
    """Collect and deterministically order evidence through the narrow Vision contract."""

    def __init__(self, vision: VisionEvidenceProvider) -> None:
        self._vision = vision

    def collect(self, frame: CapturedFrame) -> tuple[VisionEvidence, ...]:
        """Return Vision evidence ordered by kind and descending confidence."""

        evidence = tuple(
            sorted(
                self._vision.collect_evidence(frame),
                key=lambda item: (item.kind, -item.confidence),
            )
        )
        _LOGGER.debug(
            "Collected state evidence",
            extra={
                "event": "state_evidence_collected",
                "evidence_count": len(evidence),
                "evidence_kinds": tuple(item.kind for item in evidence),
            },
        )
        return evidence
