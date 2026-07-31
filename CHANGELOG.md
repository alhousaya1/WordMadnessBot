# Changelog

## Unreleased - Milestone 13

- Added serialized ADB command execution, bounded screenshot acquisition, absolute taps,
  normalized multi-point swipe tracing, and Android key-event execution.
- Connected the Decision Engine, advertisement and recovery policies, State Machine,
  Vision, Database, and Swipe Planner to the autonomous `run` lifecycle.
- Added mandatory fresh-observation verification after every runtime command.

## 0.1.0 - 2026-07-31

- Added the layered package architecture, typed domain contracts, strict JSON repository,
  resolution-independent Vision, deterministic State and Swipe layers, advertisement and
  Decision policies, production CLI/composition root, observability, diagnostics, tests,
  and release documentation.
- Removed the legacy proof-of-concept implementation and tracked runtime artifacts.
- Declared the current autonomous-input and dataset limitations for release review.
