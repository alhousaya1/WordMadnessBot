# Production Architecture Migration Plan

## 1. Purpose

This plan migrates the current Word Madness Bot prototype into the layered,
replaceable architecture defined by `docs/SRS.md` and `docs/Architecture.md`.
It treats the repository as it exists today and does not assume that any
production implementation, contract, test suite, package metadata, or CI
configuration already exists.

The migration is intentionally incremental. Each milestone is independently
mergeable, has its own tests and acceptance criteria, and leaves the repository
in a usable state. The legacy entry point remains available until the final
cutover; new production modules never import from `core/`, `config/`, or other
prototype modules.

## 2. Audited Starting Point

The current repository is a legacy prototype with:

- a root `main.py` that directly composes configuration, ADB, screenshot, and
  vision behavior;
- global configuration and an import-time file logger under `config/`;
- prototype ADB, screen, and circle detection under `core/`;
- empty placeholders for JSON loading, level reading, swipe generation, and
  scraping;
- no `src/` package, production contracts, tests, packaging metadata, static
  analysis configuration, or CI workflow;
- an empty `README.md` and flat runtime dependency list;
- committed bytecode, screenshots, debug images, and runtime logs;
- template and database directories that exist locally but contain no tracked
  production data;
- historical logs demonstrating basic ADB discovery, 1440x3120 resolution
  detection, screenshot capture, and experimental circle detection.

Prototype behavior is evidence for migration tests, not a production API. No
production module should depend on the prototype.

## 3. Target Principles

The target implementation must preserve the documented architecture:

1. Configuration and logging are infrastructure shared through explicit
   composition, not global import side effects.
2. Android communication is isolated behind replaceable contracts.
3. Screenshot acquisition is separate from image interpretation.
4. Vision produces observations and never generates input events.
5. Game-state detection converts observations into domain states.
6. The decision engine orchestrates adjacent services and contains no OCR or
   device-specific code.
7. Level knowledge is loaded from data, never hardcoded into gameplay logic.
8. Swipe generation converts domain inputs into resolution-independent paths
   and never calls ADB.
9. Lower layers report typed failures upward; higher layers own retry and
   recovery policy where appropriate.
10. Every boundary is typed, testable, and replaceable.

## 4. Proposed Production Layout

```text
src/word_madness_bot/
├── __init__.py
├── __main__.py
├── bootstrap.py
├── cli.py
├── config/
│   ├── __init__.py
│   ├── logging.py
│   └── settings.py
├── domain/
│   ├── __init__.py
│   ├── errors.py
│   ├── geometry.py
│   ├── models.py
│   └── states.py
├── application/
│   ├── __init__.py
│   ├── ports/
│   │   ├── __init__.py
│   │   ├── android.py
│   │   ├── levels.py
│   │   └── vision.py
│   ├── decision_engine.py
│   └── game_loop.py
├── infrastructure/
│   ├── __init__.py
│   ├── adb/
│   │   ├── __init__.py
│   │   ├── client.py
│   │   └── screenshot.py
│   └── levels/
│       ├── __init__.py
│       └── json_repository.py
├── vision/
│   ├── __init__.py
│   ├── classifier.py
│   ├── letters.py
│   ├── ocr.py
│   ├── preprocessing.py
│   └── templates.py
├── gameplay/
│   ├── __init__.py
│   ├── ads.py
│   ├── state_detector.py
│   └── swipe_generator.py
└── resources/
    ├── levels/
    └── templates/
```

Tests should mirror these boundaries under `tests/unit/`, with contract and
workflow tests under `tests/contract/` and `tests/integration/`.

## 5. Delivery Rules for Every Milestone

Every milestone must:

- branch from the latest `main` and contain only its declared scope;
- avoid imports from the prototype into the production package;
- include type hints, docstrings, structured logging, and typed errors;
- keep all coordinates resolution-independent;
- pass `ruff check .`, `mypy`, and `pytest` before merge;
- include deterministic tests that do not require a physical Android device;
- preserve the current prototype entry point until the cutover milestone;
- document any newly stable public contract in code and tests;
- be squashable or mergeable without relying on unmerged future milestones.

