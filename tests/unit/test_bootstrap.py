from __future__ import annotations

import logging
from typing import cast

from word_madness_bot.application.ports.android import AndroidPort
from word_madness_bot.bootstrap import build_runtime
from word_madness_bot.config.logging import StructuredLogger
from word_madness_bot.config.settings import Settings
from word_madness_bot.domain.models import DeviceDescriptor, DeviceState
from word_madness_bot.infrastructure.levels.json_repository import JsonLevelRepository


class FakeAndroid:
    def __init__(self) -> None:
        self.selected = 0
        self.verified = 0

    def select_device(self, serial: str | None = None) -> DeviceDescriptor:
        self.selected += 1
        return DeviceDescriptor(serial or "test", DeviceState.ONLINE)

    def verify_connection(self) -> bool:
        self.verified += 1
        return True


def test_build_runtime_wires_existing_production_components() -> None:
    android = FakeAndroid()
    logger = StructuredLogger(logging.getLogger("test.bootstrap"))
    runtime = build_runtime(
        Settings(),
        logger=logger,
        android_factory=lambda settings, supplied_logger: cast(AndroidPort, android),
        level_factory=lambda: JsonLevelRepository.from_json('{"levels": []}'),
    )
    assert runtime.android is cast(AndroidPort, android)
    assert runtime.game_loop.android is cast(AndroidPort, android)
    assert runtime.game_loop.levels is runtime.levels


def test_dry_run_has_no_device_io_and_shutdown_is_idempotent() -> None:
    android = FakeAndroid()
    runtime = build_runtime(
        Settings(),
        logger=StructuredLogger(logging.getLogger("test.dry-run")),
        android_factory=lambda settings, supplied_logger: cast(AndroidPort, android),
        level_factory=lambda: JsonLevelRepository.from_json('{"levels": []}'),
    )
    runtime.start(dry_run=True)
    runtime.shutdown()
    runtime.shutdown()
    assert (android.selected, android.verified) == (0, 0)
