"""Validated JSON-backed implementation of the level repository port."""

from __future__ import annotations

import json
import unicodedata
from importlib.resources import files
from pathlib import Path
from typing import Any

from word_madness_bot.application.ports.levels import LevelRepository
from word_madness_bot.domain.errors import LevelDataError, LevelNotFoundError, LevelRepositoryError
from word_madness_bot.domain.models import Level


class JsonLevelRepository(LevelRepository):
    """Immutable in-memory index loaded from validated JSON data."""

    def __init__(self, levels: tuple[Level, ...]) -> None:
        index: dict[int, Level] = {}
        for level in levels:
            if level.number in index:
                raise LevelDataError(f"Duplicate level number: {level.number}")
            index[level.number] = level
        self._levels = index

    @classmethod
    def load(cls, path: Path) -> JsonLevelRepository:
        """Load and validate a repository from a filesystem path."""
        try:
            text = path.read_text(encoding="utf-8")
        except OSError as error:
            raise LevelRepositoryError(f"Unable to read level repository: {path}") from error
        return cls.from_json(text)

    @classmethod
    def from_json(cls, text: str) -> JsonLevelRepository:
        """Load and validate a repository from JSON text."""
        try:
            payload = json.loads(text)
        except json.JSONDecodeError as error:
            raise LevelDataError("Level repository contains malformed JSON") from error
        return cls(_parse_payload(payload))

    @classmethod
    def from_package(cls) -> JsonLevelRepository:
        """Load the repository bundled with the installed package."""
        resource = files("word_madness_bot.resources.levels").joinpath("levels.json")
        try:
            return cls.from_json(resource.read_text(encoding="utf-8"))
        except OSError as error:
            raise LevelRepositoryError("Unable to read packaged level repository") from error

    def get_level(self, number: int) -> Level:
        """Return one known level or raise a typed missing-level error."""
        try:
            return self._levels[number]
        except KeyError as error:
            raise LevelNotFoundError(number) from error

    def all_levels(self) -> tuple[Level, ...]:
        """Return levels ordered by number."""
        return tuple(self._levels[number] for number in sorted(self._levels))


def _parse_payload(payload: Any) -> tuple[Level, ...]:
    if (
        not isinstance(payload, dict)
        or set(payload) != {"levels"}
        or not isinstance(payload["levels"], list)
    ):
        raise LevelDataError("Repository root must contain only a levels array")
    levels: list[Level] = []
    for item in payload["levels"]:
        if not isinstance(item, dict) or set(item) != {"number", "words"}:
            raise LevelDataError("Each level must contain number and words")
        number, words = item["number"], item["words"]
        if isinstance(number, bool) or not isinstance(number, int) or number <= 0:
            raise LevelDataError("Level number must be a positive integer")
        if not isinstance(words, list) or not words:
            raise LevelDataError("Level words must be a non-empty array")
        normalized: list[str] = []
        for word in words:
            if not isinstance(word, str) or not word.strip():
                raise LevelDataError("Every word must be a non-empty string")
            value = unicodedata.normalize("NFC", word.strip()).upper()
            if value not in normalized:
                normalized.append(value)
        levels.append(Level(number, tuple(normalized)))
    return tuple(levels)
