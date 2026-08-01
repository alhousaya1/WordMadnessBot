from __future__ import annotations

from pathlib import Path

import pytest

from word_madness_bot.application.level_executor import LevelExecutor
from word_madness_bot.application.solution_planning import LevelSolutionPlan, PlannedSolution
from word_madness_bot.application.word_execution import AcceptanceResult, WordExecutionResult
from word_madness_bot.domain.errors import WordExecutionError
from word_madness_bot.domain.geometry import PixelPoint, ScreenSize
from word_madness_bot.domain.models import ScreenCapture
from word_madness_bot.vision.screen_classifier import ScreenClassification, ScreenType

CAPTURE = ScreenCapture(b"capture", ScreenSize(400, 800))


def _plan() -> LevelSolutionPlan:
    return LevelSolutionPlan(
        1,
        tuple("ABC"),
        (
            PlannedSolution("AB", (0, 1), (PixelPoint(1, 2), PixelPoint(3, 4)), 250),
            PlannedSolution("CAB", (2, 0, 1), (PixelPoint(5, 6),), 360),
        ),
    )


class Android:
    def __init__(self) -> None:
        self.captures = 0

    def capture_screenshot(self) -> ScreenCapture:
        self.captures += 1
        return CAPTURE

    def __getattr__(self, name: str) -> object:
        return lambda *args, **kwargs: None


class WordExecutor:
    def __init__(self, accepted: tuple[bool, ...]) -> None:
        self.accepted = iter(accepted)
        self.words: list[str] = []

    def execute(
        self, plan: LevelSolutionPlan, before: ScreenCapture, debug_directory: Path
    ) -> WordExecutionResult:
        solution = plan.solutions[0]
        self.words.append(solution.word)
        accepted = next(self.accepted)
        return WordExecutionResult(
            solution.word,
            solution.duration_ms,
            solution.coordinates,
            AcceptanceResult(accepted, 0.01 if accepted else 0.0, 1.0),
            1.0,
            (0, solution.duration_ms),
            ("fake",),
        )


class Classifier:
    def __init__(self, *screens: ScreenType) -> None:
        self.screens = iter(screens)

    def classify(self, capture: ScreenCapture) -> ScreenClassification:
        return ScreenClassification(next(self.screens), 0.99)


def test_executes_every_word_then_waits_until_home(tmp_path: Path) -> None:
    android = Android()
    words = WordExecutor((True, True))
    sleeps: list[float] = []
    executor = LevelExecutor(
        android,  # type: ignore[arg-type]
        words,  # type: ignore[arg-type]
        Classifier(ScreenType.LEVEL_SCREEN, ScreenType.HOME_SCREEN),
        sleeper=sleeps.append,
    )

    result = executor.execute(_plan(), CAPTURE, tmp_path)

    assert words.words == ["AB", "CAB"]
    assert [word.word for word in result.words] == ["AB", "CAB"]
    assert result.home_capture is CAPTURE
    assert android.captures == 3
    assert sleeps == [2.0, 0.5]


def test_stops_immediately_when_a_word_is_rejected(tmp_path: Path) -> None:
    android = Android()
    words = WordExecutor((True, False))
    executor = LevelExecutor(
        android,  # type: ignore[arg-type]
        words,  # type: ignore[arg-type]
        Classifier(),
        sleeper=lambda _: None,
    )

    with pytest.raises(WordExecutionError, match="CAB"):
        executor.execute(_plan(), CAPTURE, tmp_path)

    assert words.words == ["AB", "CAB"]
    assert android.captures == 1