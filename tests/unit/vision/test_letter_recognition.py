from __future__ import annotations

import io
import json
import string
from pathlib import Path

import pytest
from PIL import Image, ImageDraw

from word_madness_bot.domain.errors import OcrError
from word_madness_bot.domain.geometry import PixelPoint, ScreenSize
from word_madness_bot.domain.models import ScreenCapture
from word_madness_bot.vision.letter_recognition import (
    OpenCvTemplateOcrEngine,
    WheelLetterRecognizer,
)
from word_madness_bot.vision.ocr import OcrResult
from word_madness_bot.vision.wheel_geometry import (
    LetterPosition,
    LetterWheelDetector,
    LetterWheelGeometry,
)


class SequenceEngine:
    def __init__(self, characters: str) -> None:
        self.characters = iter(characters)
        self.images: list[Image.Image] = []

    def recognize(self, image: Image.Image) -> OcrResult:
        self.images.append(image.copy())
        return OcrResult(next(self.characters), 0.9)


def _capture(image: Image.Image) -> ScreenCapture:
    output = io.BytesIO()
    image.save(output, format="PNG")
    return ScreenCapture(output.getvalue(), ScreenSize(*image.size))


def test_embedded_engine_recognizes_every_packaged_template() -> None:
    engine = OpenCvTemplateOcrEngine()
    resources = Path(__file__).parents[3] / "src" / "word_madness_bot" / "resources" / "glyphs"
    recognized = "".join(
        engine.recognize(Image.open(resources / f"{character}.png")).text
        for character in string.ascii_uppercase
    )
    assert recognized == string.ascii_uppercase


def test_crops_normalizes_and_saves_indexed_results(tmp_path: Path) -> None:
    image = Image.new("L", (400, 400), 235)
    draw = ImageDraw.Draw(image)
    points = (PixelPoint(200, 100), PixelPoint(300, 250), PixelPoint(100, 250))
    for point in points:
        draw.rectangle((point.x - 20, point.y - 35, point.x + 20, point.y + 35), fill=10)
    geometry = LetterWheelGeometry(
        PixelPoint(200, 200),
        160,
        tuple(LetterPosition(index, point) for index, point in enumerate(points)),
    )
    engine = SequenceEngine("ABC")
    recognizer = WheelLetterRecognizer(
        engine,
        clock=iter((1.0, 1.1, 2.0, 2.2, 3.0, 3.3)).__next__,
    )
    output = recognizer.recognize(
        _capture(image), geometry, tmp_path
    )
    assert [item.character for item in output.letters] == list("ABC")
    assert [item.elapsed_seconds for item in output.letters] == pytest.approx([0.1, 0.2, 0.3])
    assert all(item.size == (64, 64) and item.mode == "L" for item in engine.images)
    assert sorted(path.name for path in (tmp_path / "letters").glob("*.png")) == [
        "letter-0.png",
        "letter-1.png",
        "letter-2.png",
    ]
    payload = json.loads((tmp_path / "letters.json").read_text(encoding="utf-8"))
    assert payload["level"] is None
    assert [item["character"] for item in payload["letters"]] == list("ABC")


def test_real_level_fixture_recognizes_clockwise_letters(tmp_path: Path) -> None:
    fixture = Path(__file__).parents[2] / "fixtures" / "images" / "level_screen.png"
    capture = ScreenCapture(fixture.read_bytes(), ScreenSize(1440, 3120))
    geometry = LetterWheelDetector().detect(capture)
    output = WheelLetterRecognizer().recognize(capture, geometry, tmp_path)
    assert "".join(item.character for item in output.letters) == "OUNFD"
    assert all(item.confidence >= 0.9 for item in output.letters)
    assert len(tuple((tmp_path / "letters").glob("letter-*.png"))) == 5


def test_invalid_crop_content_raises_typed_ocr_error(tmp_path: Path) -> None:
    blank = _capture(Image.new("L", (200, 200), 255))
    geometry = LetterWheelGeometry(
        PixelPoint(100, 100),
        80,
        (LetterPosition(0, PixelPoint(100, 50)),),
    )
    with pytest.raises(OcrError, match="No glyph"):
        WheelLetterRecognizer().recognize(blank, geometry, tmp_path)
