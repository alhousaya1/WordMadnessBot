"""Production command-line interface with explicit exit codes."""

import argparse
import logging
import signal
from collections.abc import Sequence

from word_madness_bot.application import Application
from word_madness_bot.bootstrap import build_application
from word_madness_bot.config import Settings
from word_madness_bot.observability import configure_logging

_LOGGER = logging.getLogger(__name__)


def build_parser() -> argparse.ArgumentParser:
    """Build the CLI parser without constructing runtime dependencies."""

    parser = argparse.ArgumentParser(prog="word-madness-bot")
    subcommands = parser.add_subparsers(dest="command", required=True)
    subcommands.add_parser("run", help="run autonomous gameplay until shutdown")
    subcommands.add_parser("validate-config", help="validate runtime configuration")
    subcommands.add_parser("validate-database", help="validate and count database levels")
    subcommands.add_parser("check-device", help="check configured Android connectivity")
    subcommands.add_parser("capture-screenshot", help="save one diagnostic screenshot")
    observe = subcommands.add_parser("observe", help="perform one observation without input")
    observe.add_argument("--dry-run", action="store_true", required=True)
    return parser


def run_cli(arguments: Sequence[str] | None = None, application: Application | None = None) -> int:
    """Dispatch lifecycle operations without containing gameplay logic."""

    parsed = build_parser().parse_args(arguments)
    try:
        app = application or build_application(Settings.from_environment())
        if parsed.command == "validate-config":
            app.validate_configuration()
            _LOGGER.info("Configuration is valid")
        elif parsed.command == "validate-database":
            _LOGGER.info("Database is valid", extra={"level_count": app.validate_database()})
        elif parsed.command == "check-device":
            _LOGGER.info("Device is available", extra={"device_serial": app.check_device()})
        elif parsed.command == "capture-screenshot":
            _LOGGER.info(
                "Diagnostic screenshot saved", extra={"path": str(app.capture_diagnostic())}
            )
        elif parsed.command == "observe":
            observation = app.observe_once()
            _LOGGER.info(
                "Dry-run observation complete",
                extra={"state": observation.state.state.value, "revision": observation.revision},
            )
        elif parsed.command == "run":
            _install_shutdown_handlers(app)
            app.run_continuous()
        return 0
    except KeyboardInterrupt:
        if application is not None:
            application.request_shutdown()
        return 130
    except Exception:
        _LOGGER.exception("Command failed", extra={"command": parsed.command})
        return 1


def _install_shutdown_handlers(application: Application) -> None:
    """Translate termination signals into cooperative application shutdown."""

    def request_shutdown(signum: int, frame: object) -> None:
        _LOGGER.info("Shutdown requested", extra={"signal": signum})
        application.request_shutdown()

    signal.signal(signal.SIGINT, request_shutdown)
    signal.signal(signal.SIGTERM, request_shutdown)


def main(arguments: Sequence[str] | None = None) -> int:
    """Configure logging and return a process-compatible CLI exit code."""

    settings = Settings.from_environment()
    configure_logging(level=settings.log_level)
    return run_cli(arguments)
