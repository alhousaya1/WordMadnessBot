"""Tests for deterministic image decoding and preprocessing."""

from datetime import UTC, datetime
from io import BytesIO

import numpy as np
import pytest
from PIL import Image

from word_madness_bot.domain.errors import VisionError
from word_madness_bot.domain.models import CapturedFrame, ScreenGeometry
from word_madness_bot.vision.preprocessing import decode_frame, grayscale, resize, threshold


def _png_bytes(image: Image.Image) -> bytes:
    output = BytesIO()
    image.save(output, format="PNG")
    return output.getvalue()


def test_decode_frame_returns_rgb_with_declared_geometry() -> None:
    """Valid encoded screenshots become canonical RGB arrays."""

    frame = CapturedFrame(
        data=_png_bytes(Image.new("RGBA", (4, 3), (10, 20, 30, 255))),
        geometry=ScreenGeometry(4, 3, 320),
        captured_at=datetime.now(UTC),
    )

    decoded = decode_frame(frame)

    assert decoded.shape == (3, 4, 3)
    assert decoded.dtype == np.uint8


def test_decode_frame_rejects_geometry_mismatch() -> None:
    """Incorrect capture metadata cannot silently distort normalized coordinates."""

    frame = CapturedFrame(
        data=_png_bytes(Image.new("RGB", (4, 3))),
        geometry=ScreenGeometry(5, 3, 320),
        captured_at=datetime.now(UTC),
    )

    with pytest.raises(VisionError, match="dimensions"):
        decode_frame(frame)


def test_grayscale_threshold_and_resize_are_deterministic() -> None:
    """Core preprocessing produces stable shapes and binary values."""

    image = np.array([[[0, 0, 0], [255, 255, 255]]], dtype=np.uint8)
    gray = grayscale(image)
    binary = threshold(gray, 128)

    assert binary.tolist() == [[0, 255]]
    assert resize(binary, 4, 2).shape == (2, 4)