Hardware smoke tests may supplement automated tests, but may never replace
them or be required for the default test suite.

## 6. Milestones

### Milestone 0 — Repository Hygiene and Reproducible Tooling

**Goal**

Establish a clean, installable Python project and enforce quality gates without
changing bot behavior. Stop tracking generated artifacts and create the empty
production package and test structure.

**Files to create**

- `.gitignore`
- `pyproject.toml`
- `src/word_madness_bot/__init__.py`
- `tests/__init__.py`
- `tests/test_package.py`
- `.github/workflows/quality.yml`

**Files to modify**

- `README.md`
- `requirements.txt` (either reduce it to runtime compatibility requirements
  or point contributors to package extras in `pyproject.toml`)

**Files to remove from tracking**

- `config/__pycache__/*.pyc`
- `core/__pycache__/*.pyc`
- `logs/*.log`
- `debug/letter_circle_detected.png`
- `screenshots/latest.png`

**Tests required**

- production package import test;
- build/install smoke test in an isolated environment;
- CI execution of Ruff, mypy, and pytest;
- assertion that generated runtime paths are ignored.

**Independent merge criteria**

The legacy application still starts as before, the new package imports, a wheel
can be built, and all quality gates pass from a clean checkout.

---

### Milestone 1 — Production Foundation, Contracts, Configuration, and Logging

**Goal**

Define the stable domain types and replaceable ports that all later layers use.
Add typed settings and structured logging without import-time filesystem side
effects.

**Files to create**

- `src/word_madness_bot/config/__init__.py`
- `src/word_madness_bot/config/settings.py`
- `src/word_madness_bot/config/logging.py`
- `src/word_madness_bot/domain/__init__.py`
- `src/word_madness_bot/domain/errors.py`
- `src/word_madness_bot/domain/geometry.py`
- `src/word_madness_bot/domain/models.py`
- `src/word_madness_bot/domain/states.py`
- `src/word_madness_bot/application/__init__.py`
- `src/word_madness_bot/application/ports/__init__.py`
- `src/word_madness_bot/application/ports/android.py`
- `src/word_madness_bot/application/ports/levels.py`
- `src/word_madness_bot/application/ports/vision.py`
- `tests/unit/config/test_settings.py`
- `tests/unit/config/test_logging.py`
- `tests/unit/domain/test_geometry.py`
- `tests/contract/test_ports.py`

**Files to modify**

- `pyproject.toml` (declare settings/logging dependencies only if needed)

**Tests required**

- default and environment-overridden settings;
- invalid configuration rejection;
- log events contain level, event name, timestamp, and structured context;
- logging configuration is idempotent and does not write during import;
- geometry validation and scaling behavior;
- runtime protocol conformance tests using fakes.

**Independent merge criteria**

The production contracts can be imported and implemented by test fakes, with no
prototype imports and no device or filesystem required.

---

### Milestone 2 — ADB Transport and Screenshot Acquisition

**Goal**

Implement the documented ADB interface as infrastructure behind the Android
port: device discovery and selection, connection verification, device metadata,
screen resolution and density, shell commands, screenshots, taps, swipes, Back,
and Home. Add bounded timeouts, selective retries, structured events, and typed
exceptions. Keep screenshot acquisition free of OCR and image analysis.

**Files to create**

- `src/word_madness_bot/infrastructure/__init__.py`
- `src/word_madness_bot/infrastructure/adb/__init__.py`
- `src/word_madness_bot/infrastructure/adb/client.py`
- `src/word_madness_bot/infrastructure/adb/screenshot.py`
- `tests/unit/infrastructure/adb/test_client.py`
- `tests/unit/infrastructure/adb/test_screenshot.py`
- `tests/contract/test_android_port.py`
- `tests/integration/test_adb_smoke.py`

