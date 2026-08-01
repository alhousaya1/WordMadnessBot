import io
import subprocess
from pathlib import Path

import pytest
from PIL import Image, ImageDraw

from word_madness_bot.application.runtime_controls import (
    UpperRightPopupCloseDetector,
    YellowLevelButtonDetector,
)
from word_madness_bot.domain.errors import OcrError, RuntimeNavigationError
from word_madness_bot.domain.geometry import PixelRect, ScreenSize
from word_madness_bot.domain.models import ScreenCapture

FIXTURES = Path(__file__).parents[2] / "fixtures" / "images"


def _capture(name: str) -> ScreenCapture:
    path = FIXTURES / name
    with Image.open(path) as image:
        size = ScreenSize(*image.size)
    return ScreenCapture(path.read_bytes(), size)


def _image_capture(image: Image.Image) -> ScreenCapture:
    output = io.BytesIO()
    image.save(output, format="PNG")
    return ScreenCapture(output.getvalue(), ScreenSize(*image.size))


def test_detects_yellow_rectangle_and_reads_only_its_level_text(
    tmp_path: Path,
) -> None:
    result = YellowLevelButtonDetector(tmp_path).detect(_capture("home_screen.png"))

    assert result.level == 90
    assert (
        result.region.left + result.region.width // 2,
        result.region.top + result.region.height // 2,
    ) == (721, 2043)
    assert result.ocr_crop_size == (804, 188)
    assert sorted(path.name for path in tmp_path.iterdir()) == [
        "button_box.png",
        "button_crop.png",
        "home_screen.png",
        "yellow_mask.png",
    ]


def test_locates_alternate_yellow_button_independently_of_text() -> None:
    image = Image.new("RGB", (1080, 2400), (80, 70, 130))
    draw = ImageDraw.Draw(image)
    draw.rounded_rectangle(
        (180, 1500, 900, 1700),
        radius=8,
        fill=(235, 180, 45),
    )
    draw.rectangle((390, 1570, 690, 1630), fill=(35, 30, 25))

    region = YellowLevelButtonDetector().locate(_image_capture(image))

    assert region == PixelRect(181, 1501, 721, 201)
    assert (
        region.left + region.width // 2,
        region.top + region.height // 2,
    ) == (541, 1601)


def test_tightens_oversized_contour_only_for_ocr() -> None:
    detector = YellowLevelButtonDetector()
    region = PixelRect(100, 200, 1008, 629)

    assert detector.ocr_crop_size(region) == (908, 251)

def test_uses_largest_yellow_contour_only_in_lower_middle() -> None:
    image = Image.new("RGB", (1000, 2000), (80, 70, 130))
    draw = ImageDraw.Draw(image)
    draw.rounded_rectangle((50, 100, 950, 500), radius=30, fill=(235, 180, 45))
    draw.rounded_rectangle((250, 1200, 750, 1350), radius=20, fill=(235, 180, 45))
    draw.rounded_rectangle((400, 1500, 600, 1575), radius=15, fill=(235, 180, 45))

    region = YellowLevelButtonDetector().locate(_image_capture(image))

    assert region == PixelRect(251, 1201, 501, 151)


def test_ocr_failure_does_not_trigger_screenshot_polling(tmp_path: Path) -> None:
    capture = _capture("home_screen.png")

    class FailingDetector(YellowLevelButtonDetector):
        attempts = 0

        def _read_level(self, image: object, region: PixelRect) -> int:
            self.attempts += 1
            raise OcrError("OCR failed")

    detector = FailingDetector(tmp_path)

    with pytest.raises(OcrError, match="OCR failed"):
        detector.detect(capture)

    assert detector.attempts == 1

def test_tesseract_retries_invalid_result_with_digit_only_configuration(
    tmp_path: Path,
) -> None:
    outputs = [b"0\n", b"91\n"]
    calls: list[tuple[list[str], dict[str, object]]] = []

    def runner(
        command: list[str], **kwargs: object
    ) -> subprocess.CompletedProcess[bytes]:
        calls.append((command, kwargs))
        return subprocess.CompletedProcess(command, 0, outputs.pop(0), b"")

    detector = YellowLevelButtonDetector(
        tmp_path,
        tesseract_runner=runner,
        tesseract_executable="tesseract-test",
    )

    result = detector.detect(_capture("home_screen.png"))

    assert result.level == 91
    assert len(calls) == 2
    command, kwargs = calls[0]
    assert command == [
        "tesseract-test",
        "stdin",
        "stdout",
        "--psm",
        "7",
        "-c",
        "tessedit_char_whitelist=0123456789",
    ]
    processed = Image.open(io.BytesIO(kwargs["input"]))  # type: ignore[arg-type]
    assert processed.size == (
        result.ocr_crop_size[0] * 4,
        result.ocr_crop_size[1] * 4,
    )
    populated_values = {
        value for value, count in enumerate(processed.histogram()) if count
    }
    assert populated_values <= {0, 255}

def test_saves_all_candidates_when_yellow_button_detection_fails(
    tmp_path: Path,
) -> None:
    image = Image.new("RGB", (1000, 2000), (80, 70, 130))
    draw = ImageDraw.Draw(image)
    draw.rounded_rectangle((400, 1200, 440, 1220), radius=10, fill=(235, 180, 45))
    detector = YellowLevelButtonDetector(tmp_path)

    with pytest.raises(RuntimeNavigationError, match="Yellow level button was not detected"):
        detector.detect(_image_capture(image))

    assert sorted(path.name for path in tmp_path.iterdir()) == [
        "button_candidates.png",
        "home_screen.png",
        "yellow_mask.png",
    ]


def test_finds_close_button_in_upper_right_region() -> None:
    result = UpperRightPopupCloseDetector().detect(_capture("daily_dash_popup.png"))

    assert result == PixelRect(1200, 750, 180, 190)


def test_does_not_find_close_button_on_home_screen() -> None:
    assert UpperRightPopupCloseDetector().detect(_capture("home_screen.png")) is None
