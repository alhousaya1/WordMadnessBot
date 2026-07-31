"""Integration of runtime capture, OpenCV classification, and popup dismissal."""

from __future__ import annotations

import io
from importlib.resources import files
from pathlib import Path
from typing import Any, cast

from PIL import Image

from word_madness_bot.application.ports.android import AndroidPort
from word_madness_bot.bootstrap import build_runtime
from word_madness_bot.config.logging import configure_logging
from word_madness_bot.config.settings import Settings
from word_madness_bot.domain.geometry import PixelPoint, ScreenSize
from word_madness_bot.domain.models import DeviceDescriptor, DeviceState, ScreenCapture
from word_madness_bot.infrastructure.levels.json_repository import JsonLevelRepository


class Android:
    def __init__(self, captures: tuple[ScreenCapture, ...]) -> None:
        self.captures = iter(captures)
        self.taps: list[PixelPoint] = []

    def select_device(self, serial: str | None = None) -> DeviceDescriptor:
        return DeviceDescriptor("integration", DeviceState.ONLINE)

    def verify_connection(self) -> bool:
        return True

    def capture_screenshot(self) -> ScreenCapture:
        return next(self.captures)

    def tap(self, point: PixelPoint) -> None:
        self.taps.append(point)

    def __getattr__(self, name: str) -> Any:
        return lambda *args, **kwargs: None


def _capture(*templates: tuple[str, int, int]) -> ScreenCapture:
    image = Image.new("L", (180, 240), 24)
    for name, left, top in templates:
        data = files("word_madness_bot.resources.templates").joinpath(name).read_bytes()
        template = Image.open(io.BytesIO(data)).convert("L")
        image.paste(template, (left, top))
    output = io.BytesIO()
    image.save(output, format="PNG")
    return ScreenCapture(output.getvalue(), ScreenSize(180, 240))


def test_runtime_dismisses_daily_dash_and_exits_after_reclassification(tmp_path: Path) -> None:
    android = Android(
        (
            _capture(("daily_dash_popup.png", 30, 70), ("daily_dash_close.png", 140, 10)),
            _capture(("home_screen.png", 60, 90)),
        )
    )
    runtime = build_runtime(
        Settings(debug_directory=tmp_path),
        logger=configure_logging(name="test.popup.integration"),
        android_factory=lambda settings, logger: cast(AndroidPort, android),
        level_factory=lambda: JsonLevelRepository.from_json('{"levels": []}'),
        sleeper=lambda _: None,
    )
    runtime.start()
    runtime.shutdown()
    assert android.taps == [PixelPoint(150, 20)]
    assert (tmp_path / "screenshot-1.png").exists()
    assert (tmp_path / "screenshot-2.png").exists()