**Files to modify**

- `src/word_madness_bot/application/ports/android.py` only if implementation
  experience reveals a contract ambiguity;
- `src/word_madness_bot/domain/errors.py` for transport-specific typed errors;
- `pyproject.toml` only if an ADB library is selected.

**Tests required**

- parsing zero, one, multiple, offline, unauthorized, and malformed devices;
- explicit and automatic device selection;
- connection-state verification;
- physical and overridden size/density parsing;
- text and binary subprocess behavior;
- valid, empty, corrupt, and failed screenshot capture;
- atomic screenshot writes;
- tap, swipe, Back, Home, and arbitrary shell argument construction;
- timeout exhaustion, transient retry/backoff, permanent errors, and missing
  executable behavior;
- proof that mutating input events are not duplicated by unsafe retries;
- opt-in hardware smoke test marked and skipped by default.

**Independent merge criteria**

The adapter satisfies the Android port entirely through mocked subprocesses;
the default suite requires no device, and no gameplay or vision code is added.

---

### Milestone 3 — Resolution-Independent Screen Geometry

**Goal**

Create a single coordinate and region-scaling service so no downstream layer is
tied to the reference Galaxy S25 Ultra resolution.

**Files to create**

- `src/word_madness_bot/gameplay/__init__.py`
- `src/word_madness_bot/gameplay/geometry.py`
- `tests/unit/gameplay/test_geometry.py`

**Files to modify**

- `src/word_madness_bot/domain/geometry.py`
- `src/word_madness_bot/domain/models.py`
- `src/word_madness_bot/application/ports/android.py` only if resolution data
  needs a clarified value object;

**Tests required**

- point, rectangle, radius, duration, and path scaling;
- portrait resolutions with different aspect ratios and densities;
- clamping and out-of-bounds rejection;
- round-trip normalization within documented rounding tolerance;
- zero and invalid resolution handling.

**Independent merge criteria**

The geometry service operates only on domain values, imports no ADB or vision
implementation, and is fully usable by future modules.

---

### Milestone 4 — Vision Engine

**Goal**

Implement image loading, preprocessing, template matching, circle detection,
letter extraction, and OCR as replaceable vision components. Vision returns
observations and never sends Android input.

**Files to create**

- `src/word_madness_bot/vision/__init__.py`
- `src/word_madness_bot/vision/preprocessing.py`
- `src/word_madness_bot/vision/templates.py`
- `src/word_madness_bot/vision/letters.py`
- `src/word_madness_bot/vision/ocr.py`
- `src/word_madness_bot/vision/classifier.py`
- `tests/unit/vision/test_preprocessing.py`
- `tests/unit/vision/test_templates.py`
- `tests/unit/vision/test_letters.py`
- `tests/unit/vision/test_ocr.py`
- `tests/unit/vision/test_classifier.py`
- `tests/fixtures/images/` with minimal, licensed synthetic fixtures

**Files to modify**

- `src/word_madness_bot/application/ports/vision.py`
- `src/word_madness_bot/domain/models.py`
- `src/word_madness_bot/domain/errors.py`
- `pyproject.toml` for explicit vision/OCR dependencies and extras

**Tests required**

- image decode success and corrupt/missing input;
- deterministic preprocessing output properties;
- template threshold, no-match, and multiple-match behavior;
- circle and letter extraction with synthetic fixtures;
- OCR engine success, empty output, malformed output, and engine failure;
- classifier confidence and unknown classification;
- proof that vision modules do not import Android input infrastructure.

**Independent merge criteria**

All vision behavior runs against fixtures and fakes, emits typed observations,
and has no ADB or decision-engine dependency.

---

### Milestone 5 — Game-State Detection

**Goal**

Translate vision observations into the documented Home, Playing, Victory,
Advertisement, and Unknown domain states, including confidence and evidence.

