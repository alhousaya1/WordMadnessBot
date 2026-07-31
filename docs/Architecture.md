# Architecture

## Overview

The supported runtime is the installable `word_madness_bot` package. It follows dependency inversion: domain values have no infrastructure dependencies, application services depend on ports, and the composition root selects concrete adapters.

## Concrete layer mapping

| Layer | Production modules | Responsibility |
|---|---|---|
| Entry and composition | `cli.py`, `__main__.py`, `bootstrap.py` | configuration loading, logging initialization, dependency wiring, lifecycle and exit codes |
| Configuration | `config/settings.py`, `config/logging.py` | immutable environment settings and structured JSON events |
| Domain | `domain/` | typed errors, geometry, device/game models and states |
| Application | `application/` | ports, decisions, bounded level workflow, and recovery ownership |
| Android infrastructure | `infrastructure/adb/` | discovery, selection, shell, screenshots and input execution |
| Level infrastructure | `infrastructure/levels/` | validated packaged JSON repository |
| Vision | `vision/` | preprocessing, templates, circle/letter extraction, OCR abstraction and classification |
| Gameplay policies | `gameplay/` | geometry, stable-state detection, swipe planning and advertisement policy |
| Resources | `resources/` | packaged level and template data |

## Communication rules

- Vision returns observations and never executes Android input.
- Swipe planning returns normalized paths and never imports ADB.
- Repositories return domain models and never process screenshots.
- Infrastructure reports typed failures upward; application recovery remains bounded.
- Mutating ADB events are not automatically retried.
- Imports perform no device or filesystem writes.

## Runtime flow

The CLI loads `Settings`, initializes structured logging, and calls the composition root. The root wires `AdbClient`, `JsonLevelRepository`, `SwipePathPlanner`, `DecisionEngine`, `GameLoop`, `AdvertisementPolicy`, and `RecoveryStrategy`. Dry-run startup validates this graph without device I/O; normal startup selects and verifies one online device. Shutdown is explicit and idempotent.

## Replaceability

Android, level, and vision boundaries are protocols or abstract contracts. Tests replace device and storage boundaries with fakes, while production wiring selects subprocess ADB and packaged JSON implementations.
