"""Opt-in real-device release smoke test."""

import os

import pytest

from word_madness_bot.bootstrap import build_application


@pytest.mark.skipif(
    os.environ.get("WORD_MADNESS_RUN_DEVICE_E2E") != "1",
    reason="set WORD_MADNESS_RUN_DEVICE_E2E=1 with one authorized device",
)
def test_real_device_connectivity_and_capture() -> None:
    app = build_application()
    serial = app.check_device()
    assert serial
    observation = app.observe_once()
    assert observation.revision == 1
