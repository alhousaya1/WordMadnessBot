# Error Recovery

## Ownership

Lower layers report failures through typed results or exceptions. The Milestone 9 Decision
Engine owns bounded orchestration recovery but performs no OCR, image processing, database
parsing, swipe planning, advertisement heuristics, or ADB execution.

## Retry Policy

Recovery counters are maintained independently for unknown state, failed level reading,
missing level data, unavailable wheel letters, failed word command, and failed
verification. `decision_max_retries` is the number of retry decisions returned before the
next identical failure escalates. Every retry uses `decision_retry_delay_seconds`; the
future command executor owns waiting and fresh observation acquisition.

Successful level preparation clears resolved recovery counters. Successful word
verification clears the word-command failure counter. Counters may also be explicitly
reset after an external recovery event.

## Failure Outcomes

- OCR or level-reading failure: bounded retry, then `EscalateDecision`.
- Missing JSON level entry: bounded retry, then escalation; no words are invented.
- Missing wheel letters: bounded retry, then escalation.
- Unknown screen state: bounded retry, then escalation.
- Failed word execution: the pending word is cleared but not marked submitted, allowing a
  bounded retry of that word.
- Stale verification observation: verification fails without changing progress.
- Advertisement interruption: all actions and verification remain owned by
  `AdvertisementPolicy`; the Decision Engine only forwards its typed action.

Escalation is a typed command intent for a future higher-level runtime. Milestone 9 does
not stop the process, sleep, reconnect devices, or execute recovery input directly.
