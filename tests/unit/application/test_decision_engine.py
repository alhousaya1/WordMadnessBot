"""Unit tests for state-to-action decisions."""

import pytest

from word_madness_bot.application.decision_engine import Action, DecisionEngine
from word_madness_bot.domain.models import StateObservation
from word_madness_bot.domain.states import GameState


@pytest.mark.parametrize(
    ("state", "action"),
    [
        (GameState.HOME, Action.START_LEVEL),
        (GameState.PLAYING, Action.PLAY_LEVEL),
        (GameState.VICTORY, Action.ADVANCE),
        (GameState.ADVERTISEMENT, Action.HANDLE_ADVERTISEMENT),
        (GameState.UNKNOWN, Action.WAIT),
    ],
)
def test_action_for_every_state(state: GameState, action: Action) -> None:
    assert DecisionEngine().decide(StateObservation(state, 1, stable=True)).action is action


def test_unstable_state_waits() -> None:
    assert DecisionEngine().decide(StateObservation(GameState.PLAYING, 0.9)).action is Action.WAIT
