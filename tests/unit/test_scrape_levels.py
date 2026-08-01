from __future__ import annotations

import json
from pathlib import Path

import pytest

from scrape_levels import (
    LevelRecord,
    ScrapeError,
    parse_level,
    scrape_levels,
    validate_records,
    write_database,
)

HTML = """
<html>
  <div class="content">
    <div class="levelinfo"><h2>Level 7</h2><p>Letters: ACT</p></div>
    <p>Word answers for this level are:</p>
    <div class="words">
      <span>C</span><span>A</span><span>T</span><br>
      <span>A</span><span>C</span><span>T</span><br>
    </div>
    <div class="advertisement"><span>BUY</span><br></div>
    <div class="words"><span>T</span><span>A</span><span>C</span><br></div>
    <p>Bonus words:</p>
    <div class="words"><span>AT</span><br></div>
    <p>Hint: try a short word.</p>
    <div class="levels"><a href="/en/level-8/">Next level</a></div>
  </div>
</html>
"""


def test_parser_extracts_only_required_answer_blocks() -> None:
    assert parse_level(HTML, 7) == LevelRecord(7, ["CAT", "ACT", "TAC"])


def test_parser_rejects_wrong_level_and_missing_answers() -> None:
    with pytest.raises(ScrapeError, match="heading"):
        parse_level(HTML, 8)
    with pytest.raises(ScrapeError, match="no required"):
        parse_level(HTML.replace('class="words"', 'class="other"'), 7)


def test_failed_level_is_deferred_and_retried_later() -> None:
    attempts: dict[int, int] = {}

    def fetch(level: int) -> LevelRecord:
        attempts[level] = attempts.get(level, 0) + 1
        if level == 2 and attempts[level] == 1:
            raise ScrapeError("temporary failure")
        return LevelRecord(level, [f"WORD{level}".replace("1", "A").replace("2", "B")])

    records = scrape_levels(
        1,
        2,
        workers=1,
        retry_rounds=2,
        fetcher=fetch,
        sleeper=lambda _: None,
    )

    assert [record.number for record in records] == [1, 2]
    assert attempts == {1: 1, 2: 2}


def test_validation_requires_complete_contiguous_unique_uppercase_levels() -> None:
    with pytest.raises(ScrapeError, match="contiguous"):
        validate_records([LevelRecord(1, ["CAT"]), LevelRecord(3, ["DOG"])], end=3)
    with pytest.raises(ScrapeError, match="unique"):
        validate_records([LevelRecord(1, ["CAT", "CAT"])], end=1)
    with pytest.raises(ScrapeError, match="uppercase"):
        validate_records([LevelRecord(1, ["Cat"])], end=1)


def test_database_write_uses_repository_schema_and_valid_json(tmp_path: Path) -> None:
    output = tmp_path / "levels.json"
    records = [LevelRecord(1, ["CAT", "ACT"]), LevelRecord(2, ["DOG"])]

    write_database(records, output)

    assert json.loads(output.read_text(encoding="utf-8")) == {
        "levels": [
            {"number": 1, "words": ["CAT", "ACT"]},
            {"number": 2, "words": ["DOG"]},
        ]
    }
