"""Composition root for the production application."""

from __future__ import annotations

import time
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import NoReturn, Protocol

from word_madness_bot.application.decision_engine import DecisionEngine
from word_madness_bot.application.game_loop import GameLoop
from word_madness_bot.application.ports.android import AndroidPort
from word_madness_bot.application.ports.levels import LevelRepository
from word_madness_bot.application.recovery import RecoveryStrategy, RetryPolicy, TimeoutPolicy
from word_madness_bot.config.logging import StructuredLogger, configure_logging
from word_madness_bot.config.settings import Settings
from word_madness_bot.domain.errors import (
    RuntimeNavigationError,
    ScreenshotError,
    WordMadnessError,
)
from word_madness_bot.domain.geometry import PixelPoint
from word_madness_bot.domain.models import ScreenCapture
from word_madness_bot.gameplay.ads import AdvertisementPolicy
from word_madness_bot.gameplay.swipe_generator import SwipePathPlanner
from word_madness_bot.infrastructure.adb.client import AdbClient
from word_madness_bot.infrastructure.adb.screenshot import save_screenshot
from word_madness_bot.infrastructure.levels.json_repository import JsonLevelRepository
from word_madness_bot.vision.screen_classifier import (
    ScreenClassification,
    ScreenClassifier,
    ScreenType,
)

AndroidFactory = Callable[[Settings, StructuredLogger], AndroidPort]
LevelFactory = Callable[[], LevelRepository]
Clock = Callable[[], float]
Sleeper = Callable[[float], None]


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
    clock: Clock = field(default=time.monotonic, repr=False)
    sleeper: Sleeper = field(default=time.sleep, repr=False)
    _started: bool = False

    def start(self, *, dry_run: bool = False) -> None:
        """Navigate from the current screen into one playable level."""
        self.logger.info("runtime.starting", dry_run=dry_run)
        if not dry_run:
            device = self.android.select_device()
            self.android.verify_connection()
            self.logger.info("runtime.device.ready", serial=device.serial)
            screenshot_number = 1
            classification = self._classify(
                self._capture_debug_screenshot(f"screenshot-{screenshot_number}.png")
            )

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
                classification = self._classify(
                    self._capture_debug_screenshot(
                        f"screenshot-{screenshot_number}.png"
                    )
                )

            if classification.screen is ScreenType.HOME_SCREEN:
                if classification.start_button is None:
                    self._raise_navigation_failure(
                        classification, reason="start_level_button_not_found"
                    )
                region = classification.start_button
                point = PixelPoint(
                    region.left + region.width // 2,
                    region.top + region.height // 2,
                )
                self.logger.info(
                    "runtime.start_level.detected",
                    button_left=region.left,
                    button_top=region.top,
                    button_width=region.width,
                    button_height=region.height,
                    template_confidence=classification.start_button_confidence,
                )
                self.logger.info(
                    "runtime.start_level.tap",
                    tap_x=point.x,
                    tap_y=point.y,
                )
                self.android.tap(point)
                self.sleeper(2.0)
                screenshot_number += 1
                classification = self._classify(
                    self._capture_debug_screenshot(
                        f"screenshot-{screenshot_number}.png"
                    )
                )

            if classification.screen is not ScreenType.LEVEL_SCREEN:
                self._raise_navigation_failure(
                    classification, reason="level_screen_not_reached"
                )
            self.logger.info(
                "runtime.level.entered",
                template_confidence=classification.confidence,
            )
        self._started = True
        self.logger.info("runtime.started", dry_run=dry_run)

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
    clock: Clock = time.monotonic,
    sleeper: Sleeper = time.sleep,
) -> ApplicationRuntime:
    """Wire all production components without contacting a device at import time."""
    runtime_logger = logger or configure_logging(level=settings.log_level)
    android = android_factory(settings, runtime_logger)
    levels = level_factory()
    planner = SwipePathPlanner()
    decisions = DecisionEngine()
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
        screen_classifier=screen_classifier or ScreenClassifier(),
        clock=clock,
        sleeper=sleeper,
    )
