# Ads

## 1. Overview

Advertisement handling is a standalone policy, not the gameplay state machine. It
consumes typed `StateObservation` values and Vision evidence already attached to those
observations. It performs no OCR, screenshot analysis, ADB calls, taps, key events, or
other input. It returns one typed action for a higher layer to execute.

## 2. Ad Types

Milestone 8 supports:

- Ads with exactly one confident close control at a Vision-provided normalized location.
- Ads without a close control after the configured initial wait, when the configured Back
  key fallback is enabled.

Multiple close controls, weak close-control evidence, controls without normalized
locations, unknown State observations, and ads with no enabled dismissal mechanism are
ambiguous or unsupported and are escalated without guessing.

## 3. Detection

The policy accepts only stabilized State output. `ADVERTISEMENT` establishes that an ad is
present. `ADVERTISEMENT_CLOSE_CONTROL` Vision evidence supplies confidence and an optional
normalized location. The policy never invokes a Vision implementation or OCR directly.

## 4. Dismissal

Possible typed results are `WaitAction`, `TapAction`, `KeyEventAction`, `ObserveAction`,
`CompleteAction`, and `EscalateAction`. A tap is returned only for one unique close-control
location meeting the confidence threshold. The Back key is returned only when its fallback
is configured and the initial close-control wait has elapsed.

Every wait, tap, or key action records the current observation revision. Until the caller
provides a context with a strictly newer observation revision, the policy returns only
`ObserveAction`. A known non-advertisement observation confirms completion. An `UNKNOWN`
verification observation escalates as ambiguous instead of assuming dismissal succeeded.

## 5. Timing and Retry

Configuration controls initial wait, retry delay, total timeout, maximum attempts,
minimum close-control confidence, Back-key fallback, and Back key code. Timeout and retry
limits produce distinct escalation reasons. The caller owns elapsed monotonic time and
observation revision updates; the pure policy owns no clock, sleeps, or device state.
