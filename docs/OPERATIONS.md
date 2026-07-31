# Operations

## Supported runtime

Install the package from source or wheel and invoke `word-madness-bot`. No root script, batch launcher, or prototype package is supported after production cutover.

## Startup and shutdown

Use `word-madness-bot --dry-run` to validate configuration, logging, packaged levels, and dependency composition without Android I/O. Normal startup discovers exactly one online device, selects it, verifies its connection, and emits structured JSON events. Ctrl+C requests graceful shutdown and returns exit code 130.

## Runtime configuration

Configuration is read once from `WMB_` environment variables. Keep ADB timeouts and retries bounded. Mutating input commands are never automatically retried. Logs default to standard error; file logging is enabled only when explicitly composed with a file path.

## Hardware acceptance checklist

Run the opt-in `hardware` test on a supported Android device, then record the device model, Android version, ADB version, screen resolution, density, and test date. Verify:

- discovery and unambiguous selection;
- connection verification;
- resolution and density detection;
- screenshot acquisition and PNG dimensions;
- one test tap and one test swipe at resolution-independent coordinates;
- Back and Home key events;
- a complete fake-backed level workflow before live level acceptance;
- advertisement close-control selection and Back fallback.

Hardware checks are deliberately excluded from the default deterministic suite.

## Release and rollback

Build both source and wheel distributions, install the wheel in a clean virtual environment, run `word-madness-bot --help` and `word-madness-bot --dry-run`, then publish. The rollback point is the release tag immediately preceding the Milestone 11 cutover. Roll back by deploying that tagged artifact; do not restore retired prototype modules onto the production branch.
