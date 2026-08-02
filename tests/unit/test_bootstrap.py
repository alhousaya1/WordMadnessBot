from __future__ import annotations

import io
import logging
import struct
from collections.abc import Callable
from pathlib import Path
from typing import cast

import pytest

from word_madness_bot.application.ports.android import AndroidPort
from word_madness_bot.application.word_execution import AcceptanceResult
from word_madness_bot.bootstrap import ApplicationRuntime, build_runtime
from word_madness_bot.config.logging import StructuredLogger, configure_logging
from word_madness_bot.config.settings import Settings
from word_madness_bot.domain.errors import (
    OcrError,
    ScreenshotError,
    WheelGeometryDetectionError,
    WordNotAcceptedError,
)
from word_madness_bot.domain.geometry import PixelPoint, PixelRect, ScreenSize
from word_madness_bot.domain.models import (
    DeviceDescriptor,
    DeviceState,
    ScreenCapture,
    SwipeExecutionReceipt,
    SwipePath,
)
from word_madness_bot.infrastructure.levels.json_repository import JsonLevelRepository
from word_madness_bot.vision.letter_recognition import (
    RecognizedLetter,
    WheelLetterRecognition,
    WheelLetterRecognitionPort,
)
from word_madness_bot.vision.level_number import LevelNumberRecognitionPort
from word_madness_bot.vision.screen_classifier import ScreenClassification, ScreenType
from word_madness_bot.vision.wheel_geometry import (
    LetterPosition,
    LetterWheelGeometry,
    WheelGeometryDetector,
)

PNG = b"\x89PNG\r\n\x1a\n" + b"\x00\x00\x00\rIHDR" + struct.pack(">II", 1080, 2400)


class FakeAndroid:
    def __init__(self, screenshot: bytes = PNG) -> None:
        self.selected = 0
        self.verified = 0
        self.captures = 0
        self.screenshot = screenshot
        self.taps: list[PixelPoint] = []
        self.swipes: list[SwipePath] = []

    def select_device(self, serial: str | None = None) -> DeviceDescriptor:
        self.selected += 1
        return DeviceDescriptor(serial or "test", DeviceState.ONLINE)

    def verify_connection(self) -> bool:
        self.verified += 1
        return True

    def capture_screenshot(self) -> ScreenCapture:
        self.captures += 1
        return ScreenCapture(self.screenshot, ScreenSize(1080, 2400))

    def tap(self, point: PixelPoint) -> None:
        self.taps.append(point)

    def swipe(self, path: SwipePath) -> SwipeExecutionReceipt:
        self.swipes.append(path)
        return SwipeExecutionReceipt(("fake",), (0, path.duration_ms))


class FakeWheelDetector:
    def __init__(self, *, fail: bool = False) -> None:
        self.fail = fail
        self.calls = 0

    def detect(self, capture: ScreenCapture) -> LetterWheelGeometry:
        self.calls += 1
        if self.fail:
            raise WheelGeometryDetectionError("wheel missing")
        return LetterWheelGeometry(
            center=PixelPoint(540, 1800),
            radius=300,
            letters=(
                LetterPosition(0, PixelPoint(540, 1550)),
                LetterPosition(1, PixelPoint(760, 1900)),
                LetterPosition(2, PixelPoint(320, 1900)),
            ),
        )

    def annotate(self, capture: ScreenCapture, geometry: LetterWheelGeometry) -> bytes:
        return PNG


class FakeLetterRecognizer:
    def __init__(self, *, fail: bool = False) -> None:
        self.fail = fail
        self.calls = 0

    def recognize(
        self,
        capture: ScreenCapture,
        geometry: LetterWheelGeometry,
        debug_directory: Path,
    ) -> WheelLetterRecognition:
        self.calls += 1
        if self.fail:
            raise OcrError("letters missing")
        return WheelLetterRecognition(
            tuple(
                RecognizedLetter(
                    index=position.index,
                    character=character,
                    confidence=0.9,
                    elapsed_seconds=0.01,
                    crop_path=debug_directory / "letters" / f"letter-{position.index}.png",
                )
                for position, character in zip(geometry.letters, "ABC", strict=True)
            )
        )


class FakeLevelNumberRecognizer:
    def __init__(self, number: int = 1) -> None:
        self.number = number
        self.calls = 0

    def recognize(self, capture: ScreenCapture) -> int:
        self.calls += 1
        return self.number


