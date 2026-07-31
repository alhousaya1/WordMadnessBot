"""Integration tests against the repository's real screenshot fixture."""

from datetime import UTC, datetime
from pathlib import Path

from PIL import Image

from word_madness_bot.domain.models import CapturedFrame, ScreenGeometry
from word_madness_bot.vision.circle_detector import CircleDetector
from word_madness_bot.vision.geometry import NormalizedBox, to_pixel_box
from word_madness_bot.vision.preprocessing import crop, decode_frame, grayscale

_PROJECT_ROOT = Path(__file__).resolve().parents[3]
_SCREENSHOT = _PROJECT_ROOT / "tests" / "fixtures" / "screens" / "playing_level_90.png"


def _fixture_frame() -> CapturedFrame:
    with Image.open(_SCREENSHOT) as image:
        width, height = image.size
    return CapturedFrame(
        data=_SCREENSHOT.read_bytes(),
        geometry=ScreenGeometry(width, height, 600),
        captured_at=datetime.now(UTC),
    )


def test_real_fixture_decodes_and_crops_by_normalized_region() -> None:
    """The real reference frame follows the same resolution-independent image path."""

    frame = _fixture_frame()
    image = decode_frame(frame)
    header = crop(image, to_pixel_box(NormalizedBox(0.2, 0.02, 0.62, 0.12), frame.geometry))

    assert image.shape == (frame.geometry.height, frame.geometry.width, 3)
    assert grayscale(header).std() > 5.0


def test_real_fixture_detects_wheel_without_reference_pixel_coordinates() -> None:
    """The wheel detector finds plausible scaled geometry on the existing fixture."""

    frame = _fixture_frame()
    detection = CircleDetector().detect(decode_frame(frame), frame.geometry)

    assert detection is not None
    assert 0.35 < detection.center.x / frame.geometry.width < 0.65
    assert 0.65 < detection.center.y / frame.geometry.height < 0.90
    assert 0.20 < detection.radius / min(frame.geometry.width, frame.geometry.height) < 0.40
    assert detection.confidence > 0.65
