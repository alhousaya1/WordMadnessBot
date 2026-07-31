from __future__ import annotations

import io
import json
from pathlib import Path

import pytest
from PIL import Image, ImageDraw

from word_madness_bot.domain.errors import WheelGeometryDetectionError
from word_madness_bot.domain.geometry import ScreenSize
from word_madness_bot.domain.models import ScreenCapture
from word_madness_bot.vision.wheel_geometry import (
    LetterWheelDetector,
    save_wheel_debug_artifacts,
)


def _capture(image: Image.Image) -> ScreenCapture:
    output = io.BytesIO()
    image.save(output, format="PNG")
    return ScreenCapture(output.getvalue(), ScreenSize(*image.size))


def _synthetic_wheel() -> ScreenCapture:
    image = Image.new("RGB", (800, 1200), (40, 40, 40))
    draw = ImageDraw.Draw(image)
    center = (400, 850)
    radius = 250
    draw.ellipse(
        (center[0] - radius, center[1] - radius, center[0] + radius, center[1] + radius),
        fill=(235, 235, 235),
    )
    for x, y in ((400, 690), (550, 800), (495, 990), (305, 990), (250, 800)):
        draw.rectangle((x - 22, y - 35, x + 22, y + 35), fill=(15, 15, 15))
    return _capture(image)


def test_detects_wheel_and_indexes_positions_clockwise_from_top() -> None:
    geometry = LetterWheelDetector().detect(_synthetic_wheel())
    assert abs(geometry.center.x - 400) <= 2
    assert abs(geometry.center.y - 850) <= 4
    assert abs(geometry.radius - 250) <= 4
    assert len(geometry.letters) == 5
    assert [position.index for position in geometry.letters] == list(range(5))
    points = [position.point for position in geometry.letters]
    assert points[0].y < geometry.center.y
    assert points[1].x > geometry.center.x
    assert points[2].x > geometry.center.x
    assert points[3].x < geometry.center.x
    assert points[4].x < geometry.center.x


def test_real_level_fixture_detects_five_letter_positions() -> None:
    fixture = Path(__file__).parents[2] / "fixtures" / "images" / "level_screen.png"
    geometry = LetterWheelDetector().detect(
        ScreenCapture(fixture.read_bytes(), ScreenSize(1440, 3120))
    )
    assert abs(geometry.center.x - 720) <= 3
    assert abs(geometry.center.y - 2326) <= 3
    assert 450 <= geometry.radius <= 460
    assert len(geometry.letters) == 5


def test_annotation_and_json_artifacts_contain_detected_geometry(tmp_path: Path) -> None:
    detector = LetterWheelDetector()
    capture = _synthetic_wheel()
    geometry = detector.detect(capture)
    annotated_path, json_path = save_wheel_debug_artifacts(
        tmp_path, capture, geometry, detector
    )
    with Image.open(annotated_path) as annotated:
        assert annotated.size == (800, 1200)
        assert annotated.format == "PNG"
    payload = json.loads(json_path.read_text(encoding="utf-8"))
    assert payload["wheel_center"] == {
        "x": geometry.center.x,
        "y": geometry.center.y,
    }
    assert payload["radius"] == geometry.radius
    assert payload["number_of_letters"] == 5
    assert [item["index"] for item in payload["letter_coordinates"]] == list(range(5))


def test_detection_fails_without_a_circular_wheel() -> None:
    blank = _capture(Image.new("RGB", (800, 1200), (40, 40, 40)))
    with pytest.raises(WheelGeometryDetectionError, match="not detected"):
        LetterWheelDetector().detect(blank)
