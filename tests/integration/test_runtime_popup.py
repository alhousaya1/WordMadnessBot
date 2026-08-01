"""Integration of popup dismissal and bounded home-to-level navigation."""

from __future__ import annotations

import io
import json
from importlib.resources import files
from pathlib import Path
from typing import Any, cast

from PIL import Image, ImageDraw

from word_madness_bot.application.ports.android import AndroidPort
from word_madness_bot.application.word_execution import AcceptanceResult
from word_madness_bot.bootstrap import build_runtime
from word_madness_bot.config.logging import configure_logging
from word_madness_bot.config.settings import Settings
from word_madness_bot.domain.geometry import PixelPoint, ScreenSize
from word_madness_bot.domain.models import (
    DeviceDescriptor,
    DeviceState,
    ScreenCapture,
    SwipeExecutionReceipt,
    SwipePath,
)
from word_madness_bot.infrastructure.levels.json_repository import JsonLevelRepository


class Android:
    def __init__(self, captures: tuple[ScreenCapture, ...]) -> None:
        self.captures = iter(captures)
        self.taps: list[PixelPoint] = []
        self.swipes: list[SwipePath] = []

    def select_device(self, serial: str | None = None) -> DeviceDescriptor:
        return DeviceDescriptor("integration", DeviceState.ONLINE)

    def verify_connection(self) -> bool:
        return True

    def capture_screenshot(self) -> ScreenCapture:
        return next(self.captures)

    def tap(self, point: PixelPoint) -> None:
        self.taps.append(point)

    def swipe(self, path: SwipePath) -> SwipeExecutionReceipt:
        self.swipes.append(path)
        return SwipeExecutionReceipt(("fake",), (0, path.duration_ms))

    def __getattr__(self, name: str) -> Any:
        return lambda *args, **kwargs: None

class AcceptanceVerifier:
    def verify(
        self, before: ScreenCapture, after: ScreenCapture, confirmation: ScreenCapture
    ) -> AcceptanceResult:
        return AcceptanceResult(True, 0.01, 1.0)

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
    after_image = Image.open(level).convert("L")
    ImageDraw.Draw(after_image).rectangle((480, 500, 700, 650), fill=0)
    after_bytes = io.BytesIO()
    after_image.save(after_bytes, format="PNG")
    android = Android(
        (
            ScreenCapture(popup.read_bytes(), ScreenSize(1440, 3120)),
            ScreenCapture(home.read_bytes(), ScreenSize(1440, 3120)),
            ScreenCapture(level.read_bytes(), ScreenSize(1440, 3120)),
            ScreenCapture(after_bytes.getvalue(), ScreenSize(1440, 3120)),
            ScreenCapture(after_bytes.getvalue(), ScreenSize(1440, 3120)),
            ScreenCapture(after_bytes.getvalue(), ScreenSize(1440, 3120)),
            ScreenCapture(after_bytes.getvalue(), ScreenSize(1440, 3120)),
            ScreenCapture(after_bytes.getvalue(), ScreenSize(1440, 3120)),
            ScreenCapture(after_bytes.getvalue(), ScreenSize(1440, 3120)),
            ScreenCapture(after_bytes.getvalue(), ScreenSize(1440, 3120)),
            ScreenCapture(after_bytes.getvalue(), ScreenSize(1440, 3120)),
            ScreenCapture(after_bytes.getvalue(), ScreenSize(1440, 3120)),
            ScreenCapture(after_bytes.getvalue(), ScreenSize(1440, 3120)),
            ScreenCapture(after_bytes.getvalue(), ScreenSize(1440, 3120)),
            ScreenCapture(after_bytes.getvalue(), ScreenSize(1440, 3120)),
            ScreenCapture(after_bytes.getvalue(), ScreenSize(1440, 3120)),
            ScreenCapture(after_bytes.getvalue(), ScreenSize(1440, 3120)),
            ScreenCapture(after_bytes.getvalue(), ScreenSize(1440, 3120)),
            ScreenCapture(after_bytes.getvalue(), ScreenSize(1440, 3120)),
            ScreenCapture(after_bytes.getvalue(), ScreenSize(1440, 3120)),
            ScreenCapture(after_bytes.getvalue(), ScreenSize(1440, 3120)),
            ScreenCapture(after_bytes.getvalue(), ScreenSize(1440, 3120)),
            ScreenCapture(after_bytes.getvalue(), ScreenSize(1440, 3120)),
            ScreenCapture(after_bytes.getvalue(), ScreenSize(1440, 3120)),
            ScreenCapture(after_bytes.getvalue(), ScreenSize(1440, 3120)),
            ScreenCapture(after_bytes.getvalue(), ScreenSize(1440, 3120)),
            ScreenCapture(home.read_bytes(), ScreenSize(1440, 3120)),
        )
    )
    runtime = build_runtime(
        Settings(debug_directory=tmp_path),
        logger=configure_logging(name="test.popup.integration"),
        android_factory=lambda settings, logger: cast(AndroidPort, android),
        level_factory=JsonLevelRepository.from_package,
        sleeper=lambda _: None,
        word_acceptance_verifier=AcceptanceVerifier(),
    )
    runtime.start(max_levels=1)
    runtime.shutdown()
    assert android.taps == [PixelPoint(1290, 845), PixelPoint(721, 2043)]
    assert len(android.swipes) == 8
    assert (tmp_path / "screenshot-1.png").exists()
    assert (tmp_path / "screenshot-2.png").exists()
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
    solution = json.loads((tmp_path / "level_solution.json").read_text(encoding="utf-8"))
    assert solution["level"] == 90
    assert solution["recognized_letters"] == list("OUNFD")
    assert [item["word"] for item in solution["solutions"]] == [
        "DON", "DUN", "DUO", "FUN", "NOD", "FOND", "FUND", "FOUND"
    ]
    swipe = json.loads((tmp_path / "swipe.json").read_text(encoding="utf-8"))
    assert swipe["word"] == "FOUND"
    assert swipe["accepted"] is True
    assert (tmp_path / "word_before.png").exists()
    assert (tmp_path / "word_after.png").exists()
    assert (tmp_path / "word_confirmed.png").exists()
