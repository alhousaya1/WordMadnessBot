"""Command-line boundary for the production runtime."""

from __future__ import annotations

import argparse
import sys
from collections.abc import Callable, Mapping, Sequence
from typing import Protocol, TextIO

from word_madness_bot import __version__
from word_madness_bot.bootstrap import build_runtime
from word_madness_bot.config.settings import Settings
from word_madness_bot.domain.errors import ConfigurationError, WordMadnessError
from word_madness_bot.runtime_lock import SingleInstanceGuard


class Runtime(Protocol):
    def start(self, *, dry_run: bool = False) -> None: ...
    def shutdown(self) -> None: ...


RuntimeBuilder = Callable[[Settings], Runtime]


def create_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="word-madness-bot")
    parser.add_argument("--version", action="version", version=f"%(prog)s {__version__}")
    parser.add_argument(
        "--dry-run", action="store_true", help="build the application without device I/O"
    )
    return parser


def main(
    argv: Sequence[str] | None = None,
    *,
    environ: Mapping[str, str] | None = None,
    runtime_builder: RuntimeBuilder = build_runtime,
    stderr: TextIO | None = None,
) -> int:
    """Start and always shut down the production runtime with stable exit codes."""
    arguments = create_parser().parse_args(argv)
    error_stream = stderr or sys.stderr
    runtime: Runtime | None = None
    try:
        settings = Settings.from_environment(environ)
        with SingleInstanceGuard():
            runtime = runtime_builder(settings)
            runtime.start(dry_run=arguments.dry_run)
        return 0
    except ConfigurationError as error:
        print(f"configuration error: {error}", file=error_stream)
        return 2
    except KeyboardInterrupt:
        print("shutdown requested", file=error_stream)
        return 130
    except WordMadnessError as error:
        print(f"runtime error: {error}", file=error_stream)
        return 1
    finally:
        if runtime is not None:
            runtime.shutdown()
