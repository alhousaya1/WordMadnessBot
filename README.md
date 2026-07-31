# Word Madness Bot

Word Madness Bot is an installable Python application for layered, testable Android automation. The only supported runtime is the `word_madness_bot` package under `src/`.

## Requirements

- Python 3.11 or newer
- Android Debug Bridge (`adb`) for device-backed runs
- one connected, authorized Android device for normal startup

## Install

```console
python -m pip install .
```

For development:

```console
python -m pip install -e ".[dev]"
```

## Configure

Settings are loaded from `WMB_` environment variables. Available variables are `WMB_ADB_EXECUTABLE`, `WMB_ADB_TIMEOUT_SECONDS`, `WMB_ADB_RETRIES`, `WMB_LOG_LEVEL`, `WMB_DATA_DIRECTORY`, `WMB_LOG_DIRECTORY`, `WMB_SCREENSHOT_DIRECTORY`, and `WMB_TEMPLATE_DIRECTORY`.

## Run

Validate configuration and composition without device I/O:

```console
word-madness-bot --dry-run
```

Start with the single connected and authorized device:

```console
word-madness-bot
```

`python -m word_madness_bot` is equivalent. See `docs/OPERATIONS.md` for acceptance and rollback procedures and `docs/TROUBLESHOOTING.md` for typed startup failures.

## Quality

```console
ruff check .
mypy
pytest
python -m build
pip-audit
```
