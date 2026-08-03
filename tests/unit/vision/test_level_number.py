from __future__ import annotations

import io
from pathlib import Path

import pytest
from PIL import Image, ImageDraw

from word_madness_bot.domain.errors import OcrError
from word_madness_bot.domain.geometry import ScreenSize
from word_madness_bot.domain.models import ScreenCapture
from word_madness_bot.vision.level_number import (
    HOME_LEVEL_TEXT_REFERENCE,
    LevelNumberRecognizer,
    parse_level_number,
    scale_reference_rect,
)


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


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("Level 90", 90),
        ("LEVEL 682", 682),
        ("682", 682),
        ("  Level  \n  682  ", 682),
        ("Level ninety", None),
        ("noise 682", None),
        ("Level 682 extra", None),
        ("0", None),
        ("", None),
    ],
)
def test_parse_level_number_is_strict(text: str, expected: int | None) -> None:
    assert parse_level_number(text) == expected


@pytest.mark.parametrize(
    ("size", "expected"),
    [
        (ScreenSize(1440, 3120), (360, 1940, 720, 170)),
        (ScreenSize(720, 1560), (180, 970, 360, 85)),
        (ScreenSize(1080, 2400), (270, 1492, 540, 131)),
    ],
)
def test_home_crop_scales_from_reference(
    size: ScreenSize, expected: tuple[int, int, int, int]
) -> None:
    rect = scale_reference_rect(HOME_LEVEL_TEXT_REFERENCE, size)
    assert (rect.left, rect.top, rect.width, rect.height) == expected


def test_recognized_number_must_be_in_supported_database(tmp_path: Path) -> None:
    fixture = Path(__file__).parents[2] / "fixtures" / "images" / "level_screen.png"
    capture = ScreenCapture(fixture.read_bytes(), ScreenSize(1440, 3120))
    recognizer = LevelNumberRecognizer(supported_levels=frozenset({1, 2}), debug_directory=tmp_path)
    with pytest.raises(OcrError, match="supported"):
        recognizer.recognize(capture)
    assert recognizer.last_candidates == ("90",)


def test_home_crop_tracks_shifted_yellow_start_button(tmp_path: Path) -> None:
    image = Image.new("RGB", (1440, 3120), (25, 30, 45))
    ImageDraw.Draw(image).rounded_rectangle((263, 2072, 1175, 2271), radius=80, fill=(245, 190, 20))
    output = io.BytesIO()
    image.save(output, format="PNG")
    recognizer = LevelNumberRecognizer(debug_directory=tmp_path)

    with pytest.raises(OcrError):
        recognizer.recognize(ScreenCapture(output.getvalue(), ScreenSize(1440, 3120)))

    assert recognizer.last_crop is not None
    assert (
        recognizer.last_crop.left,
        recognizer.last_crop.top,
        recognizer.last_crop.width,
        recognizer.last_crop.height,
    ) == (363, 2082, 721, 170)
