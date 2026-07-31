"""Composition root for the production application."""

from __future__ import annotations

import time
from collections.abc import Callable
from dataclasses import dataclass, field

from word_madness_bot.application.decision_engine import DecisionEngine
from word_madness_bot.application.game_loop import GameLoop
from word_madness_bot.application.ports.android import AndroidPort
from word_madness_bot.application.ports.levels import LevelRepository
from word_madness_bot.application.recovery import RecoveryStrategy, RetryPolicy, TimeoutPolicy
from word_madness_bot.config.logging import StructuredLogger, configure_logging
from word_madness_bot.config.settings import Settings
from word_madness_bot.domain.errors import ScreenshotError, WordMadnessError
from word_madness_bot.gameplay.ads import AdvertisementPolicy
from word_madness_bot.gameplay.swipe_generator import SwipePathPlanner
from word_madness_bot.infrastructure.adb.client import AdbClient
from word_madness_bot.infrastructure.adb.screenshot import save_screenshot
from word_madness_bot.infrastructure.levels.json_repository import JsonLevelRepository

AndroidFactory = Callable[[Settings, StructuredLogger], AndroidPort]
LevelFactory = Callable[[], LevelRepository]
Clock = Callable[[], float]


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
    clock: Clock = field(default=time.monotonic, repr=False)
    _started: bool = False

    def start(self, *, dry_run: bool = False) -> None:
        """Verify the device and acquire one validated debug screenshot."""
        self.logger.info("runtime.starting", dry_run=dry_run)
        if not dry_run:
            device = self.android.select_device()
            self.android.verify_connection()
            self.logger.info("runtime.device.ready", serial=device.serial)
            self._capture_debug_screenshot()
        self._started = True
        self.logger.info("runtime.started", dry_run=dry_run)

    def _capture_debug_screenshot(self) -> None:
        destination = self.settings.debug_directory / "screenshot.png"
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
    clock: Clock = time.monotonic,
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
        clock=clock,
    )
