"""Unit tests for strict JSON level repository behavior."""

import json
from pathlib import Path
from typing import Any

import pytest

from word_madness_bot.adapters.database import JsonLevelRepository
from word_madness_bot.domain.errors import DatabaseValidationError, RepositoryError


def _write_database(tmp_path: Path, document: Any) -> Path:
    database_file = tmp_path / "levels.json"
    database_file.write_text(json.dumps(document), encoding="utf-8")
    return database_file


def _valid_level(number: int, word: str = "CAT") -> dict[str, Any]:
    return {"number": number, "letters": list(word), "words": [word]}


def test_lookup_indexes_levels_and_words_deterministically(tmp_path: Path) -> None:
    """Source ordering and query casing do not affect deterministic lookup results."""

    database_file = _write_database(
        tmp_path,
        {
            "schema_version": 1,
            "levels": [
                {"number": 20, "letters": ["C", "A", "T"], "words": ["CAT"]},
                {"number": 3, "letters": ["A", "C", "T"], "words": ["ACT", "CAT"]},
            ],
        },
    )

    repository = JsonLevelRepository(database_file)

    assert tuple(level.number for level in repository.all_levels()) == (3, 20)
    assert repository.get_level(3) is repository.get_level(3)
    assert repository.get_level(999) is None
    assert repository.contains(20)
    assert not repository.contains(True)
    assert tuple(level.number for level in repository.find_levels_by_word(" cat ")) == (3, 20)
    assert repository.find_levels_by_word("at") == ()


def test_invalid_json_reports_line_and_column(tmp_path: Path) -> None:
    """Malformed JSON produces a detailed source-location validation issue."""

    database_file = tmp_path / "levels.json"
    database_file.write_text('{"schema_version": 1,\n"levels": [}', encoding="utf-8")

    with pytest.raises(DatabaseValidationError) as captured:
        JsonLevelRepository(database_file)

    assert captured.value.issues[0].code == "invalid_json"
    assert captured.value.issues[0].path.startswith("line 2, column")


def test_schema_rejects_missing_extra_and_wrong_typed_fields(tmp_path: Path) -> None:
    """Strict validation rejects unknown keys and does not coerce JSON values."""

    database_file = _write_database(
        tmp_path,
        {
            "schema_version": True,
            "levels": [{"number": "1", "letters": "CAT", "extra": 1}],
            "unexpected": False,
        },
    )

    with pytest.raises(DatabaseValidationError) as captured:
        JsonLevelRepository(database_file)

    issues = {(issue.path, issue.code) for issue in captured.value.issues}
    assert ("$.unexpected", "additional_property") in issues
    assert ("$.schema_version", "type") in issues
    assert ("$.levels[0].words", "required") in issues
    assert ("$.levels[0].extra", "additional_property") in issues
    assert ("$.levels[0].number", "type") in issues
    assert ("$.levels[0].letters", "type") in issues


def test_schema_rejects_lowercase_empty_and_non_ascii_values(tmp_path: Path) -> None:
    """Canonical uppercase ASCII and non-empty array constraints are enforced."""

    database_file = _write_database(
        tmp_path,
        {
            "schema_version": 1,
            "levels": [
                {"number": 1, "letters": ["a", "É", "AB"], "words": []},
            ],
        },
    )

    with pytest.raises(DatabaseValidationError) as captured:
        JsonLevelRepository(database_file)

    codes = [issue.code for issue in captured.value.issues]
    assert codes.count("pattern") == 2
    assert "length" in codes
    assert "min_items" in codes


def test_semantic_validation_reports_duplicate_levels_words_and_impossible_words(
    tmp_path: Path,
) -> None:
    """All semantic database errors are aggregated with stable issue ordering."""

    database_file = _write_database(
        tmp_path,
        {
            "schema_version": 1,
            "levels": [
                {"number": 7, "letters": ["C", "A", "T"], "words": ["CAT", "CAT", "DOG"]},
                _valid_level(7),
            ],
        },
    )

    with pytest.raises(DatabaseValidationError) as captured:
        JsonLevelRepository(database_file)

    assert [issue.code for issue in captured.value.issues] == [
        "duplicate_word",
        "unformable_word",
        "duplicate_level",
    ]
    assert "$.levels[0].words[1]" in str(captured.value)


def test_missing_database_is_a_repository_error(tmp_path: Path) -> None:
    """A missing data source is reported through the repository error boundary."""

    with pytest.raises(RepositoryError, match="Level database not found"):
        JsonLevelRepository(tmp_path / "missing.json")