class FakeCompletionOverlayDetector:
    def __init__(self, *completion_home: bool) -> None:
        self.completion_home = iter(completion_home)

    def tap_to_continue_visible(self, capture: ScreenCapture) -> bool:
        return False

    def daily_celebration_visible(self, capture: ScreenCapture) -> bool:
        return False

    def completion_home_visible(self, capture: ScreenCapture) -> bool:
        return next(self.completion_home, False)

    def settings_visible(self, capture: ScreenCapture) -> bool:
        return False


class FakePopupCloseDetector:
    def detect(self, capture: ScreenCapture) -> PixelRect | None:
        return None


class FakeAcceptanceVerifier:
    def __init__(self, *, accepted: bool = True) -> None:
        self.accepted = accepted
        self.calls = 0

    def verify(
        self, before: ScreenCapture, after: ScreenCapture, confirmation: ScreenCapture
    ) -> AcceptanceResult:
        self.calls += 1
        return AcceptanceResult(self.accepted, 0.01 if self.accepted else 0.0, 1.0)


class FakeClassifier:
    def __init__(self, *results: ScreenClassification) -> None:
        home = ScreenClassification(ScreenType.HOME_SCREEN, 0.99)
        level = ScreenClassification(ScreenType.LEVEL_SCREEN, 0.99)
        self.results = iter(results or (home, level, home))
        self.fallback = ScreenClassification(
            ScreenType.HOME_SCREEN,
            0.99,
            start_button=PixelRect(200, 600, 400, 120),
            start_button_confidence=0.99,
        )
        self.calls = 0

    def classify(self, capture: ScreenCapture) -> ScreenClassification:
        self.calls += 1
        return next(self.results, self.fallback)


def _build(
    android: FakeAndroid,
    classifier: FakeClassifier,
    directory: Path,
    *,
    logger: StructuredLogger | None = None,
    clock: Callable[[], float] = lambda: 1.0,
    sleeper: Callable[[float], None] | None = None,
    wheel_detector: WheelGeometryDetector | None = None,
    letter_recognizer: WheelLetterRecognitionPort | None = None,
    acceptance_verifier: FakeAcceptanceVerifier | None = None,
    completion_overlay_detector: FakeCompletionOverlayDetector | None = None,
    level_number_recognizer: LevelNumberRecognitionPort | None = None,
) -> ApplicationRuntime:
    return build_runtime(
        Settings(debug_directory=directory),
        logger=logger or StructuredLogger(logging.getLogger("test.runtime")),
        android_factory=lambda settings, supplied_logger: cast(AndroidPort, android),
        level_factory=lambda: JsonLevelRepository.from_json(
            '{"levels":[{"number":1,"words":["AB","CAB"]}]}'
        ),
        screen_classifier=classifier,
        wheel_detector=wheel_detector or FakeWheelDetector(),
        letter_recognizer=letter_recognizer or FakeLetterRecognizer(),
        level_number_recognizer=level_number_recognizer or FakeLevelNumberRecognizer(),
        word_acceptance_verifier=acceptance_verifier or FakeAcceptanceVerifier(),
        popup_close_button_detector=FakePopupCloseDetector(),
        completion_overlay_detector=(
            completion_overlay_detector or FakeCompletionOverlayDetector()
        ),
        clock=clock,
        sleeper=(lambda _: None) if sleeper is None else sleeper,
    )


def test_build_runtime_wires_existing_production_components(tmp_path: Path) -> None:
    android = FakeAndroid()
    classifier = FakeClassifier()
    runtime = _build(android, classifier, tmp_path)
    assert runtime.android is cast(AndroidPort, android)
    assert runtime.game_loop.android is cast(AndroidPort, android)
    assert runtime.screen_classifier is classifier


