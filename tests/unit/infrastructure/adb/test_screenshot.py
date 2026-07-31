"""Tests for screenshot validation and persistence."""

from __future__ import annotations

import struct
from pathlib import Path

import pytest

from word_madness_bot.domain.errors import ScreenshotError
from word_madness_bot.infrastructure.adb.screenshot import parse_png_size, save_screenshot


def png(width: int = 10, height: int = 20) -> bytes:
    return b"\x89PNG\r\n\x1a\n" + b"\x00\x00\x00\rIHDR" + struct.pack(">II", width, height)


def test_png_dimensions_are_parsed() -> None:
    assert (parse_png_size(png()).width, parse_png_size(png()).height) == (10, 20)


@pytest.mark.parametrize("data", [b"", b"not png", b"\x89PNG\r\n\x1a\n" + b"x" * 16])
def test_invalid_png_is_rejected(data: bytes) -> None:
    with pytest.raises(ScreenshotError):
        parse_png_size(data)


def test_screenshot_save_atomically_replaces_destination(tmp_path: Path) -> None:
    destination = tmp_path / "nested" / "screen.png"
    destination.parent.mkdir()
    destination.write_bytes(b"old")
    save_screenshot(png(), destination)
    assert destination.read_bytes() == png()
    assert list(destination.parent.glob("*.tmp")) == []


def test_invalid_screenshot_does_not_replace_destination(tmp_path: Path) -> None:
    destination = tmp_path / "screen.png"
    destination.write_bytes(b"old")
    with pytest.raises(ScreenshotError):
        save_screenshot(b"bad", destination)
    assert destination.read_bytes() == b"old"
