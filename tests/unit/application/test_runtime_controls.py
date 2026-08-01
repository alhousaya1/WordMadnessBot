import io
from pathlib import Path

from PIL import Image, ImageDraw

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

    assert result.level == 90
    assert (
        result.region.left + result.region.width // 2,
        result.region.top + result.region.height // 2,
    ) == (720, 2038)


def test_locates_alternate_yellow_button_independently_of_text() -> None:
    image = Image.new("RGB", (1080, 2400), (80, 70, 130))
    draw = ImageDraw.Draw(image)
    draw.rounded_rectangle(
        (180, 1500, 900, 1700),
        radius=8,
        fill=(235, 180, 45),
    )
    draw.rectangle((390, 1570, 690, 1630), fill=(35, 30, 25))
    output = io.BytesIO()
    image.save(output, format="PNG")
    capture = ScreenCapture(output.getvalue(), ScreenSize(1080, 2400))

    region = YellowLevelButtonDetector().locate(capture)

    assert region == PixelRect(180, 1500, 721, 201)
    assert (
        region.left + region.width // 2,
        region.top + region.height // 2,
    ) == (540, 1600)


def test_finds_close_button_in_upper_right_region() -> None:
    result = UpperRightPopupCloseDetector().detect(
        _capture("daily_dash_popup.png")
    )

    assert result == PixelRect(1200, 750, 180, 190)


def test_does_not_find_close_button_on_home_screen() -> None:
    assert (
        UpperRightPopupCloseDetector().detect(_capture("home_screen.png")) is None
    )
