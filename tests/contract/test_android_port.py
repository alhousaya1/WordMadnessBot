"""Contract checks for the concrete Android adapter."""

import io

from word_madness_bot.application.ports.android import AndroidPort
from word_madness_bot.config.logging import configure_logging
from word_madness_bot.config.settings import Settings
from word_madness_bot.infrastructure.adb.client import AdbClient


def test_adb_client_satisfies_android_port_at_runtime() -> None:
    adapter = AdbClient(Settings(), configure_logging(stream=io.StringIO()))
    assert isinstance(adapter, AndroidPort)
