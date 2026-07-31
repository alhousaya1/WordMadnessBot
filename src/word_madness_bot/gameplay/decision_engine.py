"""Decision engine orchestrating existing contracts without executing commands."""

import logging
from collections.abc import Sequence
from dataclasses import replace

from word_madness_bot.contracts.state import GameStateDetector
from word_madness_bot.domain.enums import EngineState, GameState, RecoveryFailure
from word_madness_bot.domain.errors import SwipePlanningError
from word_madness_bot.domain.models import (
    AdvertisementContext,
    LevelReading,
    RuntimeObservation,
    SwipeLetter,
    VisionEvidence,
)
from word_madness_bot.gameplay.actions import CompleteAction, EscalateAction
from word_madness_bot.gameplay.ad_policy import AdvertisementPolicy
from word_madness_bot.gameplay.commands import (
    AdvertisementActionDecision,
    CommandOutcome,
    EngineCommand,
    EngineDecision,
    EscalateDecision,
    ObserveDecision,
    RetryDecision,
    SubmitWordDecision,
)
from word_madness_bot.gameplay.level_solver import LevelSolver
from word_madness_bot.gameplay.recovery_policy import RecoveryPolicy
from word_madness_bot.gameplay.state_machine import DecisionStateMachine

_LOGGER = logging.getLogger(__name__)


class DecisionEngine:
    """Separate observation, decision, command creation, and verification steps."""

    def __init__(
        self,
        state_detector: GameStateDetector,
        level_solver: LevelSolver,
        advertisement_policy: AdvertisementPolicy,
        recovery_policy: RecoveryPolicy,
        state_machine: DecisionStateMachine,
    ) -> None:
        self._state_detector = state_detector
        self._level_solver = level_solver
        self._advertisement_policy = advertisement_policy
        self._recovery_policy = recovery_policy
        self._state_machine = state_machine
        self._next_command_identifier = 1
        self._advertisement_context: AdvertisementContext | None = None
        self._advertisement_started_at: float | None = None

    def observe(
        self,
        evidence: Sequence[VisionEvidence],
        *,
        revision: int,
        level: LevelReading | None = None,
        letters: tuple[SwipeLetter, ...] = (),
        elapsed_seconds: float = 0.0,
    ) -> RuntimeObservation:
        """Obtain screen state only through State and package existing Vision results."""

        state = self._state_detector.classify(evidence)
        return RuntimeObservation(revision, state, level, letters, elapsed_seconds)

    def decide(self, observation: RuntimeObservation) -> EngineDecision:
        """Choose one decision from the explicit state and current verified progress."""

        state = observation.state.state
        if state is GameState.ADVERTISEMENT or self._advertisement_context is not None:
            self._state_machine.transition(EngineState.HANDLING_ADVERTISEMENT)
            return self._advertisement_decision(observation)
        if state is GameState.UNKNOWN:
            return self._recover(RecoveryFailure.UNKNOWN_STATE, "screen state is unknown")
        if state is GameState.HOME:
            self._state_machine.transition(EngineState.OBSERVING)
            return ObserveDecision("home screen requires a fresh playing observation")
        if state is GameState.VICTORY:
            self._state_machine.transition(EngineState.OBSERVING)
            return ObserveDecision("victory observed; wait for the next level")
        if self._state_machine.state is EngineState.VERIFYING_WORD:
            return ObserveDecision("pending word requires independent command verification")
        if observation.level is None:
            return self._recover(RecoveryFailure.LEVEL_READ_FAILED, "level reading is unavailable")
        if not observation.letters:
            return self._recover(
                RecoveryFailure.LETTERS_UNAVAILABLE, "wheel letters are unavailable"
            )
        if not self._level_solver.load(observation.level.number):
            return self._recover(
                RecoveryFailure.LEVEL_NOT_FOUND,
                f"level {observation.level.number} is absent from the repository",
            )
        self._recovery_policy.reset()
        self._state_machine.transition(EngineState.SOLVING_LEVEL)
        try:
            decision = self._level_solver.next_decision(observation.letters)
        except SwipePlanningError as error:
            return self._recover(RecoveryFailure.WORD_COMMAND_FAILED, str(error))
        if decision is None:
            return ObserveDecision("all unique words submitted; await level transition")
        return decision

    def create_command(self, decision: EngineDecision, observation_revision: int) -> EngineCommand:
        """Convert a decision into a typed command without executing it."""

        command = EngineCommand(self._next_command_identifier, observation_revision, decision)
        self._next_command_identifier += 1
        if isinstance(decision, SubmitWordDecision):
            self._state_machine.transition(EngineState.VERIFYING_WORD)
        return command

    def verify(
        self,
        command: EngineCommand,
        outcome: CommandOutcome,
        new_observation: RuntimeObservation,
    ) -> bool:
        """Verify an external command only against its outcome and a newer observation."""

        if outcome.command_identifier != command.identifier:
            raise ValueError("command outcome identifier does not match")
        if new_observation.revision <= command.observation_revision:
            return False
        if isinstance(command.decision, SubmitWordDecision):
            self._level_solver.verify_word(outcome.succeeded)
            if outcome.succeeded:
                self._state_machine.transition(EngineState.SOLVING_LEVEL)
                self._recovery_policy.reset(RecoveryFailure.WORD_COMMAND_FAILED)
                return True
            self._state_machine.transition(EngineState.RECOVERING)
            return False
        return outcome.succeeded

    def _advertisement_decision(self, observation: RuntimeObservation) -> EngineDecision:
        if self._advertisement_context is None:
            self._advertisement_started_at = observation.elapsed_seconds
            self._advertisement_context = AdvertisementContext(
                observation_revision=observation.revision,
                elapsed_seconds=0.0,
            )
        else:
            started_at = self._advertisement_started_at or 0.0
            self._advertisement_context = replace(
                self._advertisement_context,
                observation_revision=observation.revision,
                elapsed_seconds=max(0.0, observation.elapsed_seconds - started_at),
            )
        selected = self._advertisement_policy.decide(
            observation.state,
            self._advertisement_context,
        )
        self._advertisement_context = selected.context
        if isinstance(selected.action, CompleteAction):
            self._advertisement_context = None
            self._advertisement_started_at = None
            self._state_machine.transition(EngineState.OBSERVING)
        elif isinstance(selected.action, EscalateAction):
            self._state_machine.transition(EngineState.RECOVERING)
        return AdvertisementActionDecision(selected.action)

    def _recover(self, failure: RecoveryFailure, detail: str) -> RetryDecision | EscalateDecision:
        self._state_machine.transition(EngineState.RECOVERING)
        decision = self._recovery_policy.decide(failure, detail)
        _LOGGER.warning(
            "Decision recovery selected",
            extra={
                "event": "decision_recovery",
                "failure": failure.value,
                "decision": type(decision).__name__,
            },
        )
        return decision
