"""Download and validate every ZenWord level for offline use."""

from __future__ import annotations

import argparse
import json
import os
import re
import tempfile
import threading
import time
from collections.abc import Callable, Sequence
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Final, Protocol

import requests
from bs4 import BeautifulSoup, NavigableString, Tag
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

BASE_URL: Final = "https://zenword.net/en/level-{level}/"
DEFAULT_OUTPUT: Final = Path(
    "src/word_madness_bot/resources/levels/levels.json"
)
FIRST_LEVEL: Final = 1
LAST_LEVEL: Final = 1010
USER_AGENT: Final = (
    "WordMadnessBot-level-scraper/1.0 "
    "(offline level database generator; +https://github.com/alhousaya1/WordMadnessBot)"
)
TEMPORARY_HTTP_STATUSES: Final = (408, 425, 429, 500, 502, 503, 504)
WORD_PATTERN: Final = re.compile(r"^[A-Z]+$")
_thread_state = threading.local()


class ScrapeError(RuntimeError):
    """Raised when scraping or validation cannot produce a complete database."""


@dataclass(frozen=True, slots=True)
class LevelRecord:
    number: int
    words: list[str]


class FetchLevel(Protocol):
    def __call__(self, level: int) -> LevelRecord: ...


def build_session(*, request_retries: int = 3) -> requests.Session:
    """Create an HTTP session with bounded transient-failure retries."""
    retry = Retry(
        total=request_retries,
        connect=request_retries,
        read=request_retries,
        status=request_retries,
        other=0,
        backoff_factor=0.75,
        status_forcelist=TEMPORARY_HTTP_STATUSES,
        allowed_methods=frozenset({"GET"}),
        respect_retry_after_header=True,
        raise_on_status=False,
    )
    session = requests.Session()
    session.headers.update(
        {
            "User-Agent": USER_AGENT,
            "Accept": "text/html,application/xhtml+xml",
            "Accept-Language": "en-US,en;q=0.9",
        }
    )
    session.mount("https://", HTTPAdapter(max_retries=retry))
    return session


def parse_level(html: str, expected_level: int) -> LevelRecord:
    """Extract required solution words only from the anchored answer section."""
    soup = BeautifulSoup(html, "html.parser")
    heading = soup.select_one(".levelinfo h2")
    if heading is None or heading.get_text(" ", strip=True) != f"Level {expected_level}":
        raise ScrapeError(f"Level {expected_level}: page heading did not match")

    marker = soup.find(
        "p",
        string=lambda value: value is not None
        and "answers for this level are:" in value.lower(),
    )
    if not isinstance(marker, Tag):
        raise ScrapeError(f"Level {expected_level}: answer marker was not found")

    words: list[str] = []
    for sibling in marker.find_next_siblings():
        if sibling.name == "p" and "bonus words:" in sibling.get_text(" ", strip=True).lower():
            break
        classes = sibling.get("class", [])
        if sibling.name != "div" or "words" not in classes:
            continue
        words.extend(_words_from_block(sibling))

    normalized = list(dict.fromkeys(word.strip().upper() for word in words))
    if not normalized:
        raise ScrapeError(f"Level {expected_level}: no required solution words found")
    invalid = [word for word in normalized if WORD_PATTERN.fullmatch(word) is None]
    if invalid:
        raise ScrapeError(
            f"Level {expected_level}: invalid required words: {', '.join(invalid)}"
        )
    return LevelRecord(expected_level, normalized)


def _words_from_block(block: Tag) -> list[str]:
    words: list[str] = []
    letters: list[str] = []
    for child in block.children:
        if isinstance(child, NavigableString):
            continue
        if not isinstance(child, Tag):
            continue
        if child.name == "span":
            value = child.get_text("", strip=True)
            if value:
                letters.append(value)
        elif child.name == "br":
            if letters:
                words.append("".join(letters))
                letters.clear()
    if letters:
        words.append("".join(letters))
    return words


def fetch_level(
    level: int,
    *,
    timeout_seconds: float = 20.0,
    request_retries: int = 3,
) -> LevelRecord:
    """Fetch and parse one level with per-request retry handling."""
    session = getattr(_thread_state, "session", None)
    if session is None:
        session = build_session(request_retries=request_retries)
        _thread_state.session = session
    response = session.get(
        BASE_URL.format(level=level),
        timeout=(5.0, timeout_seconds),
    )
    if response.status_code in TEMPORARY_HTTP_STATUSES:
        raise ScrapeError(
            f"Level {level}: temporary HTTP status {response.status_code}"
        )
    try:
        response.raise_for_status()
    except requests.HTTPError as error:
        raise ScrapeError(
            f"Level {level}: HTTP status {response.status_code}"
        ) from error
    return parse_level(response.text, level)


