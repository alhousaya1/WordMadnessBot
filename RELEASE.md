# Word Madness Bot Release Guide

## Release Status

Milestone 13 implements the autonomous Android runtime: the production `run` command now
captures a frame, runs Vision and State, asks the Decision Engine for exactly one typed
command, executes that command through ADB, captures a strictly newer frame, and verifies
the command before any subsequent decision. Tap, multi-point swipe, Back-key, advertisement,
and bounded recovery commands are connected through replaceable adapters.

The software remains a **hardware-acceptance release candidate**, not an unconditional
production release. The repository has no attached Android device in CI, its checked-in
database is intentionally incomplete, and production template assets are not populated.
See **Limitations** and complete the hardware gates before unattended use.

## Installation

### Windows source installation

1. Install Python 3.11 or newer, Android Platform Tools, and Tesseract OCR.
2. Connect and authorize exactly one Android device, or set `WORD_MADNESS_DEVICE_SERIAL`.
3. Clone this repository.
4. Run `INSTALL.bat`. It creates `.venv`, installs the package in editable mode, and runs
   configuration and database validation.
5. Run `word-madness-bot check-device` from the activated environment.

Manual installation:

```shell
python -m venv .venv
.venv\Scripts\activate
python -m pip install --upgrade pip
python -m pip install -e ".[dev]"
word-madness-bot validate-config
word-madness-bot validate-database
```

The wheel/sdist installs `database/levels.json` and template manifests under the Python
installation prefix. Source/editable installations use the repository root.

## Configuration

Configuration is read from `WORD_MADNESS_*` process environment variables. `.env` files
are not loaded automatically. `.env.example` is the complete authoritative option list
with defaults grouped into paths/logging, ADB, State, Swipe, ads, Decision/runtime, and
observability. Invalid booleans, ranges, timeouts, counts, paths, and log levels fail at
startup with a nonzero exit code.

Diagnostics, diagnostic artifacts, and Vision debug images are independently disabled by
default. See `docs/Operations.md` for output and retention behavior.

## Usage

```shell
word-madness-bot validate-config
word-madness-bot validate-database
word-madness-bot check-device
word-madness-bot capture-screenshot
word-madness-bot observe --dry-run
word-madness-bot run
```

`observe --dry-run` never creates or executes Android input. `run` is autonomous and may
tap, trace swipe paths, and send the configured advertisement Back key. It serializes each
command and requires a fresh screenshot and verification before selecting another command.
It stops cooperatively on Ctrl+C, SIGINT, or SIGTERM. All CLI commands return
process-compatible exit codes: `0` for success, `1` for an operational/configuration error,
and `130` for keyboard interruption.

## Troubleshooting

- **`ADB command failed`**: install Platform Tools, ensure `adb` is on `PATH`, run
  `adb devices`, authorize the phone, or set `WORD_MADNESS_ADB_COMMAND`.
- **No or multiple devices**: disconnect extra devices or set an exact device serial.
- **OCR command unavailable**: install Tesseract and ensure `tesseract` is on `PATH`.
- **Database validation fails**: run `word-madness-bot validate-database`; diagnostics
  include exact JSON paths and validation codes.
- **Observation is `UNKNOWN`**: State stabilization requires consecutive confident frames;
  inspect configured debug images and confidence thresholds.
- **No diagnostics file**: set `WORD_MADNESS_DIAGNOSTICS_ENABLED=true` before startup.
- **Install cannot download packages**: verify proxy/index settings or use an approved
  offline wheelhouse. Dependencies are NumPy and Pillow; dev checks additionally use
  pytest, pytest-cov, mypy, and Ruff.

## Limitations

- Real-device multi-level solving, device disconnects, supported Android `motionevent`
  behavior, advertisement variants, and multi-resolution operation require opt-in hardware
  acceptance testing before production deployment.
- The checked-in level database contains only the validated sample level 90 and is not a
  complete game dataset.
- Template manifests contain no production Home, Victory, or advertisement image assets.
- Tesseract OCR is an external executable and is not installed by pip.
- CI hardware tests are skipped unless `WORD_MADNESS_RUN_DEVICE_E2E=1` is explicitly set.

### Physical multi-level acceptance

Prepare a device at a database-backed level and run:

```shell
set WORD_MADNESS_RUN_DEVICE_E2E=1
set WORD_MADNESS_E2E_START_LEVEL=90
set WORD_MADNESS_E2E_END_LEVEL=92
set WORD_MADNESS_E2E_MAXIMUM_CYCLES=200
pytest -q tests/e2e/test_real_multi_level.py
```

The start and the following two levels must all exist in the configured database. A release
operator must retain this passing result with the device model, Android version, screen
geometry, and template/data revision as release evidence.
