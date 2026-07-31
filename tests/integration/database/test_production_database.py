"""Integration tests for the checked-in production level database."""

from pathlib import Path

from word_madness_bot.adapters.database import JsonLevelRepository
from word_madness_bot.config import Settings


def test_production_database_is_strictly_valid() -> None:
    """The complete production document loads and indexes deterministically."""

    settings = Settings(project_root=Path(__file__).resolve().parents[3])
    repository = JsonLevelRepository(settings.level_database_file)

    levels = repository.all_levels()
    assert levels
    level_numbers = tuple(level.number for level in levels)
    assert level_numbers == tuple(sorted(level_numbers))
    assert len({level.number for level in levels}) == len(levels)
    for level in levels:
        assert repository.get_level(level.number) == level
        for word in level.words:
            assert level in repository.find_levels_by_word(word)
