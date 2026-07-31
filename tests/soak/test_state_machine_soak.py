"""Bounded soak test for decision finite-state transition stability."""

from word_madness_bot.domain.enums import EngineState
from word_madness_bot.gameplay.state_machine import DecisionStateMachine


def test_state_machine_remains_deterministic_across_many_cycles() -> None:
    machine = DecisionStateMachine()
    for _ in range(10_000):
        machine.transition(EngineState.SOLVING_LEVEL)
        machine.transition(EngineState.VERIFYING_WORD)
        machine.transition(EngineState.SOLVING_LEVEL)
        machine.transition(EngineState.OBSERVING)
    assert machine.state is EngineState.OBSERVING
