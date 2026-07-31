"""Contract tests for the concrete level repository."""

from word_madness_bot.application.ports.levels import LevelRepository
from word_madness_bot.infrastructure.levels.json_repository import JsonLevelRepository


def test_json_repository_satisfies_port() -> None:
    assert isinstance(JsonLevelRepository.from_json('{"levels":[]}'), LevelRepository)
