"""Unit tests for contract-only level solving and progress."""

from word_madness_bot.domain.models import (
    LevelDefinition,
    NormalizedPoint,
    SwipeLetter,
    SwipePath,
)
from word_madness_bot.gameplay.level_solver import LevelSolver
from word_madness_bot.gameplay.progress import LevelProgress


class RepositoryStub:
    def __init__(self, levels: tuple[LevelDefinition, ...]) -> None:
        self.levels = {level.number: level for level in levels}

    def get_level(self, level_number: int) -> LevelDefinition | None:
        return self.levels.get(level_number)

    def contains(self, level_number: int) -> bool:
        return level_number in self.levels

    def find_levels_by_word(self, word: str) -> tuple[LevelDefinition, ...]:
        return tuple(level for level in self.levels.values() if word in level.words)

    def all_levels(self) -> tuple[LevelDefinition, ...]:
        return tuple(self.levels.values())


class SwipeStub:
    def generate(self, word: str, letters: tuple[SwipeLetter, ...]) -> SwipePath:
        return SwipePath((letters[0].coordinate, letters[1].coordinate), 100)


def _solver() -> LevelSolver:
    level = LevelDefinition(1, ("A", "T"), ("AT", "TA"))
    return LevelSolver(RepositoryStub((level,)), SwipeStub(), LevelProgress())


def _letters() -> tuple[SwipeLetter, ...]:
    return (
        SwipeLetter("A", NormalizedPoint(0.2, 0.5)),
        SwipeLetter("T", NormalizedPoint(0.8, 0.5)),
    )


def test_solver_reads_repository_and_swipe_contracts_only() -> None:
    solver = _solver()
    assert solver.load(1)
    decision = solver.next_decision(_letters())
    assert decision is not None and decision.word == "AT"


def test_successful_verification_prevents_duplicate_submission() -> None:
    solver = _solver()
    solver.load(1)
    first = solver.next_decision(_letters())
    assert first is not None
    solver.verify_word(True)
    second = solver.next_decision(_letters())
    assert second is not None and second.word == "TA"
    assert "AT" in solver.progress.submitted_words


def test_pending_word_cannot_be_created_twice() -> None:
    solver = _solver()
    solver.load(1)
    assert solver.next_decision(_letters()) is not None
    assert solver.next_decision(_letters()) is None


def test_missing_level_returns_false() -> None:
    assert not _solver().load(999)
