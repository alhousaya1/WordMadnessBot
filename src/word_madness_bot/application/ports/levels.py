"""Contract for data-driven level lookup."""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from word_madness_bot.domain.models import Level


@runtime_checkable
class LevelRepository(Protocol):
    """Replaceable source of validated level data."""

    def get_level(self, number: int) -> Level | None:
        """Return a level when known, otherwise ``None``."""
        ...
