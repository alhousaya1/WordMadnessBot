"""Typed decisions, commands, and verification outcomes for orchestration."""

from dataclasses import dataclass
from typing import TypeAlias

from word_madness_bot.domain.enums import RecoveryFailure
from word_madness_bot.domain.models import SwipePath
from word_madness_bot.gameplay.actions import AdvertisementAction


@dataclass(frozen=True, slots=True)
class ObserveDecision:
    """Decide to request another observation without device assumptions."""

    reason: str


@dataclass(frozen=True, slots=True)
class SubmitWordDecision:
    """Decide to submit one not-yet-submitted level word."""

    word: str
    path: SwipePath


@dataclass(frozen=True, slots=True)
class AdvertisementActionDecision:
    """Forward exactly one action selected by AdvertisementPolicy."""

    action: AdvertisementAction


@dataclass(frozen=True, slots=True)
class RetryDecision:
    """Decide to wait before obtaining fresh evidence for a bounded retry."""

    failure: RecoveryFailure
    delay_seconds: float
    attempt: int


@dataclass(frozen=True, slots=True)
class EscalateDecision:
    """Decide that bounded automatic recovery has been exhausted."""

    failure: RecoveryFailure
    detail: str


EngineDecision: TypeAlias = (
    ObserveDecision
    | SubmitWordDecision
    | AdvertisementActionDecision
    | RetryDecision
    | EscalateDecision
)


@dataclass(frozen=True, slots=True)
class EngineCommand:
    """A numbered command created from a decision and tied to an observation revision."""

    identifier: int
    observation_revision: int
    decision: EngineDecision

    def __post_init__(self) -> None:
        if self.identifier <= 0 or self.observation_revision < 0:
            raise ValueError("command identifier and observation revision are invalid")


@dataclass(frozen=True, slots=True)
class CommandOutcome:
    """External execution result used only by the independent verification step."""

    command_identifier: int
    succeeded: bool
    detail: str = ""
