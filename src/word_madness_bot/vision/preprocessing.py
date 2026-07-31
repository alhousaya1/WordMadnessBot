"""Deterministic image decoding and preprocessing."""

from __future__ import annotations

from io import BytesIO
from pathlib import Path

from PIL import Image, ImageFilter, UnidentifiedImageError

from word_madness_bot.domain.errors import ImageDecodeError


def load_image(source: bytes | Path) -> Image.Image:
    """Decode image bytes or a path into a detached RGB image."""
    try:
        with Image.open(BytesIO(source) if isinstance(source, bytes) else source) as image:
            image.load()
            return image.convert("RGB")
    except (FileNotFoundError, OSError, UnidentifiedImageError) as error:
        raise ImageDecodeError("Unable to decode image") from error


def preprocess(image: Image.Image, *, threshold: int = 128, blur_radius: int = 0) -> Image.Image:
    """Return a deterministic binary image suitable for feature extraction."""
    if not 0 <= threshold <= 255 or blur_radius < 0:
        raise ValueError("Invalid preprocessing parameters")
    gray = image.convert("L")
    if blur_radius:
        gray = gray.filter(ImageFilter.GaussianBlur(blur_radius))
    return gray.point(lambda value: 255 if value >= threshold else 0, mode="1")
