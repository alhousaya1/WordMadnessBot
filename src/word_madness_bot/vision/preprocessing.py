"""Image decoding and reusable preprocessing operations."""

from io import BytesIO
from typing import cast

import numpy as np
from numpy.typing import NDArray
from PIL import Image, ImageFilter, ImageOps

from word_madness_bot.domain.errors import VisionError
from word_madness_bot.domain.models import BoundingBox, CapturedFrame

ImageArray = NDArray[np.uint8]


def decode_frame(frame: CapturedFrame) -> ImageArray:
    """Decode a captured frame into an RGB uint8 array and verify its geometry."""

    try:
        with Image.open(BytesIO(frame.data)) as image:
            image.load()
            rgb = image.convert("RGB")
    except (OSError, ValueError) as error:
        raise VisionError("captured frame is not a decodable image") from error
    if rgb.size != (frame.geometry.width, frame.geometry.height):
        raise VisionError("captured frame dimensions do not match its geometry")
    return np.asarray(rgb, dtype=np.uint8)


def crop(image: ImageArray, region: BoundingBox) -> ImageArray:
    """Return a copy of a validated absolute image region."""

    height, width = image.shape[:2]
    if region.right > width or region.bottom > height:
        raise VisionError("crop region lies outside image bounds")
    return image[region.top : region.bottom, region.left : region.right].copy()


def grayscale(image: ImageArray) -> ImageArray:
    """Convert RGB image data to perceptual grayscale."""

    if image.ndim == 2:
        return image.copy()
    if image.ndim != 3 or image.shape[2] != 3:
        raise VisionError("expected an RGB or grayscale image array")
    channels = image.astype(np.float32)
    gray = channels[..., 0] * 0.299 + channels[..., 1] * 0.587 + channels[..., 2] * 0.114
    return cast(ImageArray, np.clip(np.rint(gray), 0, 255).astype(np.uint8))


def autocontrast(image: ImageArray) -> ImageArray:
    """Stretch grayscale intensity while preserving uint8 output."""

    gray = grayscale(image)
    return np.asarray(ImageOps.autocontrast(Image.fromarray(gray)), dtype=np.uint8)


def gaussian_blur(image: ImageArray, radius: float) -> ImageArray:
    """Apply a resolution-scaled Gaussian blur."""

    if radius < 0:
        raise ValueError("blur radius cannot be negative")
    gray = grayscale(image)
    return np.asarray(
        Image.fromarray(gray).filter(ImageFilter.GaussianBlur(radius)), dtype=np.uint8
    )


def threshold(image: ImageArray, cutoff: int, *, invert: bool = False) -> ImageArray:
    """Produce a binary image using an explicit grayscale cutoff."""

    if not 0 <= cutoff <= 255:
        raise ValueError("threshold cutoff must be between 0 and 255")
    gray = grayscale(image)
    mask = gray <= cutoff if invert else gray >= cutoff
    return np.where(mask, 255, 0).astype(np.uint8)


def resize(image: ImageArray, width: int, height: int) -> ImageArray:
    """Resize an image with high-quality resampling."""

    if width <= 0 or height <= 0:
        raise ValueError("resize dimensions must be positive")
    mode = "L" if image.ndim == 2 else "RGB"
    resized = Image.fromarray(image, mode=mode).resize((width, height), Image.Resampling.LANCZOS)
    return np.asarray(resized, dtype=np.uint8)
