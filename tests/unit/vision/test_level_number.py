from __future__ import annotations

import io
from pathlib import Path

import pytest
from PIL import Image

from word_madness_bot.domain.errors import OcrError
from word_madness_bot.domain.geometry import ScreenSize
from word_madness_bot.domain.models import ScreenCapture
from word_madness_bot.vision.level_number import LevelNumberRecognizer


def test_real_level_fixture_recognizes_level_90() -> None:
    fixture = Path(__file__).parents[2] / "fixtures" / "images" / "level_screen.png"
    capture = ScreenCapture(fixture.read_bytes(), ScreenSize(1440, 3120))
    assert LevelNumberRecognizer().recognize(capture) == 90


def test_blank_title_raises_typed_ocr_error() -> None:
    image = Image.new("L", (1000, 2000), 0)
    output = io.BytesIO()
    image.save(output, format="PNG")
    capture = ScreenCapture(output.getvalue(), ScreenSize(1000, 2000))
    with pytest.raises(OcrError, match="No level-number"):
        LevelNumberRecognizer().recognize(capture)


def test_confidence_is_validated() -> None:
    with pytest.raises(ValueError, match="minimum_confidence"):
        LevelNumberRecognizer(minimum_confidence=1.1)
