from __future__ import annotations

import io
from pathlib import Path

import pytest

from word_madness_bot.application.level_executor import LevelExecutor
from word_madness_bot.application.solution_planning import LevelSolutionPlan, PlannedSolution
from word_madness_bot.application.word_execution import AcceptanceResult, WordExecutionResult
from word_madness_bot.config.logging import configure_logging
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
        self.verifications: list[bool] = []

    def execute(
        self,
        plan: LevelSolutionPlan,
        before: ScreenCapture,
        debug_directory: Path,
        *,
        verify: bool = True,
    ) -> WordExecutionResult:
        solution = plan.solutions[0]
        self.words.append(solution.word)
        self.durations.append(solution.duration_ms)
        self.coordinates.append(solution.coordinates)
        self.verifications.append(verify)
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
            float(len(self.words) - 1),
            float(len(self.words)),
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
    assert words.durations == [250, 360]
    assert words.verifications == [False, True]
    assert words.coordinates == [
        (PixelPoint(1, 2), PixelPoint(3, 4)),
        (PixelPoint(5, 6),),
    ]
    assert [word.word for word in result.words] == ["AB", "CAB"]
    assert result.home_capture is CAPTURE
    assert android.captures == 2
    assert sleeps == [0.1, 1.0, 0.5, 0.5]


def test_next_swipe_starts_when_previous_backend_returns(tmp_path: Path) -> None:
    stream = io.StringIO()
    words = WordExecutor((True, True))
    LevelExecutor(
        Android(),  # type: ignore[arg-type]
        words,  # type: ignore[arg-type]
        Classifier(ScreenType.HOME_SCREEN),
        logger=configure_logging(name="test.inter.word.gap", stream=stream),
        sleeper=lambda _: None,
    ).execute(_plan(), CAPTURE, tmp_path)

    output = stream.getvalue()
    assert '"previous_word": "AB"' in output
    assert '"next_word": "CAB"' in output
    assert '"previous_swipe_finished_timestamp": 1.0' in output
    assert '"next_swipe_started_timestamp": 1.0' in output
    assert '"inter_word_gap_ms": 0.0' in output


def test_preserves_per_word_planned_duration(tmp_path: Path) -> None:
    words = WordExecutor((True, True))
    LevelExecutor(
        Android(),  # type: ignore[arg-type]
        words,  # type: ignore[arg-type]
        Classifier(ScreenType.HOME_SCREEN),
        sleeper=lambda _: None,
    ).execute(_plan(), CAPTURE, tmp_path)

    assert words.durations == [250, 360]


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
    assert words.durations == [250, 360]
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
        Classifier(
            ScreenType.UNKNOWN,
            ScreenType.UNKNOWN,
            ScreenType.HOME_SCREEN,
        ),
        PopupDetector(popup, popup, None),
        sleeper=sleeps.append,
    )

    executor.execute(_plan(), CAPTURE, tmp_path)

    assert android.taps == [PixelPoint(320, 40), PixelPoint(320, 40)]
    assert sleeps == [0.1, 1.0, 0.5, 0.5, 0.5]


class CompletionOverlayDetector:
    def __init__(
        self,
        tap_to_continue: tuple[bool, ...] = (),
        daily_celebration: tuple[bool, ...] = (),
        completion_home: tuple[bool, ...] = (),
        settings: tuple[bool, ...] = (),
    ) -> None:
        self.tap_to_continue = iter(tap_to_continue)
        self.daily_celebration = iter(daily_celebration)
        self.completion_home = iter(completion_home)
        self.settings = iter(settings)

    def tap_to_continue_visible(self, capture: ScreenCapture) -> bool:
        return next(self.tap_to_continue, False)

    def daily_celebration_visible(self, capture: ScreenCapture) -> bool:
        return next(self.daily_celebration, False)

    def completion_home_visible(self, capture: ScreenCapture) -> bool:
        return next(self.completion_home, False)

    def settings_visible(self, capture: ScreenCapture) -> bool:
        return next(self.settings, False)


def test_recovers_completion_overlays_in_priority_order(tmp_path: Path) -> None:
    android = Android()
    sleeps: list[float] = []
    popup = PixelRect(300, 20, 40, 40)
    executor = LevelExecutor(
        android,  # type: ignore[arg-type]
        WordExecutor((True, True)),  # type: ignore[arg-type]
        Classifier(
            ScreenType.UNKNOWN,
            ScreenType.UNKNOWN,
            ScreenType.UNKNOWN,
            ScreenType.HOME_SCREEN,
        ),
        PopupDetector(popup, None),
        CompletionOverlayDetector(
            (True, False, False, False),
            (True, False, False),
        ),
        sleeper=sleeps.append,
    )

    executor.execute(_plan(), CAPTURE, tmp_path)

    assert android.taps == [
        PixelPoint(200, 719),
        PixelPoint(20, 56),
        PixelPoint(320, 40),
    ]
    assert android.captures == 4
    assert sleeps == [0.1, 1.0, 0.5, 0.5, 0.5, 0.5]


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


