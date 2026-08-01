from pathlib import Path

from PIL import Image

from word_madness_bot.application.runtime_controls import UpperRightPopupCloseDetector
from word_madness_bot.domain.geometry import PixelRect, ScreenSize
from word_madness_bot.domain.models import ScreenCapture

FIXTURES = Path(__file__).parents[2] / "fixtures" / "images"


def _capture(name: str) -> ScreenCapture:
    path = FIXTURES / name
    with Image.open(path) as image:
        size = ScreenSize(*image.size)
    return ScreenCapture(path.read_bytes(), size)


def test_finds_close_button_in_upper_right_region() -> None:
    result = UpperRightPopupCloseDetector().detect(_capture("daily_dash_popup.png"))

    assert result == PixelRect(1200, 750, 180, 190)


def test_does_not_find_close_button_on_home_screen() -> None:
    assert UpperRightPopupCloseDetector().detect(_capture("home_screen.png")) is None