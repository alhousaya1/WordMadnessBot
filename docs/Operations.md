# Operations

## Structured Logging

All layers use the standard `logging` API with stable `event` fields. Production logging
can use `JsonFormatter` to emit one JSON object per record, including timestamp, severity,
logger, message, structured subsystem fields, and exception diagnostics. Logging setup is
explicit and idempotent.

## Metrics

`MetricsCollector` is enabled by `WORD_MADNESS_METRICS_ENABLED`. Disabled collection is a
complete no-op. It provides thread-safe counters and bounded aggregates rather than
retaining individual samples. Stable timing names cover screenshot capture, Vision,
State classification, database lookup, Swipe planning, and Decision Engine processing.
Application lifecycle code records screenshot, Vision-pipeline, database, observation, and
Decision Engine metrics. Stable metric names and the collector API exist for State and
Swipe boundaries; their internal composition remains independently instrumentable by an
embedding host.

## Health

`HealthReporter` records process start and the latest successful application heartbeat.
Reports contain status, uptime, heartbeat age, observation count, and failure count.
`WORD_MADNESS_HEALTH_STALE_AFTER_SECONDS` controls when a missing heartbeat becomes stale.
Health reporting performs no external network or device probe.

## Diagnostics

Diagnostics are disabled unless `WORD_MADNESS_DIAGNOSTICS_ENABLED=true`. When enabled,
`DiagnosticsReporter` atomically writes `diagnostics/diagnostics.json` with health,
aggregate metrics, runtime version, and non-secret configuration flags. Reports never
include device commands, environment values, screenshots, or database contents.

Debug/diagnostic artifacts are independently controlled by
`WORD_MADNESS_DIAGNOSTIC_ARTIFACTS_ENABLED`. `ArtifactManager` sanitizes filenames, writes
atomically, and enforces configurable file-count and byte retention limits. Vision debug
images remain controlled by `WORD_MADNESS_SAVE_DEBUG_IMAGES`.

## Performance and Soak Checks

Run `PYTHONPATH=src python tools/benchmark_vision.py` for a bounded real-fixture Vision
benchmark. The automated performance test applies a generous regression ceiling, while
the bounded state-machine soak test validates deterministic transitions across 10,000
cycles. These checks do not execute Android input.
