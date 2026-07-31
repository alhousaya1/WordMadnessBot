"""Integration test for continuous verified solving across consecutive levels."""

from collections.abc import Sequence

from word_madness_bot.domain.enums import VisionEvidenceKind
from word_madness_bot.domain.models import (
    LevelDefinition,
    LevelReading,
    NormalizedPoint,
    SwipeLetter,
    SwipePath,
    VisionEvidence,
)
from word_madness_bot.gameplay.ad_policy import AdvertisementPolicy
from word_madness_bot.gameplay.commands import CommandOutcome, SubmitWordDecision
from word_madness_bot.gameplay.decision_engine import DecisionEngine
from word_madness_bot.gameplay.level_solver import LevelSolver
from word_madness_bot.gameplay.progress import LevelProgress
from word_madness_bot.gameplay.recovery_policy import RecoveryPolicy
from word_madness_bot.gameplay.state_machine import DecisionStateMachine
from word_madness_bot.state.classifier import StateClassifier


class MultiLevelRepository:
    def __init__(self) -> None:
        definitions = (
            LevelDefinition(1, ("A", "T"), ("AT", "TA")),
            LevelDefinition(2, ("I", "N"), ("IN",)),
        )
        self.levels = {level.number: level for level in definitions}

    def get_level(self, level_number: int) -> LevelDefinition | None:
        return self.levels.get(level_number)

    def contains(self, level_number: int) -> bool:
        return level_number in self.levels

    def find_levels_by_word(self, word: str) -> tuple[LevelDefinition, ...]:
        return tuple(level for level in self.levels.values() if word in level.words)

    def all_levels(self) -> tuple[LevelDefinition, ...]:
        return tuple(self.levels.values())


class SwipeContractStub:
    def generate(self, word: str, letters: Sequence[SwipeLetter]) -> SwipePath:
        return SwipePath((letters[0].coordinate, letters[1].coordinate), 100)


def _letters(first: str, second: str) -> tuple[SwipeLetter, ...]:
    return (
        SwipeLetter(first, NormalizedPoint(0.25, 0.5)),
        SwipeLetter(second, NormalizedPoint(0.75, 0.5)),
    )


def test_multiple_consecutive_levels_submit_each_word_once() -> None:
    progress = LevelProgress()
    engine = DecisionEngine(
        StateClassifier(),
        LevelSolver(MultiLevelRepository(), SwipeContractStub(), progress),
        AdvertisementPolicy(),
        RecoveryPolicy(),
        DecisionStateMachine(),
    )
    evidence = (VisionEvidence(VisionEvidenceKind.LETTER_WHEEL, 0.95),)
    revision = 1
    submitted: list[str] = []
    for level_number, letters, word_count in (
        (1, _letters("A", "T"), 2),
        (2, _letters("I", "N"), 1),
    ):
        for _ in range(word_count):
            observation = engine.observe(
                evidence,
                revision=revision,
                level=LevelReading(level_number, 0.9, str(level_number)),
                letters=letters,
            )
            decision = engine.decide(observation)
            assert isinstance(decision, SubmitWordDecision)
            submitted.append(decision.word)
            command = engine.create_command(decision, revision)
            revision += 1
            verified = engine.observe(
                evidence,
                revision=revision,
                level=LevelReading(level_number, 0.9, str(level_number)),
                letters=letters,
            )
            assert engine.verify(command, CommandOutcome(command.identifier, True), verified)
        revision += 1

    assert submitted == ["AT", "TA", "IN"]
