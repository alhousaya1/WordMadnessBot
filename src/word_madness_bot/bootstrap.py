"""Composition root for the production application."""

from __future__ import annotations

import shutil
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
    CompletionOverlayDetector,
    CompletionOverlayPort,
    PopupCloseButtonPort,
    UpperRightPopupCloseDetector,
)
from word_madness_bot.application.runtime_dispatcher import (
    RuntimeScreenDispatcher,
    RuntimeScreenState,
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
    LevelNotFoundError,
    OcrError,
    RuntimeNavigationError,
    ScreenshotError,
    WheelGeometryDetectionError,
    WordMadnessError,
    WordNotAcceptedError,
)
from word_madness_bot.domain.geometry import PixelPoint, PixelRect
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
    parse_level_number,
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
COMPLETION_HOME_TRANSITION_TIMEOUT_SECONDS = 23.0
LEVEL_ENTRY_STABILIZATION_SECONDS = 5.0
RECENT_DEBUG_CYCLE_LIMIT = 10


class RuntimeScreenClassifier(Protocol):
    """Narrow classification dependency used by the runtime."""

    def classify(self, capture: ScreenCapture) -> ScreenClassification: ...


@dataclass(slots=True)
class LevelCycleState:
    """All recognition state whose lifetime is exactly one level attempt."""

    cycle_id: str
    confirmed_home_level: int | None = None
    level_number: int | None = None
    wheel_geometry: LetterWheelGeometry | None = None
    recognized_letters: WheelLetterRecognition | None = None
    solution_plan: LevelSolutionPlan | None = None
    recognition_retry: int = 0
    replay_pass: int = 0
    previous_capture: ScreenCapture | None = None
    previous_screen_confidence: float | None = None
    validation_candidates: tuple[str, ...] = ()
    completed: bool = False

    def clear_recognition_attempt(self) -> None:
        """Discard every value derived from a failed or previous frame."""
        self.level_number = None
        self.wheel_geometry = None
        self.recognized_letters = None
        self.solution_plan = None
        self.previous_capture = None
        self.previous_screen_confidence = None
        self.validation_candidates = ()


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
    _unknown_screenshot_number: int = 0
    _cycle_sequence: int = 0
    _cycle_state: LevelCycleState | None = None

    def start(self, *, dry_run: bool = False, max_levels: int | None = None) -> None:
        """Dispatch any current game screen until the requested levels are complete."""
        if max_levels is not None and max_levels <= 0:
            raise ValueError("max_levels must be positive")
        self.logger.info("runtime.starting", dry_run=dry_run)
        if dry_run:
            self._started = True
            self.logger.info("runtime.started", dry_run=True)
            return

        device = self.android.select_device()
        self.android.verify_connection()
        self.logger.info("runtime.device.ready", serial=device.serial)
        dispatcher = RuntimeScreenDispatcher(
            self._classify,
            self.level_executor.completion_overlay_detector,
            self.level_executor.popup_close_detector,
        )
        completed_levels = 0
        screenshot_number = 0
        awaiting_level = False
        completion_home_started: float | None = None
        completion_home_attempts = 0
        fresh_capture_after_entry_wait = False

        while max_levels is None or completed_levels < max_levels:
            screenshot_number += 1
            capture = self._capture_debug_screenshot(f"screenshot-{screenshot_number}.png")
            if fresh_capture_after_entry_wait:
                cycle = self._cycle_state
                self.logger.info(
                    "runtime.level.fresh_capture_after_wait",
                    cycle_id=cycle.cycle_id if cycle is not None else None,
                    confirmed_home_level=(
                        cycle.confirmed_home_level if cycle is not None else None
                    ),
                    fresh_capture_after_wait=True,
                )
                fresh_capture_after_entry_wait = False
            dispatch = dispatcher.dispatch(capture)
            self.logger.info("runtime.screen.dispatched", runtime_state=dispatch.state.value)

            if dispatch.state is RuntimeScreenState.LEVEL:
                completion_home_started = None
                completion_home_attempts = 0
                cycle = self._cycle_state or self._reset_level_cycle()
                if awaiting_level and dispatch.classification is not None:
                    self.logger.info(
                        "runtime.level.entered",
                        cycle_id=cycle.cycle_id,
                        template_confidence=dispatch.classification.confidence,
                    )
                prepared = self._prepare_level_with_retries(capture, dispatcher, cycle)
                if prepared is None:
                    awaiting_level = False
                    continue
                awaiting_level = False
                capture, plan = prepared
                self.logger.info("runtime.level.solving_started", cycle_id=cycle.cycle_id)
                self._execute_level(capture, plan, cycle_id=cycle.cycle_id)
                cycle.completed = True
                cycle.confirmed_home_level = None
                completed_levels += 1
                continue

            if dispatch.state is RuntimeScreenState.COMPLETION_HOME:
                now = self.clock()
                if completion_home_started is None:
                    completion_home_started = now
                    completion_home_attempts = 0
                    cycle = self._reset_level_cycle()
                    self.logger.info(
                        "runtime.home.detected",
                        cycle_id=cycle.cycle_id,
                        confidence=None,
                        completion_home=True,
                    )
                if now - completion_home_started >= COMPLETION_HOME_TRANSITION_TIMEOUT_SECONDS:
                    raise RuntimeNavigationError(
                        "Completion Home did not transition after tapping the Level button "
                        f"within {COMPLETION_HOME_TRANSITION_TIMEOUT_SECONDS:.0f} seconds"
                    )

                cycle = self._cycle_state or self._reset_level_cycle()
                if cycle.confirmed_home_level is None and not self._confirm_home_level(
                    capture, cycle
                ):
                    self.sleeper(0.5)
                    continue
                point = dispatch.action_point
                should_tap = completion_home_attempts == 0
                if should_tap:
                    if point is None:
                        raise RuntimeNavigationError(
                            "Completion Home dispatcher did not provide a Level tap"
                        )
                    self._log_start_level(
                        point,
                        dispatch.action_region,
                        cycle_id=self._cycle_state.cycle_id if self._cycle_state else None,
                    )
                    self.android.tap(point)
                    self._wait_for_level_entry(cycle)
                    fresh_capture_after_entry_wait = True
                completion_home_attempts += 1
                awaiting_level = should_tap or awaiting_level
                if not should_tap:
                    self.sleeper(0.5)
                continue

            completion_home_started = None
            completion_home_attempts = 0

            if dispatch.state is RuntimeScreenState.NORMAL_HOME:
                if awaiting_level:
                    self.logger.info(
                        "runtime.level.transition_retry",
                        cycle_id=self._cycle_state.cycle_id if self._cycle_state else None,
                        reason="home_still_visible_after_start_tap",
                    )
                    self.sleeper(0.5)
                    continue
                cycle = self._reset_level_cycle()
                self.logger.info(
                    "runtime.home.detected",
                    cycle_id=cycle.cycle_id,
                    confidence=(
                        dispatch.classification.confidence if dispatch.classification else None
                    ),
                )
                if not self._confirm_home_level(capture, cycle):
                    self.sleeper(0.5)
                    continue
                point = dispatch.action_point
                if point is None:
                    raise RuntimeNavigationError("Home dispatcher did not provide a Level tap")
                self._log_start_level(point, cycle_id=cycle.cycle_id)
                self.android.tap(point)
                awaiting_level = True
                self._wait_for_level_entry(cycle)
                fresh_capture_after_entry_wait = True
                continue

            if awaiting_level and dispatch.state in {
                RuntimeScreenState.UNKNOWN,
                RuntimeScreenState.TAP_TO_CONTINUE,
            }:
                cycle = self._cycle_state or self._reset_level_cycle()
                cycle.recognition_retry += 1
                self.logger.info(
                    "runtime.level.waiting_for_wheel",
                    cycle_id=cycle.cycle_id,
                    attempt=cycle.recognition_retry,
                    detected_screen=(
                        dispatch.classification.screen.value
                        if dispatch.classification is not None
                        else dispatch.state.value
                    ),
                )
                self.sleeper(1.0)
                continue

            if dispatch.action_point is not None:
                self.android.tap(dispatch.action_point)
                self.sleeper(0.5)
                continue

            self.sleeper(0.5)

        self._started = True
        self.logger.info("runtime.started", dry_run=False)

    def _wait_for_level_entry(self, cycle: LevelCycleState) -> None:
        wait_duration_ms = round(LEVEL_ENTRY_STABILIZATION_SECONDS * 1000)
        self.logger.info(
            "runtime.level.entry_wait_started",
            cycle_id=cycle.cycle_id,
            confirmed_home_level=cycle.confirmed_home_level,
            wait_duration_ms=wait_duration_ms,
        )
        self.sleeper(LEVEL_ENTRY_STABILIZATION_SECONDS)
        self.logger.info(
            "runtime.level.entry_wait_completed",
            cycle_id=cycle.cycle_id,
            confirmed_home_level=cycle.confirmed_home_level,
            wait_duration_ms=wait_duration_ms,
        )

    def _reset_level_cycle(self) -> LevelCycleState:
        self._cycle_sequence += 1
        state = LevelCycleState(f"cycle-{self._cycle_sequence:06d}")
        self._cycle_state = state
        self._prune_debug_cycles()
        self.logger.info(
            "runtime.level.next_cycle_started",
            cycle_id=state.cycle_id,
            confirmed_home_level=None,
        )
        return state

    def _prune_debug_cycles(self) -> None:
        root = self.settings.debug_directory
        if not root.exists():
            return
        cycles = sorted(
            path for path in root.glob("cycle-[0-9][0-9][0-9][0-9][0-9][0-9]") if path.is_dir()
        )
        for expired in cycles[:-RECENT_DEBUG_CYCLE_LIMIT]:
            shutil.rmtree(expired)

    def _confirm_home_level(self, capture: ScreenCapture, cycle: LevelCycleState) -> bool:
        try:
            recognize_home = getattr(
                self.level_number_recognizer,
                "recognize_home",
                self.level_number_recognizer.recognize,
            )
            number = recognize_home(capture)
            self.levels.get_level(number)
        except (OcrError, LevelNotFoundError) as error:
            candidates = tuple(getattr(self.level_number_recognizer, "last_candidates", ()))
            self.logger.warning(
                "runtime.home.level_number_failed",
                cycle_id=cycle.cycle_id,
                raw_candidates=list(candidates),
                selected_candidate=None,
                error=str(error),
            )
            cycle.confirmed_home_level = None
            return False
        candidates = tuple(getattr(self.level_number_recognizer, "last_candidates", ()))
        selected = next(
            (candidate for candidate in candidates if parse_level_number(candidate) == number),
            str(number),
        )
        cycle.confirmed_home_level = number
        self.logger.info(
            "runtime.home.level_confirmed",
            cycle_id=cycle.cycle_id,
            confirmed_home_level=number,
            raw_candidates=list(candidates),
            selected_candidate=selected,
        )
        return True

    def _prepare_level_with_retries(
        self,
        capture: ScreenCapture,
        dispatcher: RuntimeScreenDispatcher,
        cycle: LevelCycleState,
    ) -> tuple[ScreenCapture, LevelSolutionPlan] | None:
        """Build a plan only from one fresh, positively playable frame."""
        while True:
            cycle.clear_recognition_attempt()
            cycle.previous_capture = capture
            try:
                geometry = self._detect_wheel_geometry(capture, cycle_id=cycle.cycle_id)
                if len(geometry.letters) not in {5, 6, 7}:
                    raise WheelGeometryDetectionError(
                        f"Expected 5, 6, or 7 wheel letters; detected {len(geometry.letters)}"
                    )
            except WheelGeometryDetectionError as error:
                retry_capture = self._retry_level_recognition(
                    dispatcher,
                    cycle,
                    event="runtime.level.waiting_for_letters",
                    error=error,
                )
                if retry_capture is None:
                    return None
                capture = retry_capture
                continue

            cycle.wheel_geometry = geometry
            self.logger.info(
                "runtime.level.screen_detected",
                cycle_id=cycle.cycle_id,
                wheel_visible=True,
                number_of_letters=len(geometry.letters),
            )
            title_candidates: tuple[str, ...]
            try:
                title_number = self.level_number_recognizer.recognize(capture)
                self.levels.get_level(title_number)
                title_candidates = tuple(
                    getattr(self.level_number_recognizer, "last_candidates", ())
                )
            except (OcrError, LevelNotFoundError) as error:
                title_candidates = tuple(
                    getattr(self.level_number_recognizer, "last_candidates", ())
                )
                if cycle.confirmed_home_level is not None and not title_candidates:
                    number = cycle.confirmed_home_level
                    self.logger.info(
                        "runtime.level.waiting_for_level_number",
                        cycle_id=cycle.cycle_id,
                        raw_candidates=[],
                        confirmed_home_level=number,
                        fallback_used=True,
                        error=str(error),
                    )
                else:
                    retry_capture = self._retry_level_recognition(
                        dispatcher,
                        cycle,
                        event="runtime.level.waiting_for_level_number",
                        error=error,
                    )
                    if retry_capture is None:
                        return None
                    capture = retry_capture
                    continue
            else:
                if (
                    cycle.confirmed_home_level is not None
                    and title_number != cycle.confirmed_home_level
                ):
                    confirmed_text = str(cycle.confirmed_home_level)
                    title_text = str(title_number)
                    title_is_partial = (
                        len(title_text) < len(confirmed_text)
                        and title_text in confirmed_text
                    )

                    if title_is_partial:
                        self.logger.warning(
                            "runtime.level.level_number_mismatch",
                            cycle_id=cycle.cycle_id,
                            confirmed_home_level=cycle.confirmed_home_level,
                            gameplay_title_level=title_number,
                            raw_candidates=list(title_candidates),
                            gameplay_candidate_is_partial=True,
                            selected_level=cycle.confirmed_home_level,
                            selection_reason=(
                                "confirmed_home_level_preserved_over_partial_gameplay_ocr"
                            ),
                        )
                        number = cycle.confirmed_home_level
                    else:
                        self.logger.warning(
                            "runtime.level.level_number_mismatch",
                            cycle_id=cycle.cycle_id,
                            confirmed_home_level=cycle.confirmed_home_level,
                            gameplay_title_level=title_number,
                            raw_candidates=list(title_candidates),
                            gameplay_candidate_is_partial=False,
                            selected_level=None,
                            selection_reason=(
                                "complete_conflicting_gameplay_level_requires_fresh_retry"
                            ),
                        )
                        retry_capture = self._retry_level_recognition(
                            dispatcher,
                            cycle,
                            event="runtime.level.waiting_for_level_number",
                            error=OcrError(
                                "Gameplay title does not match confirmed home level"
                            ),
                        )
                        if retry_capture is None:
                            return None
                        capture = retry_capture
                        continue
                else:
                    number = title_number

                self.logger.info(
                    "runtime.level.level_number_confirmed",
                    cycle_id=cycle.cycle_id,
                    confirmed_home_level=cycle.confirmed_home_level,
                    gameplay_title_level=title_number,
                    selected_level=number,
                    raw_candidates=list(title_candidates),
                )

            cycle.level_number = number
            cycle.validation_candidates = title_candidates
            self.logger.info(
                "runtime.level.detected",
                cycle_id=cycle.cycle_id,
                detected_level=number,
            )
            try:
                recognition = self._recognize_letters(capture, geometry, cycle_id=cycle.cycle_id)
                cycle.recognized_letters = recognition
                plan = self._plan_level_solution(
                    capture,
                    geometry,
                    recognition,
                    level_number=number,
                    cycle_id=cycle.cycle_id,
                )
            except WordMadnessError as error:
                retry_capture = self._retry_level_recognition(
                    dispatcher,
                    cycle,
                    event="runtime.level.waiting_for_letters",
                    error=error,
                )
                if retry_capture is None:
                    return None
                capture = retry_capture
                continue
            cycle.solution_plan = plan
            self.logger.info(
                "runtime.level.letters_validated",
                cycle_id=cycle.cycle_id,
                confirmed_home_level=cycle.confirmed_home_level,
                number_of_letters=len(recognition.letters),
                letters_validated=True,
            )
            return capture, plan

    def _retry_level_recognition(
        self,
        dispatcher: RuntimeScreenDispatcher,
        cycle: LevelCycleState,
        *,
        event: str,
        error: Exception,
    ) -> ScreenCapture | None:
        cycle.recognition_retry += 1
        self.logger.warning(
            event,
            cycle_id=cycle.cycle_id,
            attempt=cycle.recognition_retry,
            error=str(error),
        )
        self.logger.info(
            "runtime.level.recovery_retry",
            cycle_id=cycle.cycle_id,
            attempt=cycle.recognition_retry,
        )
        self.sleeper(0.5)
        capture = self._capture_debug_screenshot(
            f"{cycle.cycle_id}/recognition-retry-{cycle.recognition_retry:04d}.png"
        )
        dispatch = dispatcher.dispatch(capture)
        if dispatch.state in {
            RuntimeScreenState.LEVEL,
            RuntimeScreenState.UNKNOWN,
            RuntimeScreenState.TAP_TO_CONTINUE,
        }:
            return capture
        cycle.confirmed_home_level = None
        self.logger.info(
            "runtime.level.recovery_screen_changed",
            cycle_id=cycle.cycle_id,
            detected_state=dispatch.state.value,
        )
        return None

    def _recognize_level_with_retries(
        self, capture: ScreenCapture, *, attempts: int = 3
    ) -> tuple[int, ScreenCapture] | None:
        """Retry OCR on fresh frames, then return control to screen dispatch."""
        for attempt in range(1, attempts + 1):
            try:
                number = self.level_number_recognizer.recognize(capture)
                self.levels.get_level(number)
            except (OcrError, LevelNotFoundError) as error:
                self.logger.warning(
                    "runtime.level.ocr_failed",
                    attempt=attempt,
                    maximum_attempts=attempts,
                    raw_candidates=list(
                        getattr(self.level_number_recognizer, "last_candidates", ())
                    ),
                    error=str(error),
                )
                if attempt == attempts:
                    self.logger.error(
                        "runtime.level.ocr_recovery",
                        reason="attempts_exhausted",
                    )
                    return None
                self.sleeper(0.5)
                capture = self._capture_debug_screenshot(f"level-ocr-retry-{attempt}.png")
                classification = self._classify(capture)
                if classification.screen is not ScreenType.LEVEL_SCREEN:
                    self.logger.info(
                        "runtime.level.ocr_recovery",
                        reason="screen_changed",
                        detected_screen=classification.screen.value,
                    )
                    return None
            else:
                return number, capture
        return None

    def _log_start_level(
        self,
        point: PixelPoint,
        region: PixelRect | None = None,
        *,
        cycle_id: str | None = None,
    ) -> None:
        self.logger.info(
            "runtime.start_level.detected",
            cycle_id=cycle_id,
            button_left=region.left if region is not None else point.x,
            button_top=region.top if region is not None else point.y,
            button_width=region.width if region is not None else 0,
            button_height=region.height if region is not None else 0,
            ocr_crop_width=0,
            ocr_crop_height=0,
            template_confidence=None,
        )
        self.logger.info("runtime.start_level.tap", cycle_id=cycle_id, tap_x=point.x, tap_y=point.y)

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
            f"Unable to enter level: {reason} (detected {classification.screen.value})"
        )

    def _detect_wheel_geometry(
        self, capture: ScreenCapture, *, cycle_id: str | None = None
    ) -> LetterWheelGeometry:
        started = self.clock()
        debug_directory = (
            self.settings.debug_directory / cycle_id
            if cycle_id is not None
            else self.settings.debug_directory
        )
        try:
            geometry = self.wheel_detector.detect(capture)
            annotated_path, json_path = save_wheel_debug_artifacts(
                debug_directory,
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
            cycle_id=cycle_id,
            wheel_detected=True,
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
        *,
        cycle_id: str | None = None,
    ) -> WheelLetterRecognition:
        debug_directory = (
            self.settings.debug_directory / cycle_id
            if cycle_id is not None
            else self.settings.debug_directory
        )
        try:
            recognition = self.letter_recognizer.recognize(
                capture,
                geometry,
                debug_directory,
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
                cycle_id=cycle_id,
                index=letter.index,
                detected_character=letter.character,
                confidence=letter.confidence,
                elapsed_recognition_seconds=letter.elapsed_seconds,
                crop_filename=str(letter.crop_path),
            )
        self.logger.info(
            "runtime.letters.recognized",
            number_of_letters=len(recognition.letters),
            output_filename=str(debug_directory / "letters.json"),
        )
        return recognition

    def _plan_level_solution(
        self,
        capture: ScreenCapture,
        geometry: LetterWheelGeometry,
        recognition: WheelLetterRecognition,
        *,
        level_number: int,
        cycle_id: str | None = None,
    ) -> LevelSolutionPlan:
        started = self.clock()
        debug_directory = (
            self.settings.debug_directory / cycle_id if cycle_id else self.settings.debug_directory
        )
        try:
            plan = self.solution_planner.plan(level_number, recognition, geometry, capture.size)
            output_path = save_level_solution(plan, debug_directory)
        except WordMadnessError as error:
            self.logger.exception(
                "runtime.solution.planning_failed",
                planning_duration_seconds=self.clock() - started,
                error=str(error),
            )
            raise
        self.logger.info(
            "runtime.solution.planned",
            cycle_id=cycle_id,
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
        *,
        cycle_id: str | None = None,
    ) -> ScreenCapture:
        debug_directory = (
            self.settings.debug_directory / cycle_id
            if cycle_id is not None
            else self.settings.debug_directory
        )
        try:
            result = self.level_executor.execute(plan, before, debug_directory)
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
                word=word.word,
                number_of_letters=len(word.coordinates),
                number_of_segments=len(word.coordinates) - 1,
                segment_duration_ms=word.duration_ms // (len(word.coordinates) - 1),
                total_requested_duration_ms=word.duration_ms,
                actual_elapsed_duration_ms=round(word.elapsed_seconds * 1000),
                swipe_coordinates=coordinates,
                acceptance_verification=word.acceptance.accepted,
                changed_pixel_ratio=word.acceptance.changed_pixel_ratio,
                elapsed_execution_seconds=word.elapsed_seconds,
            )
        self.logger.info(
            "runtime.level.completed",
            cycle_id=cycle_id,
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
            home_template_confidence=result.home_template_confidence,
            start_button_confidence=result.start_button_confidence,
            combined_confidence=result.confidence,
            level_template_confidence=result.level_template_confidence,
            level_template_matched=result.level_template_matched,
            wheel_check_passed=result.wheel_visible,
            wheel_check_error=result.wheel_detection_error,
            elapsed_detection_seconds=self.clock() - started,
        )
        if result.screen is ScreenType.UNKNOWN:
            self._unknown_screenshot_number += 1
            destination = (
                self.settings.debug_directory
                / "unknown"
                / (f"unknown-{self._unknown_screenshot_number:04d}.png")
            )
            save_screenshot(capture.data, destination)
            self.logger.info(
                "runtime.screen.unknown_saved",
                output_filename=str(destination),
                sequence_number=self._unknown_screenshot_number,
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
    completion_overlay_detector: CompletionOverlayPort | None = None,
    clock: Clock = time.monotonic,
    sleeper: Sleeper = time.sleep,
) -> ApplicationRuntime:
    """Wire all production components without contacting a device at import time."""
    runtime_logger = logger or configure_logging(level=settings.log_level)
    android = android_factory(settings, runtime_logger)
    levels = level_factory()
    planner = SwipePathPlanner(
        segment_duration_ms=round(settings.swipe_segment_duration_seconds * 1000)
    )
    decisions = DecisionEngine()
    classifier = screen_classifier or ScreenClassifier()
    single_word_executor = SingleWordExecutor(
        android,
        word_acceptance_verifier or ImageDifferenceWordAcceptanceVerifier(),
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
        level_number_recognizer=level_number_recognizer
        or LevelNumberRecognizer(
            supported_levels=(
                frozenset(level.number for level in levels.all_levels())
                if isinstance(levels, JsonLevelRepository)
                else None
            ),
            debug_directory=settings.debug_directory,
        ),
        solution_planner=LevelSolutionPlanner(levels, planner),
        level_executor=LevelExecutor(
            android,
            single_word_executor,
            classifier,
            popup_close_button_detector or UpperRightPopupCloseDetector(),
            completion_overlay_detector or CompletionOverlayDetector(),
            logger=runtime_logger,
            inter_word_delay_seconds=settings.inter_word_safety_delay_seconds,
            clock=clock,
            sleeper=sleeper,
        ),
        clock=clock,
        sleeper=sleeper,
    )
