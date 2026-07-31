"""Integration scenarios for missing data, OCR failure, ads, and retry recovery."""

from collections.abc import Sequence

from word_madness_bot.domain.enums import RecoveryFailure, VisionEvidenceKind
from word_madness_bot.domain.models import (
    LevelDefinition,
    LevelReading,
    NormalizedPoint,
    SwipeLetter,
    SwipePath,
    VisionEvidence,
)
from word_madness_bot.gameplay.actions import CompleteAction, TapAction
from word_madness_bot.gameplay.ad_policy import AdvertisementPolicy
from word_madness_bot.gameplay.commands import (
    AdvertisementActionDecision,
    CommandOutcome,
    EscalateDecision,
    RetryDecision,
    SubmitWordDecision,
)
from word_madness_bot.gameplay.decision_engine import DecisionEngine
from word_madness_bot.gameplay.level_solver import LevelSolver
from word_madness_bot.gameplay.progress import LevelProgress
from word_madness_bot.gameplay.recovery_policy import RecoveryPolicy
from word_madness_bot.gameplay.state_machine import DecisionStateMachine
from word_madness_bot.state.classifier import StateClassifier


class Repository:
    def get_level(self, level_number: int) -> LevelDefinition | None:
        return LevelDefinition(1, ("A", "T"), ("AT",)) if level_number == 1 else None

    def contains(self, level_number: int) -> bool:
        return level_number == 1

    def find_levels_by_word(self, word: str) -> tuple[LevelDefinition, ...]:
        return ()

    def all_levels(self) -> tuple[LevelDefinition, ...]:
        return ()


class Swipe:
    def generate(self, word: str, letters: Sequence[SwipeLetter]) -> SwipePath:
        return SwipePath((letters[0].coordinate, letters[1].coordinate), 100)


def _engine(retries: int = 1) -> DecisionEngine:
    return DecisionEngine(
        StateClassifier(),
        LevelSolver(Repository(), Swipe(), LevelProgress()),
        AdvertisementPolicy(initial_wait_seconds=0.0),
        RecoveryPolicy(retries),
        DecisionStateMachine(),
    )


def _letters() -> tuple[SwipeLetter, ...]:
    return (
        SwipeLetter("A", NormalizedPoint(0.2, 0.5)),
        SwipeLetter("T", NormalizedPoint(0.8, 0.5)),
    )


def _playing() -> tuple[VisionEvidence, ...]:
    return (VisionEvidence(VisionEvidenceKind.LETTER_WHEEL, 0.95),)


def test_missing_database_and_ocr_failures_are_bounded() -> None:
    missing_database_engine = _engine()
    missing = missing_database_engine.observe(
        _playing(), revision=1, level=LevelReading(99, 0.9, "99"), letters=_letters()
    )
    assert isinstance(missing_database_engine.decide(missing), RetryDecision)
    exhausted = missing_database_engine.decide(missing)
    assert isinstance(exhausted, EscalateDecision)
    assert exhausted.failure is RecoveryFailure.LEVEL_NOT_FOUND

    ocr_engine = _engine()
    unreadable = ocr_engine.observe(_playing(), revision=1, letters=_letters())
    assert isinstance(ocr_engine.decide(unreadable), RetryDecision)
    assert isinstance(ocr_engine.decide(unreadable), EscalateDecision)


def test_advertisement_interrupts_and_is_verified_through_policy() -> None:
    engine = _engine()
    close = VisionEvidence(
        VisionEvidenceKind.ADVERTISEMENT_CLOSE_CONTROL,
        0.95,
        normalized_location=NormalizedPoint(0.9, 0.1),
    )
    ad = engine.observe(
        (VisionEvidence(VisionEvidenceKind.ADVERTISEMENT_INDICATOR, 0.95), close), revision=5
    )
    selected = engine.decide(ad)
    assert isinstance(selected, AdvertisementActionDecision)
    assert isinstance(selected.action, TapAction)

    playing = engine.observe(
        _playing(), revision=6, level=LevelReading(1, 0.9, "1"), letters=_letters()
    )
    completed = engine.decide(playing)
    assert isinstance(completed, AdvertisementActionDecision)
    assert isinstance(completed.action, CompleteAction)
    assert isinstance(engine.decide(playing), SubmitWordDecision)


def test_failed_word_command_retries_same_word_then_recovers() -> None:
    engine = _engine(retries=2)
    observation = engine.observe(
        _playing(), revision=1, level=LevelReading(1, 0.9, "1"), letters=_letters()
    )
    decision = engine.decide(observation)
    assert isinstance(decision, SubmitWordDecision)
    command = engine.create_command(decision, 1)
    newer = engine.observe(
        _playing(), revision=2, level=LevelReading(1, 0.9, "1"), letters=_letters()
    )
    assert not engine.verify(command, CommandOutcome(command.identifier, False), newer)
    retried = engine.decide(newer)
    assert isinstance(retried, SubmitWordDecision)
    assert retried.word == decision.word
