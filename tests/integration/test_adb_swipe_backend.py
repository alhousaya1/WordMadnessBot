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


class Process:
    def poll(self) -> None:
        return None

    def terminate(self) -> None:
        return None

    def wait(self, timeout: float) -> int:
        return 0

    def kill(self) -> None:
        return None


class Stream:
    def __init__(self) -> None:
        self.commands: list[str] = []

    def write(self, data: bytes) -> int:
        self.commands.append(data.decode().strip())
        return len(data)

    def flush(self) -> None:
        return None

    def readline(self) -> bytes:
        return b"OK\n"

    def __enter__(self) -> Stream:
        return self

    def __exit__(self, *args: object) -> None:
        return None


class Connection:
    def __init__(self) -> None:
        self.stream = Stream()

    def makefile(self, mode: str) -> Stream:
        assert mode == "rwb"
        return self.stream

    def __enter__(self) -> Connection:
        return self

    def __exit__(self, *args: object) -> None:
        return None


def test_production_adapter_selects_live_monkey_network_backend(tmp_path: Path) -> None:
    calls: list[list[str]] = []
    log_stream = io.StringIO()
    connection = Connection()

    def runner(command: list[str], **_: Any) -> subprocess.CompletedProcess[str]:
        calls.append(command)
        if "devices" in command:
            return _result("List of devices attached\nsamsung device\n")
        if "forward" in command and "--remove" not in command:
            return _result("4242\n")
        return _result()

    adapter = AdbClient(
        Settings(adb_retries=0, debug_directory=tmp_path),
        configure_logging(name="test.adb.swipe.backend", stream=log_stream),
        runner=runner,
        sleeper=lambda _: None,
        launcher=lambda *args, **kwargs: Process(),  # type: ignore[arg-type]
        connector=lambda *args, **kwargs: connection,  # type: ignore[arg-type]
    )
    adapter.select_device()
    adapter.swipe(
        SwipePath(
            (PixelPoint(100, 200), PixelPoint(300, 400), PixelPoint(500, 600)),
            180,
        )
    )

    assert connection.stream.commands == [
        "touch down 100 200",
        "touch move 300 400",
        "touch move 500 600",
        "touch up 500 600",
        "quit",
    ]
    events = [json.loads(line) for line in log_stream.getvalue().splitlines()]
    selection = next(event for event in events if event["event"] == "adb.swipe.backend_selected")
    assert selection["context"]["backend"] == "monkey_network_touch"
    assert selection["context"]["host_port"] == 4242
    assert selection["context"]["device_port"] == 1080
    assert selection["context"]["backend_command"][-4:] == [
        "shell",
        "monkey",
        "--port",
        "1080",
    ]