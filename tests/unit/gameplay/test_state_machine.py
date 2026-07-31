"""Unit tests for explicit decision-engine finite-state transitions."""

import pytest

from word_madness_bot.domain.enums import EngineState
from word_madness_bot.gameplay.state_machine import DecisionStateMachine


def test_documented_transition_sequence_succeeds() -> None:
    machine = DecisionStateMachine()
    machine.transition(EngineState.SOLVING_LEVEL)
    machine.transition(EngineState.VERIFYING_WORD)
    machine.transition(EngineState.SOLVING_LEVEL)
    assert machine.state is EngineState.SOLVING_LEVEL


def test_undocumented_transition_is_rejected() -> None:
    machine = DecisionStateMachine()
    machine.transition(EngineState.STOPPED)
    with pytest.raises(ValueError, match="forbidden decision transition"):
        machine.transition(EngineState.SOLVING_LEVEL)
