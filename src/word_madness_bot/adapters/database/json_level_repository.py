"""Strict, deterministic JSON implementation of the level repository contract."""

import json
from collections.abc import Mapping
from pathlib import Path
from types import MappingProxyType
from typing import Any

from word_madness_bot.domain.errors import (
    DatabaseValidationError,
    RepositoryError,
    ValidationIssue,
)
from word_madness_bot.domain.models import LevelDefinition
from word_madness_bot.services.word_validator import WordValidator

SCHEMA_VERSION = 1
_ROOT_KEYS = frozenset({"schema_version", "levels"})
_LEVEL_KEYS = frozenset({"number", "letters", "words"})


class JsonLevelRepository:
    """Load, validate, and index a local JSON level database exactly once."""

    def __init__(self, database_file: Path, word_validator: WordValidator | None = None) -> None:
        self._database_file = database_file.expanduser().resolve()
        self._word_validator = word_validator or WordValidator()
        levels = self._load_levels()
        self._levels: Mapping[int, LevelDefinition] = MappingProxyType(
            {level.number: level for level in levels}
        )
        reverse_index: dict[str, list[LevelDefinition]] = {}
        for level in levels:
            for word in level.words:
                reverse_index.setdefault(word, []).append(level)
        self._word_index: Mapping[str, tuple[LevelDefinition, ...]] = MappingProxyType(
            {word: tuple(matches) for word, matches in sorted(reverse_index.items())}
        )

    def get_level(self, level_number: int) -> LevelDefinition | None:
        """Return an immutable level definition by exact positive integer key."""

        if isinstance(level_number, bool) or level_number <= 0:
            return None
        return self._levels.get(level_number)

    def contains(self, level_number: int) -> bool:
        """Return whether an exact positive integer level key is indexed."""

        return self.get_level(level_number) is not None

    def find_levels_by_word(self, word: str) -> tuple[LevelDefinition, ...]:
        """Return matching levels in ascending order using normalized exact lookup."""

        normalized = self._word_validator.normalize(word)
        return self._word_index.get(normalized, ())

    def all_levels(self) -> tuple[LevelDefinition, ...]:
        """Return every level in ascending level-number order."""

        return tuple(self._levels.values())

    def _load_levels(self) -> tuple[LevelDefinition, ...]:
        try:
            with self._database_file.open(encoding="utf-8") as database_stream:
                document: Any = json.load(database_stream)
        except FileNotFoundError as error:
            raise RepositoryError(f"Level database not found: {self._database_file}") from error
        except OSError as error:
            message = f"Could not read level database {self._database_file}: {error}"
            raise RepositoryError(message) from error
        except json.JSONDecodeError as error:
            issue = ValidationIssue(
                path=f"line {error.lineno}, column {error.colno}",
                message=error.msg,
                code="invalid_json",
            )
            raise DatabaseValidationError(str(self._database_file), (issue,)) from error

        issues = self._validate_document(document)
        if issues:
            raise DatabaseValidationError(str(self._database_file), issues)

        root = document
        assert isinstance(root, dict)
        raw_levels = root["levels"]
        assert isinstance(raw_levels, list)
        levels = tuple(
            LevelDefinition(
                number=item["number"],
                letters=tuple(item["letters"]),
                words=tuple(item["words"]),
            )
            for item in raw_levels
        )
        return tuple(sorted(levels, key=lambda level: level.number))

    def _validate_document(self, document: object) -> tuple[ValidationIssue, ...]:
        issues: list[ValidationIssue] = []
        if not isinstance(document, dict):
            return (ValidationIssue("$", "must be an object", "type"),)

        self._validate_object_keys(document, _ROOT_KEYS, "$", issues)
        version = document.get("schema_version")
        if isinstance(version, bool) or not isinstance(version, int):
            issues.append(ValidationIssue("$.schema_version", "must be an integer", "type"))
        elif version != SCHEMA_VERSION:
            issues.append(
                ValidationIssue(
                    "$.schema_version",
                    f"must equal supported version {SCHEMA_VERSION}",
                    "const",
                )
            )

        raw_levels = document.get("levels")
        if not isinstance(raw_levels, list):
            issues.append(ValidationIssue("$.levels", "must be an array", "type"))
            return tuple(issues)
        if not raw_levels:
            issues.append(
                ValidationIssue("$.levels", "must contain at least one level", "min_items")
            )

        seen_numbers: dict[int, int] = {}
        for index, raw_level in enumerate(raw_levels):
            level_path = f"$.levels[{index}]"
            if not isinstance(raw_level, dict):
                issues.append(ValidationIssue(level_path, "must be an object", "type"))
                continue
            self._validate_object_keys(raw_level, _LEVEL_KEYS, level_path, issues)
            number = raw_level.get("number")
            if isinstance(number, bool) or not isinstance(number, int) or number <= 0:
                issues.append(
                    ValidationIssue(f"{level_path}.number", "must be a positive integer", "type")
                )
            elif number in seen_numbers:
                issues.append(
                    ValidationIssue(
                        f"{level_path}.number",
                        f"duplicates $.levels[{seen_numbers[number]}].number",
                        "duplicate_level",
                    )
                )
            else:
                seen_numbers[number] = index

            letters = self._validate_string_array(
                raw_level.get("letters"),
                f"{level_path}.letters",
                minimum_length=1,
                item_min_length=1,
                item_max_length=1,
                issues=issues,
            )
            words = self._validate_string_array(
                raw_level.get("words"),
                f"{level_path}.words",
                minimum_length=1,
                item_min_length=2,
                item_max_length=None,
                issues=issues,
            )
            if letters is not None and words is not None:
                issues.extend(
                    self._word_validator.validate_words(
                        words,
                        letters,
                        path=f"{level_path}.words",
                    )
                )
        return tuple(issues)

    @staticmethod
    def _validate_object_keys(
        value: dict[object, object],
        expected: frozenset[str],
        path: str,
        issues: list[ValidationIssue],
    ) -> None:
        string_keys = {key for key in value if isinstance(key, str)}
        for missing in sorted(expected - string_keys):
            issues.append(ValidationIssue(f"{path}.{missing}", "is required", "required"))
        for additional in sorted(string_keys - expected):
            issues.append(
                ValidationIssue(
                    f"{path}.{additional}",
                    "additional properties are not allowed",
                    "additional_property",
                )
            )

    @staticmethod
    def _validate_string_array(
        value: object,
        path: str,
        *,
        minimum_length: int,
        item_min_length: int,
        item_max_length: int | None,
        issues: list[ValidationIssue],
    ) -> tuple[str, ...] | None:
        if not isinstance(value, list):
            issues.append(ValidationIssue(path, "must be an array", "type"))
            return None
        if len(value) < minimum_length:
            issues.append(
                ValidationIssue(path, f"must contain at least {minimum_length} item", "min_items")
            )
        valid_items: list[str] = []
        all_valid = True
        for index, item in enumerate(value):
            item_path = f"{path}[{index}]"
            if not isinstance(item, str):
                issues.append(ValidationIssue(item_path, "must be a string", "type"))
                all_valid = False
                continue
            if not item.isascii() or not item.isalpha() or item != item.upper():
                issues.append(
                    ValidationIssue(
                        item_path,
                        "must contain uppercase ASCII letters only",
                        "pattern",
                    )
                )
                all_valid = False
            if len(item) < item_min_length or (
                item_max_length is not None and len(item) > item_max_length
            ):
                expected = (
                    f"exactly {item_min_length} character"
                    if item_max_length == item_min_length
                    else f"at least {item_min_length} characters"
                )
                issues.append(ValidationIssue(item_path, f"must contain {expected}", "length"))
                all_valid = False
            valid_items.append(item)
        return tuple(valid_items) if all_valid else None
