from __future__ import annotations

import io
import logging
import struct
from pathlib import Path
from typing import cast

import pytest

from word_madness_bot.application.ports.android import AndroidPort
from word_madness_bot.bootstrap import build_runtime
from word_madness_bot.config.logging import StructuredLogger, configure_logging
from word_madness_bot.config.settings import Settings
from word_madness_bot.domain.errors import ScreenshotError
from word_madness_bot.domain.geometry import ScreenSize
from word_madness_bot.domain.models import DeviceDescriptor, DeviceState, ScreenCapture
from word_madness_bot.infrastructure.levels.json_repository import JsonLevelRepository

PNG = b"\x89PNG\r\n\x1a\n" + b"\x00\x00\x00\rIHDR" + struct.pack(">II", 1080, 2400)


class FakeAndroid:
    def __init__(self, screenshot: bytes = PNG) -> None:
        self.selected = 0
        self.verified = 0
        self.captures = 0
        self.screenshot = screenshot

    def select_device(self, serial: str | None = None) -> DeviceDescriptor:
        self.selected += 1
        return DeviceDescriptor(serial or "test", DeviceState.ONLINE)

    def verify_connection(self) -> bool:
        self.verified += 1
        return True

    def capture_screenshot(self) -> ScreenCapture:
        self.captures += 1
        return ScreenCapture(self.screenshot, ScreenSize(1080, 2400))



def test_build_runtime_wires_existing_production_components(tmp_path: Path) -> None:
    android = FakeAndroid()
    runtime = build_runtime(
        Settings(debug_directory=tmp_path),
        logger=StructuredLogger(logging.getLogger("test.bootstrap")),
        android_factory=lambda settings, supplied_logger: cast(AndroidPort, android),
        level_factory=lambda: JsonLevelRepository.from_json('{"levels": []}'),
    )
    assert runtime.android is cast(AndroidPort, android)
    assert runtime.game_loop.android is cast(AndroidPort, android)
    assert runtime.game_loop.levels is runtime.levels


def test_start_captures_valid_png_and_logs_metadata(tmp_path: Path) -> None:
    android = FakeAndroid()
    stream = io.StringIO()
    runtime = build_runtime(
        Settings(debug_directory=tmp_path),
        logger=configure_logging(name="test.capture", stream=stream),
        android_factory=lambda settings, supplied_logger: cast(AndroidPort, android),
        level_factory=lambda: JsonLevelRepository.from_json('{"levels": []}'),
        clock=iter((10.0, 10.25)).__next__,
    )
    runtime.start()
    assert (tmp_path / "screenshot.png").read_bytes() == PNG
    assert (android.selected, android.verified, android.captures) == (1, 1, 1)
    output = stream.getvalue()
    assert '"resolution": "1080x2400"' in output
    assert '"capture_duration_seconds": 0.25' in output
    assert str(tmp_path / "screenshot.png").replace("\\", "\\\\") in output


def test_capture_failure_is_logged_and_raised(tmp_path: Path) -> None:
    stream = io.StringIO()
    runtime = build_runtime(
        Settings(debug_directory=tmp_path),
        logger=configure_logging(name="test.failure", stream=stream),
        android_factory=lambda settings, supplied_logger: cast(AndroidPort, FakeAndroid(b"bad")),
        level_factory=lambda: JsonLevelRepository.from_json('{"levels": []}'),
        clock=iter((2.0, 2.1)).__next__,
    )
    with pytest.raises(ScreenshotError):
        runtime.start()
    assert '"event": "runtime.screenshot.failed"' in stream.getvalue()
    assert not (tmp_path / "screenshot.png").exists()


def test_dry_run_has_no_device_or_screenshot_io(tmp_path: Path) -> None:
    android = FakeAndroid()
    runtime = build_runtime(
        Settings(debug_directory=tmp_path),
        logger=StructuredLogger(logging.getLogger("test.dry-run")),
        android_factory=lambda settings, supplied_logger: cast(AndroidPort, android),
        level_factory=lambda: JsonLevelRepository.from_json('{"levels": []}'),
    )
    runtime.start(dry_run=True)
    runtime.shutdown()
    runtime.shutdown()
    assert (android.selected, android.verified, android.captures) == (0, 0, 0)
    assert not (tmp_path / "screenshot.png").exists()
