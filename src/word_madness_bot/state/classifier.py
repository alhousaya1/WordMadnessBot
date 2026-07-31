"""Deterministic classification of Vision evidence into logical game states."""

import logging
from collections.abc import Mapping, Sequence

from word_madness_bot.config.settings import Settings
from word_madness_bot.domain.enums import GameState, StateReasonCode, VisionEvidenceKind
from word_madness_bot.domain.models import StateObservation, VisionEvidence

_LOGGER = logging.getLogger(__name__)

_EVIDENCE_STATES: Mapping[str, GameState] = {
    VisionEvidenceKind.HOME_INDICATOR: GameState.HOME,
    VisionEvidenceKind.PLAYING_BOARD: GameState.PLAYING,
    VisionEvidenceKind.LETTER_WHEEL: GameState.PLAYING,
    VisionEvidenceKind.LEVEL_NUMBER: GameState.PLAYING,
    VisionEvidenceKind.VICTORY_BANNER: GameState.VICTORY,
    VisionEvidenceKind.ADVERTISEMENT_INDICATOR: GameState.ADVERTISEMENT,
    VisionEvidenceKind.ADVERTISEMENT_CLOSE_CONTROL: GameState.ADVERTISEMENT,
}
_STATE_ORDER = (
    GameState.HOME,
    GameState.PLAYING,
    GameState.VICTORY,
    GameState.ADVERTISEMENT,
)


class StateClassifier:
    """Classify only recognized Vision evidence, preferring UNKNOWN over guesses."""

    def __init__(
        self,
        *,
        minimum_confidence: float = 0.65,
        conflict_margin: float = 0.10,
    ) -> None:
        if not 0.0 <= minimum_confidence <= 1.0:
            raise ValueError("minimum confidence must be between zero and one")
        if not 0.0 <= conflict_margin <= 1.0:
            raise ValueError("conflict margin must be between zero and one")
        self._minimum_confidence = minimum_confidence
        self._conflict_margin = conflict_margin

    @classmethod
    def from_settings(cls, settings: Settings) -> "StateClassifier":
        """Construct classification policy entirely from validated configuration."""

        return cls(
            minimum_confidence=settings.state_minimum_confidence,
            conflict_margin=settings.state_conflict_margin,
        )

    def classify(self, evidence: Sequence[VisionEvidence]) -> StateObservation:
        """Return a deterministic typed observation with machine-readable reasons."""

        ordered_evidence = tuple(sorted(evidence, key=lambda item: (item.kind, -item.confidence)))
        if not ordered_evidence:
            return self._unknown(1.0, ordered_evidence, StateReasonCode.NO_EVIDENCE)

        scores = dict.fromkeys(_STATE_ORDER, 0.0)
        recognized = False
        for item in ordered_evidence:
            state = _EVIDENCE_STATES.get(item.kind)
            if state is None:
                continue
            recognized = True
            scores[state] = max(scores[state], item.confidence)
        if not recognized:
            return self._unknown(
                1.0,
                ordered_evidence,
                StateReasonCode.NO_RECOGNIZED_EVIDENCE,
            )

        ranked = sorted(scores.items(), key=lambda item: (-item[1], _STATE_ORDER.index(item[0])))
        (winner, winner_score), (_, runner_up_score) = ranked[:2]
        if winner_score < self._minimum_confidence:
            return self._unknown(
                1.0 - winner_score,
                ordered_evidence,
                StateReasonCode.WEAK_EVIDENCE,
            )
        if runner_up_score >= self._minimum_confidence or (
            runner_up_score > 0.0 and winner_score - runner_up_score < self._conflict_margin
        ):
            conflict_confidence = (winner_score + runner_up_score) / 2.0
            return self._unknown(
                conflict_confidence,
                ordered_evidence,
                StateReasonCode.CONFLICTING_EVIDENCE,
            )

        observation = StateObservation(
            state=winner,
            confidence=winner_score,
            evidence=ordered_evidence,
            reason_codes=(StateReasonCode.CLASSIFIED,),
        )
        self._log_observation(observation)
        return observation

    def _unknown(
        self,
        confidence: float,
        evidence: tuple[VisionEvidence, ...],
        reason: StateReasonCode,
    ) -> StateObservation:
        observation = StateObservation(
            state=GameState.UNKNOWN,
            confidence=max(0.0, min(1.0, confidence)),
            evidence=evidence,
            reason_codes=(reason,),
        )
        self._log_observation(observation)
        return observation

    @staticmethod
    def _log_observation(observation: StateObservation) -> None:
        _LOGGER.debug(
            "Classified game state",
            extra={
                "event": "state_classified",
                "state": observation.state.value,
                "confidence": observation.confidence,
                "reason_codes": tuple(reason.value for reason in observation.reason_codes),
            },
        )
