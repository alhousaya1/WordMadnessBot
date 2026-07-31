"""Contract for execution of already-decided Android input actions."""

from typing import Protocol

from word_madness_bot.domain.models import Point, SwipePath


class InputExecutor(Protocol):
    """Execute completed input commands without making gameplay decisions."""

    def tap(self, serial: str, point: Point) -> None:
        """Tap an absolute screen point on the selected device."""

        ...

    def swipe(self, serial: str, path: SwipePath) -> None:
        """Execute a completed swipe path on the selected device."""

        ...

    def key_event(self, serial: str, key_code: int) -> None:
        """Send an Android key event to the selected device."""

        ...
