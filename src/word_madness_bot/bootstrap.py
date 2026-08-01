"""Composition root for the production application."""

from __future__ import annotations

import time
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import NoReturn, Protocol

from word_madness_bot.application.decision_engine import DecisionEngine
from word_madness_bot.application.game_loop import GameLoop
from word_madness_bot.application.level_executor import LevelExecutor
from word_madness_bot.application.ports.android import AndroidPort
from word_madness_bot.application.ports.levels import LevelRepository
from word_madness_bot.application.recovery import RecoveryStrategy, RetryPolicy, TimeoutPolicy
from word_madness_bot.application.runtime_controls import (
    PopupCloseButtonPort,
    UpperRightPopupCloseDetector,
)
from word_madness_bot.application.solution_planning import (
    LevelSolutionPlan,
    LevelSolutionPlanner,
    save_level_solution,
)
from word_madness_bot.application.word_execution import (
    ImageDifferenceWordAcceptanceVerifier,
    SingleWordExecutor,
    WordAcceptanceVerifier,
)
from word_madness_bot.config.logging import StructuredLogger, configure_logging
from word_madness_bot.config.settings import Settings
from word_madness_bot.domain.errors import (
    OcrError,
    RuntimeNavigationError,
    ScreenshotError,
    WheelGeometryDetectionError,
    WordMadnessError,
    WordNotAcceptedError,
)
from word_madness_bot.domain.geometry import NormalizedPoint, PixelPoint
from word_madness_bot.domain.models import ScreenCapture
from word_madness_bot.gameplay.ads import AdvertisementPolicy
from word_madness_bot.gameplay.swipe_generator import SwipePathPlanner
from word_madness_bot.infrastructure.adb.client import AdbClient
from word_madness_bot.infrastructure.adb.screenshot import save_screenshot
from word_madness_bot.infrastructure.levels.json_repository import JsonLevelRepository
from word_madness_bot.vision.letter_recognition import (
    WheelLetterRecognition,
    WheelLetterRecognitionPort,
    WheelLetterRecognizer,
)
from word_madness_bot.vision.level_number import (
    LevelNumberRecognitionPort,
    LevelNumberRecognizer,
)
from word_madness_bot.vision.screen_classifier import (
    ScreenClassification,
    ScreenClassifier,
    ScreenType,
)
from word_madness_bot.vision.wheel_geometry import (
    LetterWheelDetector,
    LetterWheelGeometry,
    WheelGeometryDetector,
    save_wheel_debug_artifacts,
)

AndroidFactory = Callable[[Settings, StructuredLogger], AndroidPort]
LevelFactory = Callable[[], LevelRepository]
Clock = Callable[[], float]
Sleeper = Callable[[float], None]
START_LEVEL_POINT = NormalizedPoint(0.500, 0.654)


class RuntimeScreenClassifier(Protocol):
    """Narrow classification dependency used by the runtime."""

    def classify(self, capture: ScreenCapture) -> ScreenClassification: ...


