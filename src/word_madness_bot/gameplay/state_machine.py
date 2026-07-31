"""Explicit finite-state machine for documented decision-engine transitions."""

import logging
from collections.abc import Mapping

from word_madness_bot.domain.enums import EngineState

_LOGGER = logging.getLogger(__name__)

_ALLOWED: Mapping[EngineState, frozenset[EngineState]] = {
    EngineState.OBSERVING: frozenset(
        {
            EngineState.OBSERVING,
            EngineState.SOLVING_LEVEL,
            EngineState.HANDLING_ADVERTISEMENT,
            EngineState.RECOVERING,
            EngineState.STOPPED,
        }
    ),
    EngineState.SOLVING_LEVEL: frozenset(
        {
            EngineState.SOLVING_LEVEL,
            EngineState.VERIFYING_WORD,
            EngineState.HANDLING_ADVERTISEMENT,
            EngineState.RECOVERING,
            EngineState.OBSERVING,
            EngineState.STOPPED,
        }
    ),
    EngineState.VERIFYING_WORD: frozenset(
        {EngineState.SOLVING_LEVEL, EngineState.RECOVERING, EngineState.STOPPED}
    ),
    EngineState.HANDLING_ADVERTISEMENT: frozenset(
        {
            EngineState.HANDLING_ADVERTISEMENT,
            EngineState.OBSERVING,
            EngineState.SOLVING_LEVEL,
            EngineState.RECOVERING,
            EngineState.STOPPED,
        }
    ),
    EngineState.RECOVERING: frozenset(
        {
            EngineState.RECOVERING,
            EngineState.OBSERVING,
            EngineState.SOLVING_LEVEL,
            EngineState.HANDLING_ADVERTISEMENT,
            EngineState.STOPPED,
        }
    ),
    EngineState.STOPPED: frozenset({EngineState.STOPPED}),
}


class DecisionStateMachine:
    """Reject every transition not present in the documented transition table."""

    def __init__(self) -> None:
        self._state = EngineState.OBSERVING

    @property
    def state(self) -> EngineState:
        """Return the current finite-state-machine state."""

        return self._state

    def transition(self, target: EngineState) -> None:
        """Move to an explicitly allowed state or raise a deterministic error."""

        if target not in _ALLOWED[self._state]:
            raise ValueError(
                f"forbidden decision transition: {self._state.value} -> {target.value}"
            )
        previous = self._state
        self._state = target
        _LOGGER.debug(
            "Decision state transition",
            extra={
                "event": "decision_transition",
                "source": previous.value,
                "target": target.value,
            },
        )
