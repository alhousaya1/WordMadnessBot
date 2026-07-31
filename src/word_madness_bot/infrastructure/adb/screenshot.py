"""PNG screenshot validation and atomic persistence."""

from __future__ import annotations

import os
import struct
import tempfile
from pathlib import Path

from word_madness_bot.domain.errors import ScreenshotError
from word_madness_bot.domain.geometry import ScreenSize

PNG_SIGNATURE = b"\x89PNG\r\n\x1a\n"


def parse_png_size(data: bytes) -> ScreenSize:
    """Validate a PNG header and return its IHDR dimensions."""
    if len(data) < 24 or not data.startswith(PNG_SIGNATURE):
        raise ScreenshotError("ADB returned an invalid PNG screenshot")
    if data[12:16] != b"IHDR":
        raise ScreenshotError("PNG screenshot has no IHDR header")
    width, height = struct.unpack(">II", data[16:24])
    try:
        return ScreenSize(width=width, height=height)
    except ValueError as error:
        raise ScreenshotError("PNG screenshot dimensions are invalid") from error


def save_screenshot(data: bytes, destination: Path) -> None:
    """Validate and atomically replace a screenshot file."""
    parse_png_size(data)
    destination.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary_name = tempfile.mkstemp(
        prefix=f".{destination.name}.", suffix=".tmp", dir=destination.parent
    )
    temporary = Path(temporary_name)
    try:
        with os.fdopen(descriptor, "wb") as stream:
            stream.write(data)
            stream.flush()
            os.fsync(stream.fileno())
        temporary.replace(destination)
    except BaseException:
        temporary.unlink(missing_ok=True)
        raise
