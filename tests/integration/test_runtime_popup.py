"""Integration of runtime capture, real-template classification, and popup dismissal."""

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


def _home_capture() -> ScreenCapture:
    image = Image.new("L", (800, 500), 24)
    data = files("word_madness_bot.resources.templates").joinpath("home_screen.png").read_bytes()
    image.paste(Image.open(io.BytesIO(data)).convert("L"), (50, 50))
    output = io.BytesIO()
    image.save(output, format="PNG")
    return ScreenCapture(output.getvalue(), ScreenSize(800, 500))


def test_runtime_dismisses_supplied_daily_dash_and_reclassifies(tmp_path: Path) -> None:
    fixture = Path(__file__).parents[1] / "fixtures" / "images" / "daily_dash_popup.png"
    android = Android(
        (
            ScreenCapture(fixture.read_bytes(), ScreenSize(1440, 3120)),
            _home_capture(),
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
    assert android.taps == [PixelPoint(1290, 845)]
    assert (tmp_path / "screenshot-1.png").exists()
    assert (tmp_path / "screenshot-2.png").exists()
