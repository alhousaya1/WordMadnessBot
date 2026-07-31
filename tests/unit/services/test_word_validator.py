"""Unit tests for pure word normalization and multiset validation."""

from word_madness_bot.services.word_validator import WordValidator


def test_normalize_is_deterministic() -> None:
    """Lookup normalization strips only boundaries and uppercases text."""

    assert WordValidator.normalize("  found  ") == "FOUND"


def test_can_form_respects_repeated_letter_counts() -> None:
    """A letter cannot be consumed more times than the wheel provides it."""

    validator = WordValidator()

    assert validator.can_form("TOOL", ("T", "O", "O", "L"))
    assert not validator.can_form("TOOL", ("T", "O", "L"))


def test_validate_words_reports_duplicates_and_unformable_words() -> None:
    """Semantic validation returns every deterministic issue with an exact path."""

    issues = WordValidator().validate_words(
        ("CAT", "cat", "DOG"),
        ("C", "A", "T"),
        path="$.levels[0].words",
    )

    assert [(issue.path, issue.code) for issue in issues] == [
        ("$.levels[0].words[1]", "duplicate_word"),
        ("$.levels[0].words[2]", "unformable_word"),
    ]