**Files to create**

- `src/word_madness_bot/gameplay/state_detector.py`
- `tests/unit/gameplay/test_state_detector.py`
- `tests/contract/test_game_states.py`

**Files to modify**

- `src/word_madness_bot/domain/states.py`
- `src/word_madness_bot/domain/models.py`
- `src/word_madness_bot/application/ports/vision.py` only for clarified
  observation fields;

**Tests required**

- each documented state and Unknown fallback;
- ambiguous and conflicting evidence;
- confidence boundaries;
- detector behavior when OCR or templates are unavailable;
- invariant that state detection causes no device input.

**Independent merge criteria**

The detector accepts only vision-port outputs and returns domain state values;
it can be exercised without ADB, a database, or orchestration.

---

### Milestone 6 — Data-Driven Level Repository

**Goal**

Implement validated JSON-backed level and word lookup, making game knowledge
data-driven as required by the SRS.

**Files to create**

- `src/word_madness_bot/infrastructure/levels/__init__.py`
- `src/word_madness_bot/infrastructure/levels/json_repository.py`
- `src/word_madness_bot/resources/levels/levels.json`
- `tests/unit/infrastructure/levels/test_json_repository.py`
- `tests/contract/test_level_repository.py`
- `tests/fixtures/levels/valid.json`
- `tests/fixtures/levels/invalid.json`

**Files to modify**

- `src/word_madness_bot/application/ports/levels.py`
- `src/word_madness_bot/domain/models.py`
- `src/word_madness_bot/domain/errors.py`
- `tools/scraper.py` only if it is deliberately retained as an offline data
  producer; otherwise defer its replacement to cutover;

**Tests required**

- valid load and lookup by level;
- Unicode normalization, case policy, duplicate words, and ordering;
- missing file, malformed JSON, invalid schema, duplicate level, and missing
  level behavior;
- packaged-resource loading after wheel installation;
- repository contract tests shared by future backends.

**Independent merge criteria**

The repository serves validated domain objects through the levels port and has
no vision, ADB, or gameplay dependency.

---

### Milestone 7 — Swipe Path Generation

**Goal**

Convert detected letters and target words into validated,
resolution-independent swipe paths without performing Android input.

**Files to create**

- `src/word_madness_bot/gameplay/swipe_generator.py`
- `tests/unit/gameplay/test_swipe_generator.py`
- `tests/property/test_swipe_paths.py`

**Files to modify**

- `src/word_madness_bot/domain/geometry.py`
- `src/word_madness_bot/domain/models.py`

**Tests required**

- repeated letters, impossible words, missing letters, and deterministic path
  selection;
- normalized-to-device coordinate scaling;
- path bounds, ordering, and minimum duration;
- property tests for arbitrary valid wheels and words;
- invariant that swipe generation imports no ADB implementation.

**Independent merge criteria**

Given domain inputs, the module deterministically returns a path value object
and performs no I/O.

---

### Milestone 8 — Decision Engine and Level Workflow

**Goal**

Implement the documented Home → read level → load words → play level → detect
completion flow as orchestration over ports. Keep OCR in vision, lookup in the
repository, and touch execution in the Android adapter.

**Files to create**

- `src/word_madness_bot/application/decision_engine.py`
- `src/word_madness_bot/application/game_loop.py`
- `tests/unit/application/test_decision_engine.py`
- `tests/unit/application/test_game_loop.py`
- `tests/integration/test_level_workflow.py`

**Files to modify**

- `src/word_madness_bot/domain/models.py`
- `src/word_madness_bot/domain/states.py`
- production ports only when orchestration exposes a documented ambiguity;

**Tests required**

- action selection for every game state;
- full level workflow with fake Android, vision, and repository ports;
- no-level-data, no-letter-wheel, rejected-word, victory, and unknown-state
  behavior;
- bounded polling, cancellation, and retry ownership;
- assertions that the engine never calls OCR implementations directly.