def test_start_captures_classifies_and_logs_level_entry(tmp_path: Path) -> None:
    android = FakeAndroid()
    classifier = FakeClassifier(
        ScreenClassification(ScreenType.HOME_SCREEN, 0.98),
        ScreenClassification(ScreenType.LEVEL_SCREEN, 0.97),
        ScreenClassification(ScreenType.HOME_SCREEN, 0.98),
    )
    stream = io.StringIO()
    runtime = _build(
        android,
        classifier,
        tmp_path,
        logger=configure_logging(name="test.capture", stream=stream),
    )
    runtime.start(max_levels=1)
    assert (tmp_path / "screenshot-1.png").read_bytes() == PNG
    assert (android.selected, android.verified, android.captures) == (1, 1, 4)
    output = stream.getvalue()
    assert '"detected_screen": "level_screen"' in output
    assert '"template_confidence": 0.97' in output
    assert '"event": "runtime.level.entered"' in output
    assert '"event": "runtime.wheel.detected"' in output
    assert '"center_x": 540' in output
    assert '"center_y": 1800' in output
    assert '"radius": 300' in output
    assert '"number_of_letters": 3' in output
    assert (tmp_path / "letter-wheel-annotated.png").exists()
    assert (tmp_path / "letter-wheel-geometry.json").exists()


def test_starting_on_level_screen_continues_solving_without_home_button(
    tmp_path: Path,
) -> None:
    android = FakeAndroid()
    runtime = _build(
        android,
        FakeClassifier(
            ScreenClassification(ScreenType.LEVEL_SCREEN, 0.99),
            ScreenClassification(ScreenType.HOME_SCREEN, 0.99),
        ),
        tmp_path,
    )

    runtime.start(max_levels=1)

    assert android.taps == []
    assert len(android.swipes) == 2
    assert runtime.level_number_recognizer.calls == 1  # type: ignore[attr-defined]


def test_home_start_is_tapped_then_level_is_verified(tmp_path: Path) -> None:
    android = FakeAndroid()
    classifier = FakeClassifier(
        ScreenClassification(
            ScreenType.HOME_SCREEN,
            0.98,
            start_button=PixelRect(200, 600, 400, 120),
            start_button_confidence=0.95,
        ),
        ScreenClassification(ScreenType.LEVEL_SCREEN, 0.96),
    )
    sleeps: list[float] = []
    stream = io.StringIO()
    runtime = _build(
        android,
        classifier,
        tmp_path,
        logger=configure_logging(name="test.home", stream=stream),
        sleeper=sleeps.append,
    )
    runtime.start(max_levels=1)
    assert android.taps == [PixelPoint(540, 1569)]
    assert sleeps == [4.0, 1.0, 0.5]
    assert android.captures == 4
    assert classifier.calls == 3
    output = stream.getvalue()
    detected_index = output.index('"event": "runtime.start_level.detected"')
    level_index = output.index('"event": "runtime.level.detected"')
    tap_index = output.index('"event": "runtime.start_level.tap"')
    assert detected_index < tap_index < level_index
    assert '"button_left": 540' in output
    assert '"button_width": 0' in output
    assert '"button_height": 0' in output
    assert '"ocr_crop_width": 0' in output
    assert '"ocr_crop_height": 0' in output
    assert '"event": "runtime.level.entered"' in output
    assert '"event": "runtime.wheel.detected"' in output
    assert '"center_x": 540' in output
    assert '"center_y": 1800' in output
    assert '"radius": 300' in output
    assert '"number_of_letters": 3' in output
    assert (tmp_path / "letter-wheel-annotated.png").exists()
    assert (tmp_path / "letter-wheel-geometry.json").exists()


def test_completion_home_start_waits_before_first_level_detection(tmp_path: Path) -> None:
    android = FakeAndroid()
    sleeps: list[float] = []
    runtime = _build(
        android,
        FakeClassifier(
            ScreenClassification(ScreenType.LEVEL_SCREEN, 0.99),
            ScreenClassification(ScreenType.HOME_SCREEN, 0.99),
        ),
        tmp_path,
        sleeper=sleeps.append,
        completion_overlay_detector=FakeCompletionOverlayDetector(True, False),
    )

    runtime.start(max_levels=1)

    assert android.taps == [PixelPoint(540, 1569)]
    assert sleeps[0] == 4.0
    assert sleeps.count(4.0) == 1


