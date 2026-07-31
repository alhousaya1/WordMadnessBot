"""Game-state detection from neutral vision classifications."""

from __future__ import annotations

from collections.abc import Mapping

from word_madness_bot.domain.models import StateObservation
from word_madness_bot.domain.states import GameState
from word_madness_bot.vision.classifier import Classification

_LABELS: Mapping[str, GameState] = {
    "home": GameState.HOME,
    "playing": GameState.PLAYING,
    "victory": GameState.VICTORY,
    "advertisement": GameState.ADVERTISEMENT,
}

_TRANSITIONS: Mapping[GameState, frozenset[GameState]] = {
    GameState.UNKNOWN: frozenset(GameState),
    GameState.HOME: frozenset(
        {GameState.HOME, GameState.PLAYING, GameState.ADVERTISEMENT, GameState.UNKNOWN}
    ),
    GameState.PLAYING: frozenset(
        {GameState.PLAYING, GameState.VICTORY, GameState.ADVERTISEMENT, GameState.UNKNOWN}
    ),
    GameState.VICTORY: frozenset(
        {
            GameState.VICTORY,
            GameState.PLAYING,
            GameState.HOME,
            GameState.ADVERTISEMENT,
            GameState.UNKNOWN,
        }
    ),
    GameState.ADVERTISEMENT: frozenset(GameState),
}


def is_valid_transition(previous: GameState, current: GameState) -> bool:
    """Return whether a state transition is valid for observation tracking."""
    return current in _TRANSITIONS[previous]


class StateDetector:
    """Map vision labels to stable, confidence-bearing game-state observations."""

    def __init__(self, *, minimum_confidence: float = 0.7, stable_observations: int = 2) -> None:
        if not 0 <= minimum_confidence <= 1:
            raise ValueError("minimum_confidence must be between zero and one")
        if stable_observations <= 0:
            raise ValueError("stable_observations must be positive")
        self.minimum_confidence = minimum_confidence
        self.stable_observations = stable_observations
        self._stable_state = GameState.UNKNOWN
        self._candidate = GameState.UNKNOWN
        self._candidate_count = 0

    @property
    def stable_state(self) -> GameState:
        """Return the most recently confirmed state."""
        return self._stable_state

    def observe(
        self,
        classification: Classification | None,
        *,
        evidence: Mapping[str, str] | None = None,
    ) -> StateObservation:
        """Consume one neutral vision result without causing device input."""
        state, confidence = self._classify(classification)
        transition_valid = is_valid_transition(self._stable_state, state)
        if not transition_valid:
            state = GameState.UNKNOWN
            confidence = 0.0
        if state == self._candidate:
            self._candidate_count += 1
        else:
            self._candidate = state
            self._candidate_count = 1
        stable = self._candidate_count >= self.stable_observations
        if stable:
            self._stable_state = state
        return StateObservation(
            state=state,
            confidence=confidence,
            evidence=tuple(sorted((evidence or {}).items())),
            stable=stable,
            consecutive_observations=self._candidate_count,
            transition_valid=transition_valid,
        )

    def _classify(self, classification: Classification | None) -> tuple[GameState, float]:
        if classification is None or classification.confidence < self.minimum_confidence:
            return GameState.UNKNOWN, 0.0 if classification is None else classification.confidence
        return _LABELS.get(
            classification.label.casefold(), GameState.UNKNOWN
        ), classification.confidence
