"""Bounded retry and escalation decisions for documented recoverable failures."""

from word_madness_bot.config.settings import Settings
from word_madness_bot.domain.enums import RecoveryFailure
from word_madness_bot.gameplay.commands import EscalateDecision, RetryDecision


class RecoveryPolicy:
    """Count failures independently and escalate at the configured retry bound."""

    def __init__(self, maximum_retries: int = 3, retry_delay_seconds: float = 1.0) -> None:
        if maximum_retries <= 0 or retry_delay_seconds <= 0.0:
            raise ValueError("recovery limits must be positive")
        self._maximum_retries = maximum_retries
        self._retry_delay_seconds = retry_delay_seconds
        self._attempts: dict[RecoveryFailure, int] = {}

    @classmethod
    def from_settings(cls, settings: Settings) -> "RecoveryPolicy":
        """Build the bounded recovery policy from validated configuration."""

        return cls(settings.decision_max_retries, settings.decision_retry_delay_seconds)

    def decide(self, failure: RecoveryFailure, detail: str) -> RetryDecision | EscalateDecision:
        """Return a retry until the bound is reached, then return escalation."""

        attempt = self._attempts.get(failure, 0) + 1
        self._attempts[failure] = attempt
        if attempt > self._maximum_retries:
            return EscalateDecision(failure, detail)
        return RetryDecision(failure, self._retry_delay_seconds, attempt)

    def reset(self, failure: RecoveryFailure | None = None) -> None:
        """Clear one recovered failure counter or all counters."""

        if failure is None:
            self._attempts.clear()
        else:
            self._attempts.pop(failure, None)
