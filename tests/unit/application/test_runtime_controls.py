from pathlib import Path

from PIL import Image

from word_madness_bot.application.runtime_controls import (
    UpperRightPopupCloseDetector,
    YellowLevelButtonDetector,
)
from word_madness_bot.domain.geometry import PixelRect, ScreenSize
from word_madness_bot.domain.models import ScreenCapture

FIXTURES = Path(__file__).parents[2] / "fixtures" / "images"


def _capture(name: str) -> ScreenCapture:
    path = FIXTURES / name
    with Image.open(path) as image:
        size = ScreenSize(*image.size)
    return ScreenCapture(path.read_bytes(), size)


def test_detects_yellow_rectangle_and_reads_only_its_level_text() -> None:
    result = YellowLevelButtonDetector().detect(_capture("home_screen.png"))

    assert result.region == PixelRect(274, 1940, 894, 196)
    assert result.level == 90


def test_finds_close_button_in_upper_right_region() -> None:
    result = UpperRightPopupCloseDetector().detect(
        _capture("daily_dash_popup.png")
    )

    assert result == PixelRect(1200, 750, 180, 190)


def test_does_not_find_close_button_on_home_screen() -> None:
    assert (
        UpperRightPopupCloseDetector().detect(_capture("home_screen.png")) is None
    )