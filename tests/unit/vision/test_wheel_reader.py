"""Tests for letter extraction, wheel composition, and configured debug rendering."""

from pathlib import Path

import numpy as np
import pytest
from PIL import Image, ImageDraw

from word_madness_bot.config import Settings
from word_madness_bot.domain.models import (
    CircleDetection,
    DetectedLetter,
    OcrResult,
    Point,
    ScreenGeometry,
)
from word_madness_bot.vision.debug_renderer import DebugRenderer
from word_madness_bot.vision.letter_extractor import LetterExtractor
from word_madness_bot.vision.preprocessing import ImageArray
from word_madness_bot.vision.wheel_reader import WheelReader


class SequenceOcr:
    """OCR double that assigns one letter to each candidate component."""

    def __init__(self, letters: list[str]) -> None:
        self._letters = iter(letters)

    def recognize(self, image: ImageArray, *, whitelist: str | None = None) -> OcrResult | None:
        """Return the next configured character."""

        return OcrResult(next(self._letters), 0.9)


class StubCircleDetector:
    """Circle detector double for wheel composition."""

    def __init__(self, result: CircleDetection | None) -> None:
        self._result = result

    def detect(self, image: ImageArray, geometry: ScreenGeometry) -> CircleDetection | None:
        """Return the configured detection."""

        return self._result


class StubLetterExtractor:
    """Letter extractor double for wheel composition."""

    def __init__(self, letters: tuple[DetectedLetter, ...]) -> None:
        self._letters = letters

    def extract(
        self,
        image: ImageArray,
        circle: CircleDetection,
    ) -> tuple[DetectedLetter, ...]:
        """Return the configured letters."""

        return self._letters


def test_letter_extractor_returns_clockwise_confident_letters() -> None:
    """Glyph candidates receive OCR confidence and stable circular ordering."""

    canvas = Image.new("RGB", (300, 300), (210, 210, 210))
    draw = ImageDraw.Draw(canvas)
    draw.rectangle((135, 50, 165, 100), fill="black")
    draw.rectangle((200, 135, 230, 185), fill="black")
    draw.rectangle((70, 135, 100, 185), fill="black")
    image = np.asarray(canvas, dtype=np.uint8)
    circle = CircleDetection(Point(150, 150), 140, 0.95)

    letters = LetterExtractor(SequenceOcr(["A", "B", "C"])).extract(image, circle)

    assert len(letters) == 3
    assert letters[0].center.y < 110
    assert all(letter.confidence > 0.8 for letter in letters)


def test_wheel_reader_combines_confidence_without_later_layer_dependencies() -> None:
    """Complete wheel confidence is bounded by geometric and OCR evidence."""

    circle = CircleDetection(Point(50, 50), 40, 0.8)
    letters = (
        DetectedLetter("A", Point(50, 15), 0.9),
        DetectedLetter("C", Point(80, 65), 0.7),
        DetectedLetter("T", Point(20, 65), 0.8),
    )
    reader = WheelReader(StubCircleDetector(circle), StubLetterExtractor(letters))

    wheel = reader.read(np.zeros((100, 100, 3), dtype=np.uint8), ScreenGeometry(100, 100, 320))

    assert wheel is not None
    assert wheel.letters == letters
    assert wheel.confidence == pytest.approx(0.8)


def test_debug_renderer_obeys_configuration(tmp_path: Path) -> None:
    """Debug images are impossible when disabled and emitted when enabled."""

    image = np.zeros((20, 20, 3), dtype=np.uint8)
    disabled = DebugRenderer(Settings(project_root=tmp_path, save_debug_images=False))

    assert disabled.render(image, "disabled.png") is None
    assert not (tmp_path / "debug").exists()

    enabled = DebugRenderer(Settings(project_root=tmp_path, save_debug_images=True))
    output = enabled.render(image, "enabled.png")

    assert output == tmp_path / "debug" / "enabled.png"
    assert output.is_file()
