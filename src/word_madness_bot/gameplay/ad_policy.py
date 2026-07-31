"""Safety-first advertisement dismissal policy independent of orchestration."""

import logging

from word_madness_bot.config.settings import Settings
from word_madness_bot.domain.enums import GameState, VisionEvidenceKind
from word_madness_bot.domain.models import AdvertisementContext, NormalizedPoint, StateObservation
from word_madness_bot.gameplay.actions import (
    AdvertisementDecision,
    AdvertisementEscalationReason,
    CompleteAction,
    EscalateAction,
    KeyEventAction,
    ObserveAction,
    TapAction,
    WaitAction,
)

_LOGGER = logging.getLogger(__name__)


class AdvertisementPolicy:
    """Choose typed dismissal actions exclusively from State and Vision evidence."""

    def __init__(
        self,
        *,
        initial_wait_seconds: float = 3.0,
        retry_delay_seconds: float = 1.0,
        timeout_seconds: float = 30.0,
        maximum_attempts: int = 4,
        minimum_confidence: float = 0.75,
        allow_back_fallback: bool = True,
        back_key_code: int = 4,
    ) -> None:
        if initial_wait_seconds < 0.0:
            raise ValueError("initial wait cannot be negative")
        if retry_delay_seconds <= 0.0 or timeout_seconds <= 0.0:
            raise ValueError("advertisement timing values must be positive")
        if maximum_attempts <= 0:
            raise ValueError("maximum attempts must be positive")
        if not 0.0 <= minimum_confidence <= 1.0:
            raise ValueError("minimum confidence must be between zero and one")
        if back_key_code < 0:
            raise ValueError("back key code cannot be negative")
        self._initial_wait_seconds = initial_wait_seconds
        self._retry_delay_seconds = retry_delay_seconds
        self._timeout_seconds = timeout_seconds
        self._maximum_attempts = maximum_attempts
        self._minimum_confidence = minimum_confidence
        self._allow_back_fallback = allow_back_fallback
        self._back_key_code = back_key_code

    @classmethod
    def from_settings(cls, settings: Settings) -> "AdvertisementPolicy":
        """Construct advertisement timing and recovery policy from configuration."""

        return cls(
            initial_wait_seconds=settings.ad_initial_wait_seconds,
            retry_delay_seconds=settings.ad_retry_delay_seconds,
            timeout_seconds=settings.ad_timeout_seconds,
            maximum_attempts=settings.ad_max_attempts,
            minimum_confidence=settings.ad_minimum_confidence,
            allow_back_fallback=settings.ad_allow_back_fallback,
            back_key_code=settings.ad_back_key_code,
        )

    def decide(
        self,
        observation: StateObservation,
        context: AdvertisementContext,
    ) -> AdvertisementDecision:
        """Return one safe action and require a newer observation after each attempt."""

        if (
            context.last_action_revision is not None
            and context.observation_revision <= context.last_action_revision
        ):
            return self._decision(
                ObserveAction(after_revision=context.last_action_revision),
                context,
            )

        if observation.state is GameState.UNKNOWN:
            return self._escalate(
                AdvertisementEscalationReason.AMBIGUOUS,
                "state observation is unknown",
                context,
            )
        if observation.state is not GameState.ADVERTISEMENT:
            return self._decision(CompleteAction(observation.state.value), context)
        if context.elapsed_seconds >= self._timeout_seconds:
            return self._escalate(
                AdvertisementEscalationReason.TIMEOUT,
                "advertisement dismissal timed out",
                context,
            )
        if context.attempt_count >= self._maximum_attempts:
            return self._escalate(
                AdvertisementEscalationReason.RETRY_LIMIT,
                "advertisement dismissal retry limit reached",
                context,
            )

        close_evidence = tuple(
            evidence
            for evidence in observation.evidence
            if evidence.kind == VisionEvidenceKind.ADVERTISEMENT_CLOSE_CONTROL
        )
        supported_locations = tuple(
            evidence.normalized_location
            for evidence in close_evidence
            if evidence.confidence >= self._minimum_confidence
            and evidence.normalized_location is not None
        )
        unique_locations = self._unique_locations(supported_locations)
        if len(unique_locations) > 1:
            return self._escalate(
                AdvertisementEscalationReason.AMBIGUOUS,
                "multiple confident advertisement close controls were detected",
                context,
            )
        if len(unique_locations) == 1:
            return self._attempt(TapAction(unique_locations[0]), context)
        if close_evidence:
            return self._escalate(
                AdvertisementEscalationReason.AMBIGUOUS,
                "close-control evidence is weak or has no normalized location",
                context,
            )

        if context.elapsed_seconds < self._initial_wait_seconds:
            remaining = self._initial_wait_seconds - context.elapsed_seconds
            return self._attempt(
                WaitAction(min(self._retry_delay_seconds, remaining)),
                context,
            )
        if self._allow_back_fallback:
            return self._attempt(KeyEventAction(self._back_key_code), context)
        return self._escalate(
            AdvertisementEscalationReason.UNSUPPORTED,
            "no supported close control and back fallback is disabled",
            context,
        )

    def _attempt(
        self,
        action: WaitAction | TapAction | KeyEventAction,
        context: AdvertisementContext,
    ) -> AdvertisementDecision:
        next_context = AdvertisementContext(
            observation_revision=context.observation_revision,
            attempt_count=context.attempt_count + 1,
            elapsed_seconds=context.elapsed_seconds,
            last_action_revision=context.observation_revision,
        )
        return self._decision(action, next_context)

    def _escalate(
        self,
        reason: AdvertisementEscalationReason,
        detail: str,
        context: AdvertisementContext,
    ) -> AdvertisementDecision:
        return self._decision(EscalateAction(reason, detail), context)

    @staticmethod
    def _unique_locations(locations: tuple[NormalizedPoint, ...]) -> tuple[NormalizedPoint, ...]:
        return tuple(sorted(set(locations), key=lambda point: (point.y, point.x)))

    @staticmethod
    def _decision(
        action: WaitAction
        | TapAction
        | KeyEventAction
        | ObserveAction
        | CompleteAction
        | EscalateAction,
        context: AdvertisementContext,
    ) -> AdvertisementDecision:
        decision = AdvertisementDecision(action=action, context=context)
        _LOGGER.debug(
            "Selected advertisement policy action",
            extra={
                "event": "advertisement_action_selected",
                "action_type": type(action).__name__,
                "attempt_count": context.attempt_count,
                "observation_revision": context.observation_revision,
            },
        )
        return decision