**Independent merge criteria**

The engine completes deterministic workflows with fakes, is not yet the default
entry point, and leaves the prototype runtime untouched.

---

### Milestone 9 — Advertisement Handling and Recovery Policies

**Goal**

Implement advertisement detection/dismissal orchestration and cross-cutting
recovery for device disconnects, screenshot failures, vision misses, and
missing level data.

**Files to create**

- `src/word_madness_bot/gameplay/ads.py`
- `src/word_madness_bot/application/recovery.py`
- `tests/unit/gameplay/test_ads.py`
- `tests/unit/application/test_recovery.py`
- `tests/integration/test_ad_recovery_workflow.py`

**Files to modify**

- `src/word_madness_bot/application/decision_engine.py`
- `src/word_madness_bot/application/game_loop.py`
- `src/word_madness_bot/domain/errors.py`
- `src/word_madness_bot/domain/states.py`

**Tests required**

- known ad types, close controls, Android Back fallback, and timeout behavior;
- false-positive prevention and Unknown fallback;
- bounded retries with backoff and retry exhaustion;
- device reconnection and screenshot reacquisition;
- cancellation and unrecoverable-error propagation;
- proof that lower layers report failures rather than making gameplay choices.

**Independent merge criteria**

Recovery and ad workflows pass with fakes, remain bounded, and do not become the
default executable until cutover.

---

### Milestone 10 — Composition Root, CLI, and Production Runtime

**Goal**

Wire configuration, logging, adapters, repositories, vision, and application
services in one composition root. Provide a non-interactive, testable CLI and
package entry point.

**Files to create**

- `src/word_madness_bot/bootstrap.py`
- `src/word_madness_bot/cli.py`
- `src/word_madness_bot/__main__.py`
- `tests/unit/test_bootstrap.py`
- `tests/unit/test_cli.py`
- `tests/integration/test_application_startup.py`

**Files to modify**

- `src/word_madness_bot/config/settings.py`
- `src/word_madness_bot/config/logging.py`
- `pyproject.toml` to expose the `word-madness-bot` console script;
- `README.md` with production install, configuration, and run instructions;

**Tests required**

- dependency wiring with fake factories;
- CLI help, version, invalid configuration, graceful shutdown, and exit codes;
- startup without import-time file or device I/O;
- packaged console-script smoke test;
- end-to-end dry-run workflow using only fakes and fixtures.

**Independent merge criteria**

The production CLI is installable and runnable in dry-run mode while the legacy
entry point remains available for comparison.

---

### Milestone 11 — Production Cutover and Prototype Retirement

**Goal**

Make the production package the only supported runtime after parity and
hardware acceptance. Remove prototype modules and obsolete launch mechanisms,
then verify a clean installation from source and wheel.

**Files to create**

- `tests/integration/test_production_smoke.py`
- `docs/OPERATIONS.md`
- `docs/TROUBLESHOOTING.md`

**Files to modify**

- `README.md`
- `INSTALL.bat` to install the package and supported extras, or remove it if
  cross-platform installation replaces it;
- `START BOT.bat` to invoke the package console script, or remove it if no
  longer supported;
- `docs/Architecture.md` to record concrete module-to-layer mappings;
- `docs/Ads.md`, `docs/Database.md`, `docs/Gameplay.md`, and `docs/Vision.md` to
  replace placeholder sections with verified operational behavior;
- `pyproject.toml` to remove temporary migration compatibility settings;

**Files to remove**

- `main.py`
- `config/`
- `core/`
- obsolete `tools/` modules not retained as supported developer utilities;
- `requirements.txt` if package metadata is the sole dependency source;
- any remaining committed runtime outputs.

**Tests required**

- clean source and wheel installation on supported Python versions;
- production CLI smoke test;
- full fake-backed level and ad workflow;
- opt-in real-device acceptance checklist covering discovery, resolution,
  screenshot, tap, swipe, Back, Home, level completion, and ad dismissal;
