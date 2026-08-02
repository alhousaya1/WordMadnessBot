from __future__ import annotations

import socket

import pytest

from word_madness_bot.domain.errors import RuntimeNavigationError
from word_madness_bot.runtime_lock import SingleInstanceGuard


def _available_port() -> int:
    probe = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    probe.bind(("127.0.0.1", 0))
    port = int(probe.getsockname()[1])
    probe.close()
    return port


def test_only_one_runtime_guard_can_own_device_control() -> None:
    port = _available_port()
    with SingleInstanceGuard(port=port):
        with pytest.raises(RuntimeNavigationError, match="already running"):
            with SingleInstanceGuard(port=port):
                pass


def test_runtime_guard_releases_ownership() -> None:
    port = _available_port()
    with SingleInstanceGuard(port=port):
        pass
    with SingleInstanceGuard(port=port):
        pass
