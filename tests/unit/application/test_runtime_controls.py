import io
from pathlib import Path

from PIL import Image, ImageDraw

from word_madness_bot.application.runtime_controls import (
    CompletionOverlayDetector,
    UpperRightPopupCloseDetector,
)
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


def _drawn_capture(draw_image: Image.Image) -> ScreenCapture:
    output = io.BytesIO()
    draw_image.save(output, format="PNG")
    return ScreenCapture(output.getvalue(), ScreenSize(*draw_image.size))


def test_detects_bright_tap_to_continue_line_in_lower_screen() -> None:
    image = Image.new("RGB", (400, 800), (25, 30, 45))
    draw = ImageDraw.Draw(image)
    for index in range(8):
        left = 90 + index * 28
        draw.rectangle((left, 560, left + 15, 590), fill=(245, 245, 245))

    assert CompletionOverlayDetector().tap_to_continue_visible(_drawn_capture(image))


def test_completion_home_button_prevents_overlay_and_back_detection() -> None:
    image = Image.new("RGB", (400, 800), (25, 30, 45))
    ImageDraw.Draw(image).rounded_rectangle(
        (80, 440, 320, 520),
        radius=30,
        fill=(245, 190, 20),
    )
    capture = _drawn_capture(image)
    detector = CompletionOverlayDetector()

    assert detector.completion_home_visible(capture)
    assert detector.completion_home_button(capture) == PixelRect(80, 440, 241, 81)
    assert not detector.tap_to_continue_visible(capture)
    assert not detector.daily_celebration_visible(capture)
    assert not detector.settings_visible(capture)


def test_detects_settings_layout_without_touching_internal_controls() -> None:
    image = Image.new("RGB", (400, 800), (25, 30, 45))
    draw = ImageDraw.Draw(image)
    draw.polygon(
        ((18, 55), (42, 35), (42, 48), (58, 48), (58, 62), (42, 62), (42, 75)), fill="white"
    )
    for top in (150, 260, 370, 480, 590):
        for left in (70, 95, 120, 145, 170, 195):
            draw.rectangle((left, top, left + 16, top + 24), fill="white")

    assert CompletionOverlayDetector().settings_visible(_drawn_capture(image))


def test_large_intelligent_heading_is_primary_completion_home_signal() -> None:
    image = Image.new("RGB", (400, 800), (25, 30, 45))
    draw = ImageDraw.Draw(image)
    for index in range(11):
        left = 45 + index * 28
        draw.rectangle((left, 105, left + 15, 150), fill=(245, 245, 245))

    capture = _drawn_capture(image)

    assert CompletionOverlayDetector().completion_home_visible(capture)