def scrape_levels(
    start: int = FIRST_LEVEL,
    end: int = LAST_LEVEL,
    *,
    workers: int = 8,
    retry_rounds: int = 4,
    fetcher: FetchLevel = fetch_level,
    sleeper: Callable[[float], None] = time.sleep,
) -> list[LevelRecord]:
    """Scrape a complete inclusive range, deferring failures to later rounds."""
    if start <= 0 or end < start:
        raise ValueError("level range must be positive and ordered")
    if workers <= 0:
        raise ValueError("workers must be positive")
    if retry_rounds <= 0:
        raise ValueError("retry_rounds must be positive")

    records: dict[int, LevelRecord] = {}
    pending = set(range(start, end + 1))
    failures: dict[int, str] = {}
    for round_number in range(1, retry_rounds + 1):
        current = sorted(pending)
        pending.clear()
        with ThreadPoolExecutor(max_workers=workers) as executor:
            futures = {executor.submit(fetcher, level): level for level in current}
            for future in as_completed(futures):
                level = futures[future]
                try:
                    record = future.result()
                except (requests.RequestException, ScrapeError) as error:
                    pending.add(level)
                    failures[level] = str(error)
                    print(
                        f"[round {round_number}/{retry_rounds}] "
                        f"deferred level {level}: {error}",
                        flush=True,
                    )
                    continue
                if record.number != level:
                    raise ScrapeError(
                        f"Requested level {level}, received level {record.number}"
                    )
                records[level] = record
                failures.pop(level, None)

        print(
            f"[round {round_number}/{retry_rounds}] "
            f"complete={len(records)} pending={len(pending)}",
            flush=True,
        )
        if not pending:
            break
        if round_number < retry_rounds:
            sleeper(min(2 ** (round_number - 1), 30))

    if pending:
        summary = "; ".join(
            f"{level}: {failures.get(level, 'unknown failure')}"
            for level in sorted(pending)
        )
        raise ScrapeError(f"Unable to scrape all levels after retries: {summary}")
    return [records[level] for level in range(start, end + 1)]


def validate_records(
    records: Sequence[LevelRecord],
    *,
    start: int = FIRST_LEVEL,
    end: int = LAST_LEVEL,
) -> None:
    """Validate schema content and exact contiguous level coverage."""
    expected = list(range(start, end + 1))
    actual = [record.number for record in records]
    if actual != expected:
        raise ScrapeError(
            f"Expected contiguous levels {start}-{end}; received {actual[:5]}..."
        )
    for record in records:
        if not record.words:
            raise ScrapeError(f"Level {record.number}: words must not be empty")
        if len(record.words) != len(set(record.words)):
            raise ScrapeError(f"Level {record.number}: words must be unique")
        if any(WORD_PATTERN.fullmatch(word) is None for word in record.words):
            raise ScrapeError(f"Level {record.number}: words must be uppercase A-Z")


def write_database(records: Sequence[LevelRecord], output: Path) -> None:
    """Validate and atomically replace the output with the repository schema."""
    if not records:
        raise ScrapeError("Cannot write an empty level database")
    validate_records(
        records,
        start=records[0].number,
        end=records[-1].number,
    )
    payload: dict[str, Any] = {
        "levels": [asdict(record) for record in records],
    }
    output.parent.mkdir(parents=True, exist_ok=True)
    temporary_path: Path | None = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="w",
            encoding="utf-8",
            newline="\n",
            prefix=f".{output.name}.",
            suffix=".tmp",
            dir=output.parent,
            delete=False,
        ) as temporary:
            json.dump(payload, temporary, ensure_ascii=False, indent=2)
            temporary.write("\n")
            temporary_path = Path(temporary.name)
        parsed = json.loads(temporary_path.read_text(encoding="utf-8"))
        if parsed != payload:
            raise ScrapeError("Generated JSON did not round-trip exactly")
        os.replace(temporary_path, output)
    finally:
        if temporary_path is not None and temporary_path.exists():
            temporary_path.unlink()


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Scrape ZenWord solution levels into the packaged JSON database."
    )
    parser.add_argument("--start", type=int, default=FIRST_LEVEL)
    parser.add_argument("--end", type=int, default=LAST_LEVEL)
    parser.add_argument("--workers", type=int, default=8)
    parser.add_argument("--retry-rounds", type=int, default=4)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    records = scrape_levels(
        args.start,
        args.end,
        workers=args.workers,
        retry_rounds=args.retry_rounds,
    )
    validate_records(records, start=args.start, end=args.end)
    write_database(records, args.output)
    print(
        f"Wrote {len(records)} validated levels to {args.output}",
        flush=True,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
