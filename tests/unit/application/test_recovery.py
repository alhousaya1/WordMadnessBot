import pytest

from word_madness_bot.application.recovery import RecoveryStrategy, RetryPolicy, TimeoutPolicy
from word_madness_bot.domain.errors import (
    RecoveryExhaustedError,
    WorkflowCancelledError,
    WorkflowTimeoutError,
)


def test_transient_failure_retries_with_backoff() -> None:
    calls = 0
    delays: list[float] = []

    def operation() -> str:
        nonlocal calls
        calls += 1
        if calls < 3:
            raise OSError("temporary")
        return "ok"

    strategy = RecoveryStrategy(
        RetryPolicy(3, 0.1, 2), TimeoutPolicy(5), sleeper=delays.append, clock=lambda: 0
    )
    assert strategy.execute(operation, recoverable=(OSError,)) == "ok"
    assert delays == [0.1, 0.2]


def test_permanent_error_is_not_retried() -> None:
    strategy = RecoveryStrategy(
        RetryPolicy(), TimeoutPolicy(), sleeper=lambda _: None, clock=lambda: 0
    )
    with pytest.raises(ValueError):
        strategy.execute(lambda: (_ for _ in ()).throw(ValueError()), recoverable=(OSError,))


def test_exhaustion_cancellation_and_timeout_are_typed() -> None:
    strategy = RecoveryStrategy(
        RetryPolicy(2, 0), TimeoutPolicy(1), sleeper=lambda _: None, clock=lambda: 0
    )
    with pytest.raises(RecoveryExhaustedError):
        strategy.execute(lambda: (_ for _ in ()).throw(OSError()), recoverable=(OSError,))
    with pytest.raises(WorkflowCancelledError):
        strategy.execute(lambda: 1, recoverable=(OSError,), cancelled=lambda: True)
    timed = RecoveryStrategy(RetryPolicy(), TimeoutPolicy(1), clock=iter([0, 2]).__next__)
    with pytest.raises(WorkflowTimeoutError):
        timed.execute(lambda: 1, recoverable=(OSError,))
