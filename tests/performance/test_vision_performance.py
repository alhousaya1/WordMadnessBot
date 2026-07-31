"""Performance guard for the existing real screenshot Vision fixture."""

from datetime import UTC, datetime
from pathlib import Path
from time import perf_counter

from PIL import Image

from word_madness_bot.domain.models import CapturedFrame, ScreenGeometry
from word_madness_bot.vision.circle_detector import CircleDetector
from word_madness_bot.vision.preprocessing import decode_frame


def test_real_fixture_circle_pipeline_completes_within_practical_budget() -> None:
    image_path = (
        Path(__file__).resolve().parents[2]
        / "tests"
        / "fixtures"
        / "screens"
        / "playing_level_90.png"
    )
    with Image.open(image_path) as image:
        width, height = image.size
    frame = CapturedFrame(
        image_path.read_bytes(), ScreenGeometry(width, height, 600), datetime.now(UTC)
    )
    started = perf_counter()
    result = CircleDetector().detect(decode_frame(frame), frame.geometry)
    elapsed = perf_counter() - started
    assert result is not None
    assert elapsed < 5.0
