"""Opt-in real-device runtime screenshot integration test."""

import os
from pathlib import Path

import pytest

from word_madness_bot.bootstrap import build_runtime
from word_madness_bot.config.settings import Settings
from word_madness_bot.infrastructure.adb.screenshot import parse_png_size


@pytest.mark.hardware
@pytest.mark.skipif(os.environ.get("WMB_RUN_ADB_SMOKE") != "1", reason="hardware test is opt-in")
def test_runtime_captures_real_device_screenshot(tmp_path: Path) -> None:
    settings = Settings.from_environment(
        {**os.environ, "WMB_DEBUG_DIRECTORY": str(tmp_path)}
    )
    runtime = build_runtime(settings)
    runtime.start()
    runtime.shutdown()
    screenshot = tmp_path / "screenshot-1.png"
    assert parse_png_size(screenshot.read_bytes()).width > 0
