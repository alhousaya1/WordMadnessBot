"""Integration coverage for production ADB swipe backend selection."""

from __future__ import annotations

import io
import json
import subprocess
from pathlib import Path
from typing import Any, cast

from word_madness_bot.config.logging import configure_logging
from word_madness_bot.config.settings import Settings
from word_madness_bot.domain.geometry import PixelPoint
from word_madness_bot.domain.models import SwipePath
from word_madness_bot.infrastructure.adb.client import AdbClient


def _result(stdout: str = "") -> subprocess.CompletedProcess[str]:
    return cast(
        subprocess.CompletedProcess[str],
        subprocess.CompletedProcess([], 0, stdout, ""),
    )


class Device:
    def __init__(self) -> None:
        self.points: list[tuple[int, int]] = []
        self.duration = 0.0

    def swipe_points(self, points: list[tuple[int, int]], duration: float = 0.5) -> bool:
        self.points = points
        self.duration = duration
        return True


def test_production_adapter_selects_uiautomator2_swipe_points_backend(
    tmp_path: Path,
) -> None:
    log_stream = io.StringIO()
    device = Device()

    def runner(command: list[str], **_: Any) -> subprocess.CompletedProcess[str]:
        if "devices" in command:
            return _result("List of devices attached\nsamsung device\n")
        return _result()

    adapter = AdbClient(
        Settings(adb_retries=0, debug_directory=tmp_path),
        configure_logging(name="test.adb.swipe.backend", stream=log_stream),
        runner=runner,
        u2_connector=lambda serial: device,
    )
    adapter.select_device()
    adapter.swipe(
        SwipePath(
            (PixelPoint(100, 200), PixelPoint(300, 400), PixelPoint(500, 600)),
            180,
        )
    )

    assert device.points == [(100, 200), (300, 400), (500, 600)]
    assert device.duration == 0.09
    events = [json.loads(line) for line in log_stream.getvalue().splitlines()]
    selection = next(event for event in events if event["event"] == "adb.swipe.backend_selected")
    assert selection["context"] == {
        "backend": "uiautomator2_swipe_points",
        "backend_command": ["uiautomator2", "swipe_points", "samsung"],
        "requested_duration_seconds": 0.18,
        "segment_duration_seconds": 0.09,
        "point_count": 3,
    }
