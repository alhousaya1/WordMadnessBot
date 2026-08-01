"""Unit tests for validated JSON level loading."""

from pathlib import Path

import pytest

from word_madness_bot.domain.errors import LevelDataError, LevelNotFoundError, LevelRepositoryError
from word_madness_bot.domain.models import Level
from word_madness_bot.infrastructure.levels.json_repository import JsonLevelRepository


def test_valid_load_lookup_order_normalization_and_duplicates() -> None:
    fixture = Path(__file__).parents[3] / "fixtures" / "levels" / "valid.json"
    repository = JsonLevelRepository.load(fixture)
    assert repository.get_level(2).words == ("CAFÉ", "TEA")
    assert repository.all_levels() == (Level(1, ("CAT", "ACT")), Level(2, ("CAFÉ", "TEA")))


def test_missing_file_is_typed(tmp_path: Path) -> None:
    with pytest.raises(LevelRepositoryError):
        JsonLevelRepository.load(tmp_path / "missing.json")


@pytest.mark.parametrize("text", ["{", "[]", '{"levels":{}}', '{"extra":1,"levels":[]}'])
def test_malformed_or_invalid_root_is_rejected(text: str) -> None:
    with pytest.raises(LevelDataError):
        JsonLevelRepository.from_json(text)


def test_invalid_schema_fixture_is_rejected() -> None:
    fixture = Path(__file__).parents[3] / "fixtures" / "levels" / "invalid.json"
    with pytest.raises(LevelDataError):
        JsonLevelRepository.load(fixture)


def test_duplicate_level_is_rejected() -> None:
    text = '{"levels":[{"number":1,"words":["A"]},{"number":1,"words":["B"]}]}'
    with pytest.raises(LevelDataError, match="Duplicate"):
        JsonLevelRepository.from_json(text)


def test_missing_level_is_typed() -> None:
    with pytest.raises(LevelNotFoundError):
        JsonLevelRepository.from_json('{"levels":[]}').get_level(99)


def test_packaged_repository_loads_every_scraped_level() -> None:
    levels = JsonLevelRepository.from_package().all_levels()
    assert len(levels) == 1010
    assert levels[0] == Level(1, ("IF", "FIT"))
    assert levels[89] == Level(
        90,
        ("DON", "DUN", "DUO", "FUN", "NOD", "FOND", "FUND", "FOUND"),
    )
    assert levels[-1] == Level(
        1010,
        ("CAN", "DIG", "DIN", "GIN", "INN", "NAG", "GAIN"),
    )