@dataclass(slots=True)
class ApplicationRuntime:
    """Owned production dependency graph with an explicit lifecycle."""

    settings: Settings
    logger: StructuredLogger
    android: AndroidPort
    levels: LevelRepository
    planner: SwipePathPlanner
    decisions: DecisionEngine
    game_loop: GameLoop
    advertisements: AdvertisementPolicy
    recovery: RecoveryStrategy
    screen_classifier: RuntimeScreenClassifier
    wheel_detector: WheelGeometryDetector
    letter_recognizer: WheelLetterRecognitionPort
    level_number_recognizer: LevelNumberRecognitionPort
    solution_planner: LevelSolutionPlanner
    level_executor: LevelExecutor
    clock: Clock = field(default=time.monotonic, repr=False)
    sleeper: Sleeper = field(default=time.sleep, repr=False)
    _started: bool = False

    def start(self, *, dry_run: bool = False, max_levels: int | None = None) -> None:
        """Run complete levels continuously, unless a test supplies a level bound."""
        if max_levels is not None and max_levels <= 0:
            raise ValueError("max_levels must be positive")
        self.logger.info("runtime.starting", dry_run=dry_run)
        if not dry_run:
            device = self.android.select_device()
            self.android.verify_connection()
            self.logger.info("runtime.device.ready", serial=device.serial)
            screenshot_number = 1
            capture = self._capture_debug_screenshot(
                f"screenshot-{screenshot_number}.png"
            )
            classification = self._classify(capture)

            if classification.screen is ScreenType.DAILY_DASH_POPUP:
                if classification.close_button is None:
                    self._raise_navigation_failure(
                        classification, reason="daily_dash_close_not_found"
                    )
                region = classification.close_button
                point = PixelPoint(
                    region.left + region.width // 2,
                    region.top + region.height // 2,
                )
                self.logger.info("runtime.daily_dash.tap", tap_x=point.x, tap_y=point.y)
                self.android.tap(point)
                self.sleeper(0.5)
                screenshot_number += 1
                capture = self._capture_debug_screenshot(
                    f"screenshot-{screenshot_number}.png"
                )
                classification = self._classify(capture)

            completed_levels = 0
            if classification.screen is ScreenType.LEVEL_SCREEN:
                level_number = self.level_number_recognizer.recognize(capture)
                self.logger.info(
                    "runtime.level.detected",
                    detected_level=level_number,
                )
                capture = self._solve_detected_level(capture, level_number)
                completed_levels += 1
            elif classification.screen is not ScreenType.HOME_SCREEN:
                self._raise_navigation_failure(
                    classification, reason="home_screen_not_reached"
                )

            while max_levels is None or completed_levels < max_levels:
                point = START_LEVEL_POINT.to_pixels(capture.size)
                self.logger.info(
                    "runtime.start_level.detected",
                    button_left=point.x,
                    button_top=point.y,
                    button_width=0,
                    button_height=0,
                    ocr_crop_width=0,
                    ocr_crop_height=0,
                    template_confidence=None,
                )
                capture, classification = self._enter_level(point)
                self.logger.info(
                    "runtime.level.entered",
                    template_confidence=classification.confidence,
                )
                level_number = self.level_number_recognizer.recognize(capture)
                self.logger.info(
                    "runtime.level.detected",
                    detected_level=level_number,
                )
                capture = self._solve_detected_level(capture, level_number)
                completed_levels += 1
        self._started = True
        self.logger.info("runtime.started", dry_run=dry_run)

    def _solve_detected_level(
        self,
        capture: ScreenCapture,
        level_number: int,
    ) -> ScreenCapture:
        geometry = self._detect_wheel_geometry(capture)
        recognition = self._recognize_letters(capture, geometry)
        plan = self._plan_level_solution(
            capture,
            geometry,
            recognition,
            level_number=level_number,
        )
        self.sleeper(10.0)
        return self._execute_level(capture, plan)

    def _enter_level(
        self,
        point: PixelPoint,
    ) -> tuple[ScreenCapture, ScreenClassification]:
        while True:
            self.logger.info("runtime.start_level.tap", tap_x=point.x, tap_y=point.y)
            self.android.tap(point)
            self.sleeper(3.0)
            capture = self.android.capture_screenshot()
            classification = self._classify(capture)
            if classification.screen is ScreenType.LEVEL_SCREEN:
                return capture, classification
    def _raise_navigation_failure(
        self,
        classification: ScreenClassification,
        *,
        reason: str,
    ) -> NoReturn:
        self.logger.error(
            "runtime.level.transition_failed",
            reason=reason,
            detected_screen=classification.screen.value,
            template_confidence=classification.confidence,
        )
        raise RuntimeNavigationError(
            f"Unable to enter level: {reason} "
            f"(detected {classification.screen.value})"
        )

    def _detect_wheel_geometry(self, capture: ScreenCapture) -> LetterWheelGeometry:
        started = self.clock()
        try:
            geometry = self.wheel_detector.detect(capture)
            annotated_path, json_path = save_wheel_debug_artifacts(
                self.settings.debug_directory,
                capture,
                geometry,
                self.wheel_detector,
            )
        except WheelGeometryDetectionError as error:
            self.logger.exception(
                "runtime.wheel.detection_failed",
                detection_duration_seconds=self.clock() - started,
                error=str(error),
            )
            raise
        self.logger.info(
            "runtime.wheel.detected",
            detection_duration_seconds=self.clock() - started,
            center_x=geometry.center.x,
            center_y=geometry.center.y,
            radius=geometry.radius,
            number_of_letters=len(geometry.letters),
            annotated_filename=str(annotated_path),
            json_filename=str(json_path),
        )
        return geometry

    def _recognize_letters(
        self,
        capture: ScreenCapture,
        geometry: LetterWheelGeometry,
    ) -> WheelLetterRecognition:
        try:
            recognition = self.letter_recognizer.recognize(
                capture,
                geometry,
                self.settings.debug_directory,
            )
        except OcrError as error:
            self.logger.exception(
                "runtime.letters.recognition_failed",
                error=str(error),
            )
            raise
        for letter in recognition.letters:
            self.logger.info(
                "runtime.letter.recognized",
                index=letter.index,
                detected_character=letter.character,
                confidence=letter.confidence,
                elapsed_recognition_seconds=letter.elapsed_seconds,
                crop_filename=str(letter.crop_path),
            )
        self.logger.info(
            "runtime.letters.recognized",
            number_of_letters=len(recognition.letters),
            output_filename=str(self.settings.debug_directory / "letters.json"),
        )
        return recognition

    def _plan_level_solution(
        self,
        capture: ScreenCapture,
        geometry: LetterWheelGeometry,
        recognition: WheelLetterRecognition,
        *,
        level_number: int,
    ) -> LevelSolutionPlan:
        started = self.clock()
        try:
            plan = self.solution_planner.plan(
                level_number, recognition, geometry, capture.size
            )
            output_path = save_level_solution(plan, self.settings.debug_directory)
        except WordMadnessError as error:
            self.logger.exception(
                "runtime.solution.planning_failed",
                planning_duration_seconds=self.clock() - started,
                error=str(error),
            )
            raise
        self.logger.info(
            "runtime.solution.planned",
            detected_level=plan.level,
            recognized_letters=list(plan.recognized_letters),
            number_of_solution_words=len(plan.solutions),
            planning_duration_seconds=self.clock() - started,
            output_filename=str(output_path),
        )
        return plan

    def _execute_level(
        self,
        before: ScreenCapture,
        plan: LevelSolutionPlan,
    ) -> ScreenCapture:
        try:
            result = self.level_executor.execute(
                plan, before, self.settings.debug_directory
            )
        except WordNotAcceptedError as error:
            self.logger.error(
                "runtime.word.not_accepted",
                executed_word=error.word,
                acceptance_verification=False,
            changed_pixel_ratio=error.changed_pixel_ratio,
            )
            raise
        except WordMadnessError as error:
            self.logger.exception(
                "runtime.word.execution_failed",
                error=str(error),
            )
            raise
        for word in result.words:
            coordinates = [{"x": point.x, "y": point.y} for point in word.coordinates]
            self.logger.info(
                "runtime.word.executed",
                executed_word=word.word,
                swipe_duration_ms=word.duration_ms,
                swipe_coordinates=coordinates,
                acceptance_verification=word.acceptance.accepted,
                changed_pixel_ratio=word.acceptance.changed_pixel_ratio,
                elapsed_execution_seconds=word.elapsed_seconds,
            )
        self.logger.info(
            "runtime.level.completed",
            detected_level=plan.level,
            number_of_solution_words=len(result.words),
        )
        return result.home_capture

    def _classify(self, capture: ScreenCapture) -> ScreenClassification:
        started = self.clock()
        result = self.screen_classifier.classify(capture)
        self.logger.info(
            "runtime.screen.detected",
            detected_screen=result.screen.value,
            template_confidence=result.confidence,
            elapsed_detection_seconds=self.clock() - started,
        )
        return result

    def _capture_debug_screenshot(self, filename: str) -> ScreenCapture:
        destination = self.settings.debug_directory / filename
        started = self.clock()
        try:
            capture = self.android.capture_screenshot()
            save_screenshot(capture.data, destination)
        except WordMadnessError:
            self.logger.exception(
                "runtime.screenshot.failed",
                output_filename=str(destination),
                capture_duration_seconds=self.clock() - started,
            )
            raise
        except OSError as error:
            self.logger.exception(
                "runtime.screenshot.failed",
                output_filename=str(destination),
                capture_duration_seconds=self.clock() - started,
            )
            raise ScreenshotError(f"Unable to save screenshot: {destination}") from error
        self.logger.info(
            "runtime.screenshot.captured",
            resolution=f"{capture.size.width}x{capture.size.height}",
            output_filename=str(destination),
            capture_duration_seconds=self.clock() - started,
        )
        return capture

    def shutdown(self) -> None:
        """Complete the lifecycle safely; repeated shutdown is harmless."""
        if not self._started:
            return
        self._started = False
        self.logger.info("runtime.stopped")


