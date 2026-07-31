"""Stable contract tests for every documented game state."""

from word_madness_bot.domain.models import StateObservation
from word_madness_bot.domain.states import GameState


def test_all_documented_states_are_typed_and_observable() -> None:
    assert set(GameState) == {
        GameState.HOME,
        GameState.PLAYING,
        GameState.VICTORY,
        GameState.ADVERTISEMENT,
        GameState.UNKNOWN,
    }
    for state in GameState:
        assert StateObservation(state, 1.0, stable=True, consecutive_observations=1).state is state