def test_completion_home_takes_ownership_before_arrow_handlers(tmp_path: Path) -> None:
    android = Android()
    detector = CompletionOverlayDetector(
        tap_to_continue=(True,),
        daily_celebration=(True,),
        completion_home=(True,),
    )
    executor = LevelExecutor(
        android,  # type: ignore[arg-type]
        WordExecutor((True, True)),  # type: ignore[arg-type]
        Classifier(ScreenType.UNKNOWN),
        PopupDetector(PixelRect(300, 20, 40, 40)),
        detector,
        sleeper=lambda _: None,
    )

    executor.execute(_plan(), CAPTURE, tmp_path)

    assert android.taps == []
    assert next(detector.tap_to_continue) is True
    assert next(detector.daily_celebration) is True


def test_normal_home_takes_ownership_before_arrow_handlers(tmp_path: Path) -> None:
    android = Android()
    detector = CompletionOverlayDetector(daily_celebration=(True,))
    executor = LevelExecutor(
        android,  # type: ignore[arg-type]
        WordExecutor((True, True)),  # type: ignore[arg-type]
        Classifier(ScreenType.HOME_SCREEN),
        PopupDetector(PixelRect(300, 20, 40, 40)),
        detector,
        sleeper=lambda _: None,
    )

    executor.execute(_plan(), CAPTURE, tmp_path)

    assert android.taps == []
    assert next(detector.daily_celebration) is True


def test_settings_page_taps_back_once_then_returns_to_home(tmp_path: Path) -> None:
    android = Android()
    sleeps: list[float] = []
    executor = LevelExecutor(
        android,  # type: ignore[arg-type]
        WordExecutor((True, True)),  # type: ignore[arg-type]
        Classifier(ScreenType.UNKNOWN, ScreenType.HOME_SCREEN),
        PopupDetector(None),
        CompletionOverlayDetector(settings=(True,)),
        sleeper=sleeps.append,
    )

    executor.execute(_plan(), CAPTURE, tmp_path)

    assert android.taps == [PixelPoint(20, 56)]
    assert android.captures == 2
    assert sleeps == [0.1, 1.0, 0.5, 0.5]


def test_delay_occurs_only_between_successful_words(tmp_path: Path) -> None:
    events: list[tuple[str, object]] = []

    class OrderedAndroid(Android):
        def capture_screenshot(self) -> ScreenCapture:
            events.append(("capture", self.captures))
            return super().capture_screenshot()

    class OrderedWords(WordExecutor):
        def execute(
            self,
            plan: LevelSolutionPlan,
            before: ScreenCapture,
            debug_directory: Path,
            *,
            verify: bool = True,
        ) -> WordExecutionResult:
            events.append(("word", plan.solutions[0].word))
            return super().execute(plan, before, debug_directory, verify=verify)

    class OrderedClassifier(Classifier):
        def classify(self, capture: ScreenCapture) -> ScreenClassification:
            events.append(("classify", "home"))
            return super().classify(capture)

    words = OrderedWords((True, True))
    LevelExecutor(
        OrderedAndroid(),  # type: ignore[arg-type]
        words,  # type: ignore[arg-type]
        OrderedClassifier(ScreenType.HOME_SCREEN),
        completion_animation_wait_seconds=0,
        recovery_poll_seconds=0.5,
        sleeper=lambda seconds: events.append(("sleep", seconds)),
    ).execute(_plan(), CAPTURE, tmp_path)

    assert events[:3] == [("word", "AB"), ("sleep", 0.1), ("word", "CAB")]
    assert events[3:] == [("sleep", 0), ("sleep", 0.5), ("capture", 0), ("classify", "home")]
    assert words.words == ["AB", "CAB"]
    assert words.durations == [250, 360]


def test_replay_pass_uses_same_inter_word_delay_and_logging(tmp_path: Path) -> None:
    stream = io.StringIO()
    sleeps: list[float] = []
    words = WordExecutor((True, True, True, True))
    executor = LevelExecutor(
        Android(),  # type: ignore[arg-type]
        words,  # type: ignore[arg-type]
        Classifier(ScreenType.HOME_SCREEN, ScreenType.HOME_SCREEN),
        logger=configure_logging(name="test.inter.word.replay", stream=stream),
        sleeper=sleeps.append,
    )

    executor.execute(_plan(), CAPTURE, tmp_path, pass_number=1)
    executor.execute(_plan(), CAPTURE, tmp_path, pass_number=2)

    assert sleeps == [0.1, 1.0, 0.5, 0.1, 1.0, 0.5]
    assert words.words == ["AB", "CAB", "AB", "CAB"]
    output = stream.getvalue()
    assert output.count('"event": "runtime.word.inter_word_delay"') == 2
    assert '"completed_word": "AB"' in output
    assert '"next_word": "CAB"' in output
    assert '"delay_ms": 100' in output
    assert '"pass_number": 2' in output
    assert "runtime.level.first_word_ready_wait" not in output
