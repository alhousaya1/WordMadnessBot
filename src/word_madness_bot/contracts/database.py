"""Contract for data-driven level lookup."""

from typing import Protocol

from word_madness_bot.domain.models import LevelDefinition


class LevelRepository(Protocol):
    """Retrieve level definitions independently of their storage format."""

    def get_level(self, level_number: int) -> LevelDefinition | None:
        """Return a level definition, or ``None`` when it is not stored."""

        ...

    def contains(self, level_number: int) -> bool:
        """Return whether a level definition exists."""

        ...

    def find_levels_by_word(self, word: str) -> tuple[LevelDefinition, ...]:
        """Return levels containing a word in ascending level-number order."""

        ...

    def all_levels(self) -> tuple[LevelDefinition, ...]:
        """Return every level in ascending level-number order."""

        ...
