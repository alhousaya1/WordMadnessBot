# Word Madness Bot

The production application lives in `src/word_madness_bot`. The legacy prototype remains available during migration but is not used by the production runtime.

## Install

Install Python 3.11 or newer and ADB, then install the package:

```console
python -m pip install .
```

## Configure

Runtime settings use `WMB_` environment variables. Supported values include `WMB_ADB_EXECUTABLE`, `WMB_ADB_TIMEOUT_SECONDS`, `WMB_ADB_RETRIES`, `WMB_LOG_LEVEL`, and the data, log, screenshot, and template directory variables documented by `Settings`.

## Run

Validate composition and configuration without contacting an Android device:

```console
word-madness-bot --dry-run
```

Start against the single connected and authorized Android device:

```console
word-madness-bot
```

The equivalent module command is `python -m word_madness_bot`. Startup errors return non-zero exit codes, and interruption triggers graceful shutdown.
