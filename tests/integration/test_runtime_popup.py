"""Integration of popup dismissal and bounded home-to-level navigation."""

from __future__ import annotations

import io
import json
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
    image = Image.new("L", (1400, 1000), 24)
    for name, left, top in templates:
        data = files("word_madness_bot.resources.templates").joinpath(name).read_bytes()
        image.paste(Image.open(io.BytesIO(data)).convert("L"), (left, top))
    output = io.BytesIO()
    image.save(output, format="PNG")
    return ScreenCapture(output.getvalue(), ScreenSize(1400, 1000))


def test_runtime_dismisses_popup_enters_level_and_saves_every_capture(
    tmp_path: Path,
) -> None:
    fixtures = Path(__file__).parents[1] / "fixtures" / "images"
    popup = fixtures / "daily_dash_popup.png"
    home = fixtures / "home_screen.png"
    level = fixtures / "level_screen.png"
    android = Android(
        (
            ScreenCapture(popup.read_bytes(), ScreenSize(1440, 3120)),
            ScreenCapture(home.read_bytes(), ScreenSize(1440, 3120)),
            ScreenCapture(level.read_bytes(), ScreenSize(1440, 3120)),
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
    assert android.taps == [PixelPoint(1290, 845), PixelPoint(720, 2040)]
    assert (tmp_path / "screenshot-1.png").exists()
    assert (tmp_path / "screenshot-2.png").exists()
    assert (tmp_path / "screenshot-3.png").exists()
    assert (tmp_path / "letter-wheel-annotated.png").exists()
    assert (tmp_path / "letter-wheel-geometry.json").exists()
    crops = sorted((tmp_path / "letters").glob("letter-*.png"))
    assert [path.name for path in crops] == [
        "letter-0.png",
        "letter-1.png",
        "letter-2.png",
        "letter-3.png",
        "letter-4.png",
    ]
    payload = json.loads((tmp_path / "letters.json").read_text(encoding="utf-8"))
    assert "".join(item["character"] for item in payload["letters"]) == "OUNFD"