def test_daily_dash_then_home_then_level_navigation(tmp_path: Path) -> None:
    android = FakeAndroid()
    classifier = FakeClassifier(
        ScreenClassification(
            ScreenType.DAILY_DASH_POPUP,
            0.98,
            close_button=PixelRect(90, 30, 20, 20),
        ),
        ScreenClassification(
            ScreenType.HOME_SCREEN,
            0.97,
            start_button=PixelRect(200, 600, 400, 120),
            start_button_confidence=0.96,
        ),
        ScreenClassification(ScreenType.LEVEL_SCREEN, 0.95),
    )
    sleeps: list[float] = []
    runtime = _build(android, classifier, tmp_path, sleeper=sleeps.append)
    runtime.start(max_levels=1)
    assert android.taps == [PixelPoint(100, 40), PixelPoint(540, 1569)]
    assert sleeps == [0.5, 4.0, 1.0, 0.5]
    assert android.captures == 5
    assert classifier.calls == 4


def test_entry_waits_without_tapping_until_level_wheel_appears(tmp_path: Path) -> None:
    classifier = FakeClassifier(
        ScreenClassification(ScreenType.HOME_SCREEN, 0.98),
        ScreenClassification(ScreenType.UNKNOWN, 0.2),
        ScreenClassification(ScreenType.UNKNOWN, 0.2),
        ScreenClassification(ScreenType.LEVEL_SCREEN, 0.96),
        ScreenClassification(ScreenType.HOME_SCREEN, 0.98),
    )
    sleeps: list[float] = []
    android = FakeAndroid()

    _build(android, classifier, tmp_path, sleeper=sleeps.append).start(max_levels=1)

    assert android.taps == [PixelPoint(540, 1569)]
    assert sleeps[:3] == [4.0, 1.0, 1.0]


def test_capture_failure_is_logged_and_raised(tmp_path: Path) -> None:
    stream = io.StringIO()
    runtime = _build(
        FakeAndroid(b"bad"),
        FakeClassifier(),
        tmp_path,
        logger=configure_logging(name="test.failure", stream=stream),
    )
    with pytest.raises(ScreenshotError):
        runtime.start(max_levels=1)
    assert '"event": "runtime.screenshot.failed"' in stream.getvalue()


def test_wheel_detection_failure_logs_and_raises(tmp_path: Path) -> None:
    stream = io.StringIO()
    runtime = _build(
        FakeAndroid(),
        FakeClassifier(
            ScreenClassification(ScreenType.HOME_SCREEN, 0.99),
            ScreenClassification(ScreenType.LEVEL_SCREEN, 0.99),
        ),
        tmp_path,
        logger=configure_logging(name="test.wheel.failure", stream=stream),
        wheel_detector=FakeWheelDetector(fail=True),
    )
    with pytest.raises(WheelGeometryDetectionError, match="wheel missing"):
        runtime.start(max_levels=1)
    output = stream.getvalue()
    assert '"event": "runtime.wheel.detection_failed"' in output
    assert '"error": "wheel missing"' in output


def test_letter_recognition_failure_logs_and_raises(tmp_path: Path) -> None:
    stream = io.StringIO()
    runtime = _build(
        FakeAndroid(),
        FakeClassifier(
            ScreenClassification(ScreenType.HOME_SCREEN, 0.99),
            ScreenClassification(ScreenType.LEVEL_SCREEN, 0.99),
        ),
        tmp_path,
        logger=configure_logging(name="test.letters.failure", stream=stream),
        letter_recognizer=FakeLetterRecognizer(fail=True),
    )
    with pytest.raises(OcrError, match="letters missing"):
        runtime.start(max_levels=1)
    assert '"event": "runtime.letters.recognition_failed"' in stream.getvalue()


def test_unknown_screens_are_saved_sequentially_with_detector_diagnostics(
    tmp_path: Path,
) -> None:
    android = FakeAndroid()
    stream = io.StringIO()
    runtime = _build(
        android,
        FakeClassifier(
            ScreenClassification(ScreenType.UNKNOWN, 0.21),
            ScreenClassification(ScreenType.UNKNOWN, 0.24),
            ScreenClassification(ScreenType.LEVEL_SCREEN, 0.99),
            ScreenClassification(ScreenType.HOME_SCREEN, 0.99),
        ),
        tmp_path,
        logger=configure_logging(name="test.unknown", stream=stream),
    )

    runtime.start(max_levels=1)

    unknown_directory = tmp_path / "unknown"
    assert (unknown_directory / "unknown-0001.png").read_bytes() == PNG
    assert (unknown_directory / "unknown-0002.png").read_bytes() == PNG
    output = stream.getvalue()
    assert output.count('"event": "runtime.screen.unknown_saved"') == 2
    assert '"level_template_matched": null' in output
    assert '"wheel_check_passed": null' in output


