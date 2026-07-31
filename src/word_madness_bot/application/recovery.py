"""Bounded retry, timeout, and recovery policy for application workflows."""

from __future__ import annotations

import time
from collections.abc import Callable
from dataclasses import dataclass
from enum import StrEnum
from typing import TypeVar

from word_madness_bot.domain.errors import (
    RecoveryExhaustedError,
    WorkflowCancelledError,
    WorkflowTimeoutError,
)

T = TypeVar("T")


class RecoveryAction(StrEnum):
    RETRY = "retry"
    RECONNECT_DEVICE = "reconnect_device"
    REACQUIRE_SCREENSHOT = "reacquire_screenshot"
    ABORT = "abort"


@dataclass(frozen=True, slots=True)
class RetryPolicy:
    max_attempts: int = 3
    initial_delay_seconds: float = 0.1
    backoff_multiplier: float = 2.0

    def __post_init__(self) -> None:
        if self.max_attempts <= 0 or self.initial_delay_seconds < 0 or self.backoff_multiplier < 1:
            raise ValueError("Invalid retry policy")


@dataclass(frozen=True, slots=True)
class TimeoutPolicy:
    timeout_seconds: float = 10.0

    def __post_init__(self) -> None:
        if self.timeout_seconds <= 0:
            raise ValueError("timeout_seconds must be positive")


class RecoveryStrategy:
    """Retry only declared recoverable failures within strict bounds."""

    def __init__(
        self,
        retry: RetryPolicy,
        timeout: TimeoutPolicy,
        *,
        sleeper: Callable[[float], None] = time.sleep,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        self.retry, self.timeout, self.sleeper, self.clock = retry, timeout, sleeper, clock

    def execute(
        self,
        operation: Callable[[], T],
        *,
        recoverable: tuple[type[Exception], ...],
        cancelled: Callable[[], bool] = lambda: False,
        on_retry: Callable[[Exception, int], None] | None = None,
    ) -> T:
        started = self.clock()
        last_error: Exception | None = None
        for attempt in range(1, self.retry.max_attempts + 1):
            if cancelled():
                raise WorkflowCancelledError("Recovery was cancelled")
            if self.clock() - started >= self.timeout.timeout_seconds:
                raise WorkflowTimeoutError("Recovery timeout expired")
            try:
                return operation()
            except recoverable as error:
                last_error = error
                if attempt == self.retry.max_attempts:
                    break
                if on_retry is not None:
                    on_retry(error, attempt)
                self.sleeper(
                    self.retry.initial_delay_seconds
                    * self.retry.backoff_multiplier ** (attempt - 1)
                )
        raise RecoveryExhaustedError(self.retry.max_attempts) from last_error
