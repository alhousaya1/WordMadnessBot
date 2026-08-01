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


def test_production_adapter_selects_stock_android_monkey_script_backend(
    tmp_path: Path,
) -> None:
    calls: list[list[str]] = []
    log_stream = io.StringIO()

    def runner(command: list[str], **_: Any) -> subprocess.CompletedProcess[str]:
        calls.append(command)
        if "devices" in command:
            return _result("List of devices attached\nsamsung device\n")
        return _result()

    adapter = AdbClient(
        Settings(adb_retries=0, debug_directory=tmp_path),
        configure_logging(name="test.adb.swipe.backend", stream=log_stream),
        runner=runner,
    )
    adapter.select_device()
    adapter.swipe(
        SwipePath(
            (PixelPoint(100, 200), PixelPoint(300, 400), PixelPoint(500, 600)),
            180,
        )
    )

    monkey_command = calls[2]
    assert monkey_command[-5:] == [
        "shell",
        "monkey",
        "-f",
        "/data/local/tmp/word_madness_swipe.txt",
        "1",
    ]
    events = [json.loads(line) for line in log_stream.getvalue().splitlines()]
    selection = next(event for event in events if event["event"] == "adb.swipe.backend_selected")
    assert selection["context"] == {
        "backend": "monkey_script",
        "backend_command": monkey_command[-5:],
    }
    script = (tmp_path / "swipe_script.txt").read_text(encoding="utf-8")
    pointer_events = [line for line in script.splitlines() if line.startswith("DispatchPointer")]
    assert [event.split(",")[2] for event in pointer_events] == ["0", "2", "2", "1"]
    assert pointer_events[-2].split(",")[3:5] == ["500", "600"]
    assert pointer_events[-1].split(",")[3:5] == ["500", "600"]
