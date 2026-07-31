# Gameplay

## States and decisions

The stable states are Home, Playing, Victory, Advertisement, and Unknown. `StateDetector` combines classifier evidence with confidence thresholds and stability history. `DecisionEngine` maps only stable observations to typed actions; unstable or unknown observations wait.

## Level workflow

`GameLoop` loads a typed level through `LevelRepository`, plans each word through `SwipePathPlanner`, and submits completed paths through `AndroidPort`. Unmappable words are recorded as rejected. Polling has a hard limit and cancellation path.

## Swipe planning

Detected letters use normalized coordinates. Words map deterministically to unused wheel positions, including repeated letters. Interpolation bounds segment length and screen conversion clamps points to device pixels. Planning performs no I/O.

## Advertisement and recovery

Advertisement handling is a separate bounded policy. Cross-cutting retry and timeout behavior is owned by `RecoveryStrategy`; lower layers report failures instead of making gameplay choices.

## Current runtime boundary

Production startup composes all implemented services and validates device connectivity. Automated solving and continuous level progression are not inferred beyond the bounded workflows implemented and tested here.
