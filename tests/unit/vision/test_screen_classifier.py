from __future__ import annotations

import io
from importlib.resources import files
from pathlib import Path

import pytest
from PIL import Image, ImageDraw

from word_madness_bot.domain.geometry import PixelRect, ScreenSize
from word_madness_bot.domain.models import ScreenCapture
from word_madness_bot.vision.screen_classifier import ScreenClassifier, ScreenType


def _template(name: str) -> Image.Image:
    data = files("word_madness_bot.resources.templates").joinpath(name).read_bytes()
    return Image.open(io.BytesIO(data)).convert("L")


def _capture(*templates: tuple[str, int, int]) -> ScreenCapture:
    image = Image.new("L", (1400, 1000), 24)
    for name, left, top in templates:
        image.paste(_template(name), (left, top))
    output = io.BytesIO()
    image.save(output, format="PNG")
    return ScreenCapture(output.getvalue(), ScreenSize(1400, 1000))


@pytest.mark.parametrize(
    ("template", "expected"),
    [
        ("home_screen.png", ScreenType.HOME_SCREEN),
        ("level_screen.png", ScreenType.LEVEL_SCREEN),
    ],
)
def test_classifies_supported_non_popup_screens(template: str, expected: ScreenType) -> None:
    result = ScreenClassifier().classify(_capture((template, 30, 80)))
    assert result.screen is expected
    assert result.confidence >= 0.9
    assert result.close_button is None


def test_visible_wheel_overrides_failed_level_template() -> None:
    screenshot = Path(__file__).parents[2] / "fixtures" / "images" / "level_screen.png"
    capture = ScreenCapture(screenshot.read_bytes(), ScreenSize(1440, 3120))
    classifier = ScreenClassifier()
    classifier._templates[ScreenType.LEVEL_SCREEN] = classifier._templates[ScreenType.HOME_SCREEN]

    result = classifier.classify(capture)

    assert result.screen is ScreenType.LEVEL_SCREEN
    assert result.confidence == 1.0
    assert result.wheel_visible is True
    assert result.level_template_matched is False


def test_classifies_daily_dash_and_locates_close_button() -> None:
    result = ScreenClassifier().classify(
        _capture(("daily_dash_popup.png", 30, 70), ("daily_dash_close.png", 600, 280))
    )
    assert result.screen is ScreenType.DAILY_DASH_POPUP
    assert result.close_button is not None
    assert result.close_button.left + result.close_button.width // 2 == 690
    assert result.close_button.top + result.close_button.height // 2 == 375


def test_locates_start_level_button_on_home_screen() -> None:
    result = ScreenClassifier().classify(
        _capture(("home_screen.png", 30, 80), ("start_level_button.png", 300, 500))
    )
    assert result.screen is ScreenType.HOME_SCREEN
    assert result.start_button is not None
    assert result.start_button.left == 300
    assert result.start_button.top == 500
    assert result.start_button_confidence is not None
    assert result.start_button_confidence >= 0.99


def test_supplied_home_screenshot_locates_start_button() -> None:
    screenshot = Path(__file__).parents[2] / "fixtures" / "images" / "home_screen.png"
    result = ScreenClassifier().classify(
        ScreenCapture(screenshot.read_bytes(), ScreenSize(1440, 3120))
    )
    assert result.screen is ScreenType.HOME_SCREEN
    assert result.start_button == PixelRect(260, 1930, 920, 220)
    assert result.start_button_confidence is not None
    assert result.start_button_confidence >= 0.99


def test_supplied_daily_dash_screenshot_regression() -> None:
    screenshot = Path(__file__).parents[2] / "fixtures" / "images" / "daily_dash_popup.png"
    data = screenshot.read_bytes()
    result = ScreenClassifier().classify(ScreenCapture(data, ScreenSize(1440, 3120)))
    assert result.screen is ScreenType.DAILY_DASH_POPUP
    assert result.confidence >= 0.99
    assert result.close_button is not None


def test_returns_unknown_without_matching_evidence() -> None:
    result = ScreenClassifier().classify(_capture())
    assert result.screen is ScreenType.UNKNOWN


def test_completion_home_is_detected_from_yellow_level_button() -> None:
    image = Image.new("RGB", (1000, 2000), (30, 35, 55))
    draw = ImageDraw.Draw(image)
    draw.rounded_rectangle((250, 1220, 750, 1380), radius=70, fill=(245, 190, 20))
    draw.text((420, 1280), "Level 92", fill=(255, 255, 255))
    output = io.BytesIO()
    image.save(output, format="PNG")
    capture = ScreenCapture(output.getvalue(), ScreenSize(1000, 2000))

    result = ScreenClassifier().classify(capture)

    assert result.screen is ScreenType.HOME_SCREEN
    assert result.start_button == PixelRect(250, 1220, 501, 161)
    assert result.start_button_confidence == 1.0


def test_completion_home_requires_a_large_button_shaped_yellow_region() -> None:
    image = Image.new("RGB", (1000, 2000), (30, 35, 55))
    ImageDraw.Draw(image).ellipse((450, 1250, 550, 1350), fill=(245, 190, 20))
    output = io.BytesIO()
    image.save(output, format="PNG")

    result = ScreenClassifier().classify(ScreenCapture(output.getvalue(), ScreenSize(1000, 2000)))

    assert result.screen is ScreenType.UNKNOWN
