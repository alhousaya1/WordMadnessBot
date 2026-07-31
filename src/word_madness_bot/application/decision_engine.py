"""Pure decisions over stable game-state observations."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

from word_madness_bot.domain.models import StateObservation
from word_madness_bot.domain.states import GameState


class Action(StrEnum):
    """High-level actions selected without performing I/O."""

    START_LEVEL = "start_level"
    PLAY_LEVEL = "play_level"
    ADVANCE = "advance"
    HANDLE_ADVERTISEMENT = "handle_advertisement"
    WAIT = "wait"


@dataclass(frozen=True, slots=True)
class Decision:
    """One explainable action selected from a state observation."""

    action: Action
    reason: str


class DecisionEngine:
    """Select the next action without OCR, device, or repository access."""

    def decide(self, observation: StateObservation) -> Decision:
        """Map a stable state to its adjacent workflow action."""
        if not observation.stable:
            return Decision(Action.WAIT, "state is not stable")
        actions = {
            GameState.HOME: Decision(Action.START_LEVEL, "home screen is ready"),
            GameState.PLAYING: Decision(Action.PLAY_LEVEL, "level is active"),
            GameState.VICTORY: Decision(Action.ADVANCE, "victory is confirmed"),
            GameState.ADVERTISEMENT: Decision(
                Action.HANDLE_ADVERTISEMENT, "advertisement requires bounded dismissal"
            ),
            GameState.UNKNOWN: Decision(Action.WAIT, "state is unknown"),
        }
        return actions[observation.state]