def build_runtime(
    settings: Settings,
    *,
    logger: StructuredLogger | None = None,
    android_factory: AndroidFactory = AdbClient,
    level_factory: LevelFactory = JsonLevelRepository.from_package,
    screen_classifier: RuntimeScreenClassifier | None = None,
    wheel_detector: WheelGeometryDetector | None = None,
    letter_recognizer: WheelLetterRecognitionPort | None = None,
    level_number_recognizer: LevelNumberRecognitionPort | None = None,
    word_acceptance_verifier: WordAcceptanceVerifier | None = None,
    popup_close_button_detector: PopupCloseButtonPort | None = None,
    clock: Clock = time.monotonic,
    sleeper: Sleeper = time.sleep,
) -> ApplicationRuntime:
    """Wire all production components without contacting a device at import time."""
    runtime_logger = logger or configure_logging(level=settings.log_level)
    android = android_factory(settings, runtime_logger)
    levels = level_factory()
    planner = SwipePathPlanner()
    decisions = DecisionEngine()
    classifier = screen_classifier or ScreenClassifier()
    single_word_executor = SingleWordExecutor(
        android,
        word_acceptance_verifier or ImageDifferenceWordAcceptanceVerifier(),
        sleeper=sleeper,
        clock=clock,
    )
    return ApplicationRuntime(
        settings=settings,
        logger=runtime_logger,
        android=android,
        levels=levels,
        planner=planner,
        decisions=decisions,
        game_loop=GameLoop(android, levels, planner, decisions),
        advertisements=AdvertisementPolicy(),
        recovery=RecoveryStrategy(RetryPolicy(), TimeoutPolicy()),
        screen_classifier=classifier,
        wheel_detector=wheel_detector or LetterWheelDetector(),
        letter_recognizer=letter_recognizer or WheelLetterRecognizer(),
        level_number_recognizer=level_number_recognizer or LevelNumberRecognizer(),
        solution_planner=LevelSolutionPlanner(levels, planner),
        level_executor=LevelExecutor(
            android,
            single_word_executor,
            classifier,
            popup_close_button_detector or UpperRightPopupCloseDetector(),
            swipe_duration_ms=settings.swipe_duration_ms,
            sleeper=sleeper,
        ),
        clock=clock,
        sleeper=sleeper,
    )
