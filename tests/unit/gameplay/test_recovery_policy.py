"""Unit tests for bounded retry and recovery policy."""

from word_madness_bot.domain.enums import RecoveryFailure
from word_madness_bot.gameplay.commands import EscalateDecision, RetryDecision
from word_madness_bot.gameplay.recovery_policy import RecoveryPolicy


def test_retries_are_bounded_then_escalated() -> None:
    policy = RecoveryPolicy(maximum_retries=2, retry_delay_seconds=0.5)
    assert policy.decide(RecoveryFailure.LEVEL_READ_FAILED, "missing") == RetryDecision(
        RecoveryFailure.LEVEL_READ_FAILED, 0.5, 1
    )
    assert isinstance(policy.decide(RecoveryFailure.LEVEL_READ_FAILED, "missing"), RetryDecision)
    assert isinstance(policy.decide(RecoveryFailure.LEVEL_READ_FAILED, "missing"), EscalateDecision)


def test_failure_counters_are_independent_and_resettable() -> None:
    policy = RecoveryPolicy(maximum_retries=1)
    policy.decide(RecoveryFailure.UNKNOWN_STATE, "unknown")
    policy.reset(RecoveryFailure.UNKNOWN_STATE)
    assert isinstance(policy.decide(RecoveryFailure.UNKNOWN_STATE, "unknown"), RetryDecision)
    assert isinstance(policy.decide(RecoveryFailure.LEVEL_NOT_FOUND, "absent"), RetryDecision)
