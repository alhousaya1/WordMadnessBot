"""Typed advertisement actions returned for execution by higher layers."""

from dataclasses import dataclass
from enum import StrEnum
from typing import TypeAlias

from word_madness_bot.domain.models import AdvertisementContext, NormalizedPoint


class AdvertisementEscalationReason(StrEnum):
    """Machine-readable reasons why safe automatic dismissal stopped."""

    AMBIGUOUS = "ambiguous_advertisement"
    UNSUPPORTED = "unsupported_advertisement"
    TIMEOUT = "advertisement_timeout"
    RETRY_LIMIT = "advertisement_retry_limit"


@dataclass(frozen=True, slots=True)
class WaitAction:
    """Wait without guessing where to interact, then obtain a new observation."""

    delay_seconds: float

    def __post_init__(self) -> None:
        if self.delay_seconds <= 0.0:
            raise ValueError("advertisement wait delay must be positive")


@dataclass(frozen=True, slots=True)
class TapAction:
    """Request a tap at a Vision-provided normalized close-control location."""

    point: NormalizedPoint


@dataclass(frozen=True, slots=True)
class KeyEventAction:
    """Request a configured key event without executing it directly."""

    key_code: int

    def __post_init__(self) -> None:
        if self.key_code < 0:
            raise ValueError("key code cannot be negative")


@dataclass(frozen=True, slots=True)
class ObserveAction:
    """Require a newer State observation before another policy action."""

    after_revision: int


@dataclass(frozen=True, slots=True)
class CompleteAction:
    """Report that a new known State observation confirms the ad has exited."""

    observed_state: str


@dataclass(frozen=True, slots=True)
class EscalateAction:
    """Safely stop automatic dismissal and report a recovery reason upward."""

    reason: AdvertisementEscalationReason
    detail: str


AdvertisementAction: TypeAlias = (
    WaitAction | TapAction | KeyEventAction | ObserveAction | CompleteAction | EscalateAction
)


@dataclass(frozen=True, slots=True)
class AdvertisementDecision:
    """One typed policy action and the context required for the next evaluation."""

    action: AdvertisementAction
    context: AdvertisementContext
