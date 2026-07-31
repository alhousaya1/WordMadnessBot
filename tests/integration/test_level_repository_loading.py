"""Integration coverage for file-backed repository loading."""

from pathlib import Path

from word_madness_bot.infrastructure.levels.json_repository import JsonLevelRepository


def test_fixture_repository_loads_end_to_end() -> None:
    path = Path(__file__).parents[1] / "fixtures" / "levels" / "valid.json"
    repository = JsonLevelRepository.load(path)
    assert repository.get_level(1).words == ("CAT", "ACT")
