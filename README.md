# Word Madness Bot

> **Release status:** autonomous hardware-integration release candidate. Android command
> execution is implemented, but physical-device acceptance, complete game data, and
> production templates remain release gates. See [`RELEASE.md`](RELEASE.md).

Word Madness Bot is a modular Android automation application for the Word Madness
(ZenWord) game. The implementation follows the strict layered architecture in
`docs/Architecture.md`; each external capability is represented by a typed contract so
implementations can be replaced without changing domain or gameplay logic.

## Current status

The project foundation provides typed domain models, dependency-inversion contracts,
validated environment-based configuration, and configurable logging. The local JSON
level repository provides strictly validated, deterministic level and word lookup. The
production composition root supplies ADB connectivity and input, diagnostic capture,
dry-run observation, and a cooperative autonomous runtime through the installed CLI.

## Command-line interface

The installed `word-madness-bot` entry point supports:

```shell
word-madness-bot validate-config
word-madness-bot validate-database
word-madness-bot check-device
word-madness-bot capture-screenshot
word-madness-bot observe --dry-run
word-madness-bot run
```

Dry-run observation captures and analyzes one frame but never creates or executes input.
Continuous run executes one typed command at a time and always captures a newer observation
for verification before selecting another command. It cooperatively stops on `SIGINT` or
`SIGTERM` and returns process exit codes instead of requesting interactive input.

## Observability and diagnostics

Runtime metrics, health reporting, JSON structured logs, bounded diagnostic artifacts,
and atomic diagnostics reports are configurable independently. Diagnostics and artifact
output are disabled by default. See `docs/Operations.md` for environment switches,
retention behavior, report contents, and performance/soak commands.

## Requirements

- Python 3.11 or newer
- Windows for the supplied batch scripts
- Android Platform Tools for device commands
- Tesseract OCR for level and letter recognition

## Installation

On Windows, run `INSTALL.bat`. It creates `.venv` and installs the package with its
development tools. On other platforms:

```shell
python -m venv .venv
. .venv/bin/activate
python -m pip install -e '.[dev]'
```

Copy `.env.example` to `.env` only if local overrides are needed. The application does
not load `.env` implicitly; export required values in the process environment before
starting the CLI.

## Development checks

```shell
ruff check .
mypy
pytest
PYTHONPATH=src python tools/validate_database.py
```

Runtime logs, screenshots, and debug artifacts are excluded from version control.

See [`RELEASE_CHECKLIST.md`](RELEASE_CHECKLIST.md) for the final audited GO/NO-GO status.
