from __future__ import annotations

from pathlib import Path

import pytest

from word_madness_bot.application.level_executor import LevelExecutor
from word_madness_bot.application.solution_planning import LevelSolutionPlan, PlannedSolution
from word_madness_bot.application.word_execution import AcceptanceResult, WordExecutionResult
from word_madness_bot.domain.errors import RuntimeTransitionError, WordExecutionError
from word_madness_bot.domain.geometry import PixelPoint, PixelRect, ScreenSize
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
        self.taps: list[PixelPoint] = []

    def capture_screenshot(self) -> ScreenCapture:
        self.captures += 1
        return CAPTURE

    def tap(self, point: PixelPoint) -> None:
        self.taps.append(point)

    def __getattr__(self, name: str) -> object:
        return lambda *args, **kwargs: None


class WordExecutor:
    def __init__(self, accepted: tuple[bool, ...]) -> None:
        self.accepted = iter(accepted)
        self.words: list[str] = []
        self.durations: list[int] = []
        self.coordinates: list[tuple[PixelPoint, ...]] = []

    def execute(
        self, plan: LevelSolutionPlan, before: ScreenCapture, debug_directory: Path
    ) -> WordExecutionResult:
        solution = plan.solutions[0]
        self.words.append(solution.word)
        self.durations.append(solution.duration_ms)
        self.coordinates.append(solution.coordinates)
        accepted = next(self.accepted)
        return WordExecutionResult(
            solution.word,
            solution.duration_ms,
            solution.coordinates,
            AcceptanceResult(accepted, 0.01 if accepted else 0.0, 1.0),
            1.0,
            (0, solution.duration_ms),
            ("fake",),
            CAPTURE,
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
    assert words.durations == [500, 500]
    assert words.coordinates == [
        (PixelPoint(1, 2), PixelPoint(3, 4)),
        (PixelPoint(5, 6),),
    ]
    assert [word.word for word in result.words] == ["AB", "CAB"]
    assert result.home_capture is CAPTURE
    assert android.captures == 2
    assert sleeps == [1.0, 0.5, 0.5]


def test_runtime_swipe_duration_is_configurable(tmp_path: Path) -> None:
    android = Android()
    words = WordExecutor((True, True))
    executor = LevelExecutor(
        android,  # type: ignore[arg-type]
        words,  # type: ignore[arg-type]
        Classifier(ScreenType.HOME_SCREEN),
        swipe_duration_ms=750,
        sleeper=lambda _: None,
    )

    executor.execute(_plan(), CAPTURE, tmp_path)

    assert words.durations == [750, 750]


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
    assert words.durations == [500, 500]
    assert words.coordinates == [
        (PixelPoint(1, 2), PixelPoint(3, 4)),
        (PixelPoint(5, 6),),
    ]
    assert android.captures == 0


class PopupDetector:
    def __init__(self, *results: PixelRect | None) -> None:
        self.results = iter(results)

    def detect(self, capture: ScreenCapture) -> PixelRect | None:
        return next(self.results)


def test_dismisses_reappearing_popup_until_it_is_gone(tmp_path: Path) -> None:
    android = Android()
    words = WordExecutor((True, True))
    sleeps: list[float] = []
    popup = PixelRect(300, 20, 40, 40)
    executor = LevelExecutor(
        android,  # type: ignore[arg-type]
        words,  # type: ignore[arg-type]
        Classifier(ScreenType.HOME_SCREEN),
        PopupDetector(popup, popup, None),
        sleeper=sleeps.append,
    )

    executor.execute(_plan(), CAPTURE, tmp_path)

    assert android.taps == [PixelPoint(320, 40), PixelPoint(320, 40)]
    assert sleeps == [1.0, 0.5, 0.5, 0.5]


class CompletionOverlayDetector:
    def __init__(
        self,
        tap_to_continue: tuple[bool, ...],
        daily_celebration: tuple[bool, ...],
    ) -> None:
        self.tap_to_continue = iter(tap_to_continue)
        self.daily_celebration = iter(daily_celebration)

    def tap_to_continue_visible(self, capture: ScreenCapture) -> bool:
        return next(self.tap_to_continue)

    def daily_celebration_visible(self, capture: ScreenCapture) -> bool:
        return next(self.daily_celebration)


def test_recovers_completion_overlays_in_priority_order(tmp_path: Path) -> None:
    android = Android()
    sleeps: list[float] = []
    popup = PixelRect(300, 20, 40, 40)
    executor = LevelExecutor(
        android,  # type: ignore[arg-type]
        WordExecutor((True, True)),  # type: ignore[arg-type]
        Classifier(ScreenType.HOME_SCREEN),
        PopupDetector(popup, None),
        CompletionOverlayDetector(
            (True, False, False, False),
            (True, False, False),
        ),
        sleeper=sleeps.append,
    )

    executor.execute(_plan(), CAPTURE, tmp_path)

    assert android.taps == [
        PixelPoint(200, 400),
        PixelPoint(20, 56),
        PixelPoint(320, 40),
    ]
    assert android.captures == 4
    assert sleeps == [1.0, 0.5, 0.5, 0.5, 0.5]


def test_raises_when_completion_recovery_exceeds_twenty_seconds(
    tmp_path: Path,
) -> None:
    android = Android()
    clock = iter((0.0, 0.0, 5.0, 10.0, 15.0, 20.0)).__next__
    executor = LevelExecutor(
        android,  # type: ignore[arg-type]
        WordExecutor((True, True)),  # type: ignore[arg-type]
        Classifier(
            ScreenType.LEVEL_SCREEN,
            ScreenType.LEVEL_SCREEN,
            ScreenType.LEVEL_SCREEN,
            ScreenType.LEVEL_SCREEN,
        ),
        recovery_timeout_seconds=20.0,
        clock=clock,
        sleeper=lambda _: None,
    )

    with pytest.raises(RuntimeTransitionError, match="within 20 seconds"):
        executor.execute(_plan(), CAPTURE, tmp_path)

    assert android.captures == 4
