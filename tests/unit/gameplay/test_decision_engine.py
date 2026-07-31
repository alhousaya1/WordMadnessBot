"""Unit tests for separated observation, decision, command, and verification."""

from collections.abc import Sequence

from word_madness_bot.domain.enums import GameState, RecoveryFailure, VisionEvidenceKind
from word_madness_bot.domain.models import (
    LevelDefinition,
    LevelReading,
    NormalizedPoint,
    SwipeLetter,
    SwipePath,
    VisionEvidence,
)
from word_madness_bot.gameplay.ad_policy import AdvertisementPolicy
from word_madness_bot.gameplay.commands import (
    CommandOutcome,
    EscalateDecision,
    ObserveDecision,
    RetryDecision,
    SubmitWordDecision,
)
from word_madness_bot.gameplay.decision_engine import DecisionEngine
from word_madness_bot.gameplay.level_solver import LevelSolver
from word_madness_bot.gameplay.progress import LevelProgress
from word_madness_bot.gameplay.recovery_policy import RecoveryPolicy
from word_madness_bot.gameplay.state_machine import DecisionStateMachine
from word_madness_bot.state.classifier import StateClassifier


class RepositoryStub:
    def __init__(self) -> None:
        self.levels = {1: LevelDefinition(1, ("A", "T"), ("AT", "TA"))}

    def get_level(self, level_number: int) -> LevelDefinition | None:
        return self.levels.get(level_number)

    def contains(self, level_number: int) -> bool:
        return level_number in self.levels

    def find_levels_by_word(self, word: str) -> tuple[LevelDefinition, ...]:
        return ()

    def all_levels(self) -> tuple[LevelDefinition, ...]:
        return tuple(self.levels.values())


class SwipeStub:
    def generate(self, word: str, letters: Sequence[SwipeLetter]) -> SwipePath:
        return SwipePath((letters[0].coordinate, letters[1].coordinate), 100)


def _engine(maximum_retries: int = 2) -> DecisionEngine:
    solver = LevelSolver(RepositoryStub(), SwipeStub(), LevelProgress())
    return DecisionEngine(
        StateClassifier(),
        solver,
        AdvertisementPolicy(),
        RecoveryPolicy(maximum_retries),
        DecisionStateMachine(),
    )


def _letters() -> tuple[SwipeLetter, ...]:
    return (
        SwipeLetter("A", NormalizedPoint(0.2, 0.5)),
        SwipeLetter("T", NormalizedPoint(0.8, 0.5)),
    )


def _playing_evidence() -> tuple[VisionEvidence, ...]:
    return (VisionEvidence(VisionEvidenceKind.LETTER_WHEEL, 0.95),)


def test_observation_uses_state_interface_and_decision_uses_contracts() -> None:
    engine = _engine()
    observation = engine.observe(
        _playing_evidence(), revision=1, level=LevelReading(1, 0.9, "1"), letters=_letters()
    )
    decision = engine.decide(observation)
    assert observation.state.state is GameState.PLAYING
    assert isinstance(decision, SubmitWordDecision)
    assert decision.word == "AT"


def test_command_creation_and_verification_are_independent() -> None:
    engine = _engine()
    first_observation = engine.observe(
        _playing_evidence(), revision=1, level=LevelReading(1, 0.9, "1"), letters=_letters()
    )
    decision = engine.decide(first_observation)
    command = engine.create_command(decision, first_observation.revision)
    newer = engine.observe(
        _playing_evidence(), revision=2, level=LevelReading(1, 0.9, "1"), letters=_letters()
    )
    assert not engine.verify(command, CommandOutcome(command.identifier, True), first_observation)
    assert engine.verify(command, CommandOutcome(command.identifier, True), newer)
    next_decision = engine.decide(newer)
    assert isinstance(next_decision, SubmitWordDecision)
    assert next_decision.word == "TA"


def test_missing_level_and_level_read_failure_use_bounded_recovery() -> None:
    engine = _engine(maximum_retries=1)
    missing_ocr = engine.observe(_playing_evidence(), revision=1, letters=_letters())
    first = engine.decide(missing_ocr)
    second = engine.decide(missing_ocr)
    assert isinstance(first, RetryDecision)
    assert first.failure is RecoveryFailure.LEVEL_READ_FAILED
    assert isinstance(second, EscalateDecision)


def test_home_and_victory_return_observation_commands_only() -> None:
    engine = _engine()
    home = engine.observe((VisionEvidence(VisionEvidenceKind.HOME_INDICATOR, 0.9),), revision=1)
    victory = engine.observe((VisionEvidence(VisionEvidenceKind.VICTORY_BANNER, 0.9),), revision=2)
    assert isinstance(engine.decide(home), ObserveDecision)
    assert isinstance(engine.decide(victory), ObserveDecision)
