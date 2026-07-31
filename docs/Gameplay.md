# Gameplay

## 1. Overview

Milestone 6 defines only logical game-state classification. The State layer consumes
confidence-bearing Vision evidence and emits typed `StateObservation` values. It is
independent of gameplay decisions, ADB input, the level database, and swipe planning. It
never invokes OCR; OCR remains behind Vision interfaces.

## 2. Game States

The supported states are `HOME`, `PLAYING`, `VICTORY`, `ADVERTISEMENT`, and `UNKNOWN`.
Recognized Vision evidence kinds map deterministically to the first four states. Empty,
unrecognized, weak, ambiguous, or conflicting evidence maps to `UNKNOWN` rather than a
best-effort guess.

## 3. State Machine

State-machine decisions are deferred to a later milestone. Milestone 6 provides temporal
stabilization: a known state must repeat for the configured number of consecutive frames
before it is exposed. During debounce the output is `UNKNOWN`. An unknown observation is
returned immediately and resets temporal history.

## 4. Level Flow

Milestone 9 provides an explicit finite-state machine with these internal states:
`OBSERVING`, `SOLVING_LEVEL`, `VERIFYING_WORD`, `HANDLING_ADVERTISEMENT`, `RECOVERING`,
and `STOPPED`. Every allowed transition is declared in one transition table; undeclared
transitions fail immediately.

The runtime flow separates four public steps:

1. Observation classifies Vision evidence only through `GameStateDetector` and packages
   already-produced level and wheel results.
2. Decision uses the State result and orchestrates existing Database, Swipe, and
   Advertisement Policy contracts.
3. Command creation numbers a typed command and ties it to the observation revision that
   caused it. It never executes the command.
4. Verification accepts an external command outcome and requires a strictly newer
   observation before progress can change.

`PLAYING` requires a valid level reading, wheel letters, and an exact repository entry.
Words are considered submitted only after successful command verification. Submitted
words are retained for the active level and cannot be selected again. A different level
number resets progress, allowing continuous solving across consecutive levels.

## 5. Word Solving

Milestone 7 implements only pure word-to-path planning. The Swipe layer accepts a target
word and `SwipeLetter` values containing detected characters and normalized screen
coordinates. It has no dependency on gameplay, ADB, Vision implementations, the level
database implementation, or State classification.

Each occurrence in a target word consumes one distinct matching wheel letter. Duplicate
wheel letters are sorted by normalized `y` and then `x`, making repeated-letter mapping
independent of detector output order. A word requiring more copies of a letter than the
wheel provides is rejected before path creation.

## 6. Input Automation

The State and Swipe layers perform no taps, swipes, key events, or other device input.
Swipe output is an immutable `SwipePath` made exclusively of `NormalizedPoint` values.
Interpolation adds a configurable number of points between letter anchors. Configurable
smoothstep blending changes movement pacing without moving or omitting any required
letter coordinate.

Every completed path is validated before it is returned. Validation rejects stationary
segments, non-finite or out-of-bounds coordinates, zero-distance paths, and segment steps
larger than the configured normalized maximum. Duration is deterministic from normalized
target length and configured milliseconds per letter. The production ADB input adapter
reads current device geometry, scales every point, and traces the complete path with
ordered Android motion events.

The autonomous application loop executes exactly one `EngineCommand`, captures a strictly
newer observation, and invokes Decision Engine verification before asking for another
decision. Failed input is also followed by a verification capture when the device remains
available. Advertisement waits, taps, Back keys, observation requests, completion, and
escalation remain typed policy outputs until this execution boundary.

## 7. Progress Tracking

Every observation contains a confidence and one or more machine-readable reason codes.
Classification reasons distinguish successful classification, absent evidence,
unrecognized evidence, weak evidence, and conflicts. Stabilization adds explicit
`debouncing`, `stabilized`, or `unknown_input` reasons. Structured debug logs contain the
state, confidence, reason codes, candidate count, and evidence kinds.

## 8. Advertisement Policy Boundary

Advertisement dismissal is a typed policy and remains separate from the gameplay state
machine. It consumes stabilized State observations, selects at most one safe action,
and requires a new observation after every wait or dismissal attempt. It cannot execute
the action or infer success without verification. Unsupported and ambiguous cases are
escalated through the Decision Engine without duplicating advertisement logic.
