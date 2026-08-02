"""Process-local device-control ownership guard."""

from __future__ import annotations

import socket

from word_madness_bot.domain.errors import RuntimeNavigationError

LOCK_HOST = "127.0.0.1"
LOCK_PORT = 47653


class SingleInstanceGuard:
    """Hold an exclusive localhost socket while one bot runtime owns the device."""

    def __init__(self, *, port: int = LOCK_PORT) -> None:
        self.port = port
        self._socket: socket.socket | None = None

    def __enter__(self) -> SingleInstanceGuard:
        guard = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        try:
            if hasattr(socket, "SO_EXCLUSIVEADDRUSE"):
                guard.setsockopt(socket.SOL_SOCKET, socket.SO_EXCLUSIVEADDRUSE, 1)
            guard.bind((LOCK_HOST, self.port))
            guard.listen(1)
        except OSError as error:
            guard.close()
            raise RuntimeNavigationError(
                "Another Word Madness Bot process is already running"
            ) from error
        self._socket = guard
        return self

    def __exit__(self, exc_type: object, exc_value: object, traceback: object) -> None:
        if self._socket is not None:
            self._socket.close()
            self._socket = None
