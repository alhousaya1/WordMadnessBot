"""Temporal debouncing for confidence-bearing state observations."""

import logging

from word_madness_bot.config.settings import Settings
from word_madness_bot.domain.enums import GameState, StateReasonCode
from word_madness_bot.domain.models import StateObservation

_LOGGER = logging.getLogger(__name__)


class StateStabilizer:
    """Require consecutive matching observations before exposing a known state."""

    def __init__(self, required_consecutive: int = 2) -> None:
        if required_consecutive <= 0:
            raise ValueError("required consecutive observations must be positive")
        self._required_consecutive = required_consecutive
        self._candidate = GameState.UNKNOWN
        self._candidate_count = 0
        self._candidate_confidences: list[float] = []

    @classmethod
    def from_settings(cls, settings: Settings) -> "StateStabilizer":
        """Construct temporal policy from validated configuration."""

        return cls(required_consecutive=settings.state_stable_frames)

    def stabilize(self, observation: StateObservation) -> StateObservation:
        """Return UNKNOWN until a known state repeats for the configured frame count."""

        if observation.state is GameState.UNKNOWN:
            self.reset()
            reasons = tuple(
                dict.fromkeys((*observation.reason_codes, StateReasonCode.UNKNOWN_INPUT))
            )
            return StateObservation(
                state=GameState.UNKNOWN,
                confidence=observation.confidence,
                evidence=observation.evidence,
                reason_codes=reasons,
            )

        if observation.state is not self._candidate:
            self._candidate = observation.state
            self._candidate_count = 0
            self._candidate_confidences.clear()
        self._candidate_count += 1
        self._candidate_confidences.append(observation.confidence)

        if self._candidate_count < self._required_consecutive:
            result = StateObservation(
                state=GameState.UNKNOWN,
                confidence=1.0 - observation.confidence,
                evidence=observation.evidence,
                reason_codes=(StateReasonCode.DEBOUNCING,),
            )
        else:
            result = StateObservation(
                state=observation.state,
                confidence=min(self._candidate_confidences),
                evidence=observation.evidence,
                reason_codes=(StateReasonCode.CLASSIFIED, StateReasonCode.STABILIZED),
            )
        _LOGGER.debug(
            "Stabilized game state",
            extra={
                "event": "state_stabilized",
                "input_state": observation.state.value,
                "output_state": result.state.value,
                "candidate_count": self._candidate_count,
                "required_count": self._required_consecutive,
            },
        )
        return result

    def reset(self) -> None:
        """Forget temporal history after unknown evidence or an explicit reset."""

        self._candidate = GameState.UNKNOWN
        self._candidate_count = 0
        self._candidate_confidences.clear()
