"""Benchmark the checked-in screenshot through the production Vision primitives."""

import argparse
import logging
from datetime import UTC, datetime
from pathlib import Path

from PIL import Image

from word_madness_bot.domain.models import CapturedFrame, ScreenGeometry
from word_madness_bot.observability.metrics import MetricName, MetricsCollector
from word_madness_bot.vision.circle_detector import CircleDetector
from word_madness_bot.vision.preprocessing import decode_frame

_LOGGER = logging.getLogger(__name__)


def main() -> int:
    """Run a bounded benchmark and log aggregate latency."""

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--image", type=Path, default=Path("tests/fixtures/screens/playing_level_90.png"))
    parser.add_argument("--iterations", type=int, default=5)
    arguments = parser.parse_args()
    if arguments.iterations <= 0:
        parser.error("--iterations must be positive")
    with Image.open(arguments.image) as image:
        width, height = image.size
    frame = CapturedFrame(
        arguments.image.read_bytes(),
        ScreenGeometry(width, height, 600),
        datetime.now(UTC),
    )
    metrics = MetricsCollector()
    detector = CircleDetector()
    for _ in range(arguments.iterations):
        with metrics.time(MetricName.VISION_PIPELINE):
            detector.detect(decode_frame(frame), frame.geometry)
    timing = metrics.snapshot().timings[MetricName.VISION_PIPELINE.value]
    _LOGGER.info(
        "Vision benchmark complete",
        extra={
            "event": "vision_benchmark",
            "iterations": timing.count,
            "average_seconds": timing.average_seconds,
            "maximum_seconds": timing.maximum_seconds,
        },
    )
    return 0


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    raise SystemExit(main())
