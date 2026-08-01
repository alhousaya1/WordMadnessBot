"""Whole-level execution composed from the single-word executor."""

from __future__ import annotations

import time
from collections.abc import Callable
from dataclasses import dataclass, replace
from pathlib import Path
from typing import Protocol

from word_madness_bot.application.ports.android import AndroidPort
from word_madness_bot.application.runtime_controls import PopupCloseButtonPort
from word_madness_bot.application.solution_planning import LevelSolutionPlan
from word_madness_bot.application.word_execution import (
    SingleWordExecutor,
    WordExecutionResult,
)
from word_madness_bot.domain.errors import WordExecutionError, WordNotAcceptedError
from word_madness_bot.domain.geometry import PixelPoint
from word_madness_bot.domain.models import ScreenCapture
from word_madness_bot.vision.screen_classifier import ScreenClassification, ScreenType

Sleeper = Callable[[float], None]


class LevelScreenClassifier(Protocol):
    """Classify captures while waiting for a completed level to return home."""

    def classify(self, capture: ScreenCapture) -> ScreenClassification: ...


@dataclass(frozen=True, slots=True)
class LevelExecutionResult:
    """Accepted word results and the home capture following level completion."""

    words: tuple[WordExecutionResult, ...]
    home_capture: ScreenCapture


class LevelExecutor:
    """Execute every planned word, then wait for the level-completion transition."""

    def __init__(
        self,
        android: AndroidPort,
        word_executor: SingleWordExecutor,
        screen_classifier: LevelScreenClassifier,
        popup_close_detector: PopupCloseButtonPort | None = None,
        *,
        completion_animation_wait_seconds: float = 2.0,
        home_poll_wait_seconds: float = 0.5,
        popup_dismiss_wait_seconds: float = 2.0,
        swipe_duration_ms: int = 500,
        sleeper: Sleeper = time.sleep,
    ) -> None:
        if completion_animation_wait_seconds < 0:
            raise ValueError("completion_animation_wait_seconds cannot be negative")
        if home_poll_wait_seconds < 0:
            raise ValueError("home_poll_wait_seconds cannot be negative")
        if swipe_duration_ms <= 0:
            raise ValueError("swipe_duration_ms must be positive")
        if popup_dismiss_wait_seconds < 0:
            raise ValueError("popup_dismiss_wait_seconds cannot be negative")
        self.android = android
        self.word_executor = word_executor
        self.screen_classifier = screen_classifier
        self.popup_close_detector = popup_close_detector
        self.completion_animation_wait_seconds = completion_animation_wait_seconds
        self.home_poll_wait_seconds = home_poll_wait_seconds
        self.popup_dismiss_wait_seconds = popup_dismiss_wait_seconds
        self.swipe_duration_ms = swipe_duration_ms
        self.sleeper = sleeper

    def execute(
        self,
        plan: LevelSolutionPlan,
        before: ScreenCapture,
        debug_directory: Path,
    ) -> LevelExecutionResult:
        """Execute and verify all solutions in order, stopping on the first failure."""
        if not plan.solutions:
            raise WordExecutionError("Level solution plan contains no words")

        results: list[WordExecutionResult] = []
        current = before
        for solution in plan.solutions:
            single_word_plan = LevelSolutionPlan(
                plan.level,
                plan.recognized_letters,
                (replace(solution, duration_ms=self.swipe_duration_ms),),
            )
            result = self.word_executor.execute(
                single_word_plan,
                current,
                debug_directory,
            )
            if not result.acceptance.accepted:
                raise WordNotAcceptedError(result.word, result.acceptance.changed_pixel_ratio)
            results.append(result)
            current = result.after_capture

        self.sleeper(self.completion_animation_wait_seconds)
        while True:
            close_button = (
                None
                if self.popup_close_detector is None
                else self.popup_close_detector.detect(current)
            )
            if close_button is not None:
                self.android.tap(
                    PixelPoint(
                        close_button.left + close_button.width // 2,
                        close_button.top + close_button.height // 2,
                    )
                )
                self.sleeper(self.popup_dismiss_wait_seconds)
                current = self.android.capture_screenshot()
                continue
            classification = self.screen_classifier.classify(current)
            if classification.screen is ScreenType.HOME_SCREEN:
                return LevelExecutionResult(tuple(results), current)
            self.sleeper(self.home_poll_wait_seconds)
            current = self.android.capture_screenshot()
