"""Contract for pure word-to-path conversion."""

from collections.abc import Sequence
from typing import Protocol

from word_madness_bot.domain.models import SwipeLetter, SwipePath


class SwipeGenerator(Protocol):
    """Plan completed swipe paths without communicating with Android."""

    def generate(self, word: str, letters: Sequence[SwipeLetter]) -> SwipePath:
        """Convert a target word and normalized letter coordinates into a path."""

        ...