def test_dry_run_has_no_device_screenshot_or_classification_io(tmp_path: Path) -> None:
    android = FakeAndroid()
    classifier = FakeClassifier()
    runtime = _build(android, classifier, tmp_path)
    runtime.start(dry_run=True)
    runtime.shutdown()
    assert (android.selected, android.verified, android.captures) == (0, 0, 0)
    assert classifier.calls == 0
    assert not (tmp_path / "screenshot-1.png").exists()


def test_rejected_first_word_logs_and_stops(tmp_path: Path) -> None:
    android = FakeAndroid()
    stream = io.StringIO()
    runtime = _build(
        android,
        FakeClassifier(),
        tmp_path,
        logger=configure_logging(name="test.word.rejected", stream=stream),
        acceptance_verifier=FakeAcceptanceVerifier(accepted=False),
    )
    with pytest.raises(WordNotAcceptedError, match="AB"):
        runtime.start(max_levels=1)
    assert len(android.swipes) == 3
    assert (tmp_path / "swipe.json").exists()
    assert '"event": "runtime.word.not_accepted"' in stream.getvalue()


def test_completed_level_automatically_starts_the_next_level(tmp_path: Path) -> None:
    home = ScreenClassification(ScreenType.HOME_SCREEN, 0.99)
    classifier = FakeClassifier(
        home,
        ScreenClassification(ScreenType.LEVEL_SCREEN, 0.99),
        home,
        home,
        ScreenClassification(ScreenType.LEVEL_SCREEN, 0.99),
        home,
    )
    android = FakeAndroid()
    runtime = _build(android, classifier, tmp_path)

    runtime.start(max_levels=2)

    assert len(android.swipes) == 4
    assert android.taps == [PixelPoint(540, 1569), PixelPoint(540, 1569)]


class RetryingLevelNumberRecognizer:
    def __init__(self) -> None:
        self.calls = 0
        self.last_candidates: tuple[str, ...] = ()

    def recognize(self, capture: ScreenCapture) -> int:
        self.calls += 1
        if self.calls < 3:
            self.last_candidates = ("( }",)
            raise OcrError("invalid level text")
        self.last_candidates = ("1",)
        return 1


def test_level_ocr_retries_with_fresh_screenshots(tmp_path: Path) -> None:
    android = FakeAndroid()
    recognizer = RetryingLevelNumberRecognizer()
    sleeps: list[float] = []
    runtime = _build(
        android,
        FakeClassifier(
            ScreenClassification(ScreenType.LEVEL_SCREEN, 0.99),
            ScreenClassification(ScreenType.LEVEL_SCREEN, 0.99),
            ScreenClassification(ScreenType.LEVEL_SCREEN, 0.99),
            ScreenClassification(ScreenType.HOME_SCREEN, 0.99),
        ),
        tmp_path,
        sleeper=sleeps.append,
        level_number_recognizer=recognizer,
    )

    runtime.start(max_levels=1)

    assert recognizer.calls == 3
    assert sleeps[:2] == [0.5, 0.5]
    assert (tmp_path / "level-ocr-retry-1.png").exists()
    assert (tmp_path / "level-ocr-retry-2.png").exists()


def test_post_start_tap_to_continue_false_positive_does_not_tap(tmp_path: Path) -> None:
    android = FakeAndroid()
    sleeps: list[float] = []
    runtime = _build(
        android,
        FakeClassifier(
            ScreenClassification(ScreenType.HOME_SCREEN, 0.99),
            ScreenClassification(ScreenType.UNKNOWN, 0.2),
            ScreenClassification(ScreenType.LEVEL_SCREEN, 0.99),
            ScreenClassification(ScreenType.HOME_SCREEN, 0.99),
        ),
        tmp_path,
        sleeper=sleeps.append,
    )
    original_dispatcher = runtime.level_executor.completion_overlay_detector
    assert original_dispatcher is not None
    original_dispatcher.tap_to_continue_visible = lambda capture: True  # type: ignore[method-assign]

    runtime.start(max_levels=1)

    assert android.taps == [PixelPoint(540, 1569)]
    assert sleeps[:2] == [4.0, 1.0]