- repository scan proving no imports or references to removed prototype
  packages;
- package-data verification for levels and templates;
- Ruff, mypy, pytest, and dependency/security audit in CI.

**Independent merge criteria**

All production acceptance checks pass, the documented rollback point is the
previous release tag, no production import references the prototype, and a
clean checkout needs no untracked local assets to run supported workflows.

## 7. Milestone Dependency Order

```text
M0 Tooling and hygiene
└── M1 Foundation and contracts
    ├── M2 ADB and screenshots
    │   └── M3 Resolution geometry
    ├── M4 Vision
    │   └── M5 State detection
    └── M6 Level repository
        └── M7 Swipe generation
            └── M8 Decision engine and game loop
                └── M9 Ads and recovery
                    └── M10 Composition root and CLI
                        └── M11 Cutover and retirement
```

M2, M4, and M6 may be developed in parallel after M1. M3 may proceed once the
geometry value objects from M1 and screen metadata from M2 are stable. All
branches should be short-lived and rebased or updated onto the latest merged
dependency milestone before review.

## 8. Cross-Milestone Acceptance Matrix

| Concern | First established | Final acceptance |
|---|---:|---|
| Reproducible build and quality gates | M0 | Clean source and wheel installs |
| Typed replaceable contracts | M1 | No infrastructure leakage into domain/application |
| Android communication | M2 | Real-device smoke checklist passes |
| Resolution independence | M3 | Multiple resolution/aspect-ratio tests pass |
| Vision | M4 | Fixture suite is deterministic and input-free |
| Game state | M5 | Every documented state and Unknown are covered |
| Data-driven levels | M6 | Packaged JSON validates and missing data is typed |
| Swipe paths | M7 | Property tests prove bounded deterministic paths |
| Decision workflow | M8 | Fake-backed level completion passes |
| Ads and recovery | M9 | Failures are bounded, logged, and recoverable |
| Production runtime | M10 | CLI and dry-run startup pass from installed package |
| Legacy retirement | M11 | No legacy imports/files remain in supported runtime |

## 9. Risks and Controls

- **Documentation gaps:** Ads, Database, Gameplay, and Vision documents are
  outlines. Resolve behavioral ambiguity through explicit contracts and tests;
  update those documents only when behavior is implemented and verified.
- **Prototype coupling:** Never import prototype modules into production. Use
  black-box observations and fixtures when preserving behavior.
- **Hardware dependence:** Mock process and device boundaries by default; keep
  real-device tests opt-in and separately marked.
- **Coordinate assumptions:** Normalize every point and crop and test multiple
  resolutions before gameplay integration.
- **OCR instability:** Put OCR behind a port, record confidence, and preserve an
  Unknown/failure path instead of treating guesses as facts.
- **Unsafe retries:** Retry idempotent reads and captures only; do not silently
  repeat taps, swipes, or key events.
- **Unbounded automation:** Every loop, retry, and wait needs a timeout,
  cancellation path, and observable failure.
- **Data quality:** Validate level JSON at load time and keep invalid data from
  entering domain workflows.
- **Repository contamination:** CI should reject tracked bytecode, logs,
  screenshots, local environments, and generated debug artifacts.

## 10. Definition of Migration Complete

The migration is complete only when:

- the production package is installable from a clean checkout and built wheel;
- all documented layers have explicit, tested boundaries;
- the full fake-backed workflow passes without a device;
- the opt-in hardware acceptance checklist passes on at least one supported
  Android device and records resolution-independent behavior;
- Ruff, mypy, pytest, and CI pass with no ignored failures;
- runtime logs contain structured context and no import creates files;
- game knowledge is packaged data rather than source-code constants;
- no supported entry point imports or references `core/` or `config/`;
- generated runtime artifacts are not tracked;
- the prototype has been removed only after production parity and rollback
  documentation are complete.
