"""Opt-in real-device ADB smoke test."""

import os

import pytest

from word_madness_bot.config.logging import configure_logging
from word_madness_bot.config.settings import Settings
from word_madness_bot.infrastructure.adb.client import AdbClient


@pytest.mark.hardware
@pytest.mark.skipif(os.environ.get("WMB_RUN_ADB_SMOKE") != "1", reason="hardware test is opt-in")
def test_connected_device_smoke() -> None:
    client = AdbClient(Settings.from_environment(), configure_logging())
    client.select_device(os.environ.get("WMB_ADB_SERIAL"))
    assert client.verify_connection()
    assert client.get_display_metrics().size.width > 0
    assert client.capture_screenshot().data.startswith(b"\x89PNG")
