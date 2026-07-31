"""Tests for explicit structured logging."""

import importlib
import io
import json
from pathlib import Path

from word_madness_bot.config.logging import configure_logging


def test_import_has_no_filesystem_side_effect(tmp_path: Path, monkeypatch: object) -> None:
    monkeypatch.chdir(tmp_path)  # type: ignore[attr-defined]

    importlib.import_module("word_madness_bot.config.logging")

    assert list(tmp_path.iterdir()) == []


def test_log_event_is_structured_json() -> None:
    stream = io.StringIO()
    structured = configure_logging(name="word_madness_bot.test.json", stream=stream)

    structured.info("device.discovered", serial="abc", count=1)

    event = json.loads(stream.getvalue())
    assert event["level"] == "INFO"
    assert event["event"] == "device.discovered"
    assert event["context"] == {"count": 1, "serial": "abc"}
    assert event["timestamp"].endswith("+00:00")


def test_logging_configuration_is_idempotent() -> None:
    first_stream = io.StringIO()
    second_stream = io.StringIO()
    configure_logging(name="word_madness_bot.test.once", stream=first_stream)
    structured = configure_logging(name="word_madness_bot.test.once", stream=second_stream)

    structured.warning("single.event")

    assert first_stream.getvalue() == ""
    assert len(second_stream.getvalue().splitlines()) == 1


def test_file_logging_requires_explicit_path(tmp_path: Path) -> None:
    destination = tmp_path / "nested" / "events.jsonl"
    structured = configure_logging(
        name="word_madness_bot.test.file",
        stream=io.StringIO(),
        log_file=destination,
    )

    structured.error("explicit.file", attempt=2)

    event = json.loads(destination.read_text(encoding="utf-8"))
    assert event["event"] == "explicit.file"
    assert event["context"] == {"attempt": 2}
