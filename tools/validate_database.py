"""Validate the production level database without starting the bot."""

import argparse
import logging
from pathlib import Path
from typing import Sequence

from word_madness_bot.adapters.database import JsonLevelRepository
from word_madness_bot.domain.errors import DatabaseValidationError, RepositoryError

_LOGGER = logging.getLogger(__name__)


def build_parser() -> argparse.ArgumentParser:
    """Build the command-line parser for database validation."""

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "database",
        nargs="?",
        type=Path,
        default=Path("database/levels.json"),
        help="path to levels.json (default: database/levels.json)",
    )
    return parser


def main(arguments: Sequence[str] | None = None) -> int:
    """Validate a database and return a process-compatible status code."""

    database_file = build_parser().parse_args(arguments).database
    try:
        repository = JsonLevelRepository(database_file)
    except DatabaseValidationError as error:
        _LOGGER.error("Validation failed for %s:", error.source)
        for issue in error.issues:
            _LOGGER.error("- %s", issue)
        return 1
    except RepositoryError as error:
        _LOGGER.error("Validation failed: %s", error)
        return 1
    _LOGGER.info("Valid database: %s (%d levels)", database_file, len(repository.all_levels()))
    return 0


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
    raise SystemExit(main())
