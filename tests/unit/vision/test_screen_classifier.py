from __future__ import annotations

import io
from importlib.resources import files
from pathlib import Path

import pytest
from PIL import Image

from word_madness_bot.domain.geometry import ScreenSize
from word_madness_bot.domain.models import ScreenCapture
from word_madness_bot.vision.screen_classifier import ScreenClassifier, ScreenType


def _template(name: str) -> Image.Image:
    data = files("word_madness_bot.resources.templates").joinpath(name).read_bytes()
    return Image.open(io.BytesIO(data)).convert("L")


def _capture(*templates: tuple[str, int, int]) -> ScreenCapture:
    image = Image.new("L", (800, 500), 24)
    for name, left, top in templates:
        image.paste(_template(name), (left, top))
    output = io.BytesIO()
    image.save(output, format="PNG")
    return ScreenCapture(output.getvalue(), ScreenSize(800, 500))


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


def test_classifies_daily_dash_and_locates_close_button() -> None:
    result = ScreenClassifier().classify(
        _capture(("daily_dash_popup.png", 30, 70), ("daily_dash_close.png", 600, 280))
    )
    assert result.screen is ScreenType.DAILY_DASH_POPUP
    assert result.close_button is not None
    assert result.close_button.left + result.close_button.width // 2 == 690
    assert result.close_button.top + result.close_button.height // 2 == 375


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
