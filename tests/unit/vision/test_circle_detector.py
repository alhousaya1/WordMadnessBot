"""Tests for resolution-scaled wheel circle detection."""

import numpy as np
from PIL import Image, ImageDraw

from word_madness_bot.domain.models import ScreenGeometry
from word_madness_bot.vision.circle_detector import CircleDetector


def _synthetic_wheel(width: int, height: int) -> np.ndarray:
    image = Image.new("RGB", (width, height), (15, 40, 100))
    radius = round(min(width, height) * 0.25)
    center = (width // 2, round(height * 0.76))
    ImageDraw.Draw(image).ellipse(
        (
            center[0] - radius,
            center[1] - radius,
            center[0] + radius,
            center[1] + radius,
        ),
        fill=(205, 205, 205),
    )
    return np.asarray(image, dtype=np.uint8)


def test_circle_detection_scales_across_resolutions() -> None:
    """Wheel center and radius remain proportional on different screen sizes."""

    detector = CircleDetector()
    for width, height in ((300, 600), (600, 1200)):
        geometry = ScreenGeometry(width, height, 320)
        result = detector.detect(_synthetic_wheel(width, height), geometry)

        assert result is not None
        assert abs(result.center.x / width - 0.5) < 0.02
        assert abs(result.center.y / height - 0.76) < 0.02
        assert abs(result.radius / min(width, height) - 0.25) < 0.03
        assert result.confidence > 0.8
