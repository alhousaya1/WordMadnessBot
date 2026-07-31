"""Unit tests for the safety-first advertisement policy."""

from dataclasses import replace

import pytest

from word_madness_bot.config import Settings
from word_madness_bot.domain.enums import GameState, StateReasonCode, VisionEvidenceKind
from word_madness_bot.domain.models import (
    AdvertisementContext,
    NormalizedPoint,
    StateObservation,
    VisionEvidence,
)
from word_madness_bot.gameplay.actions import (
    AdvertisementEscalationReason,
    CompleteAction,
    EscalateAction,
    KeyEventAction,
    ObserveAction,
    TapAction,
    WaitAction,
)
from word_madness_bot.gameplay.ad_policy import AdvertisementPolicy


def _observation(
    state: GameState = GameState.ADVERTISEMENT,
    evidence: tuple[VisionEvidence, ...] = (),
) -> StateObservation:
    return StateObservation(
        state=state,
        confidence=0.9,
        evidence=evidence,
        reason_codes=(StateReasonCode.STABILIZED,),
    )


def _close(x: float, y: float, confidence: float = 0.9) -> VisionEvidence:
    return VisionEvidence(
        VisionEvidenceKind.ADVERTISEMENT_CLOSE_CONTROL,
        confidence,
        normalized_location=NormalizedPoint(x, y),
    )


def test_single_confident_close_control_returns_normalized_tap() -> None:
    """The policy returns, but never executes, a Vision-located close tap."""

    decision = AdvertisementPolicy().decide(
        _observation(evidence=(_close(0.9, 0.1),)),
        AdvertisementContext(observation_revision=4, elapsed_seconds=2.0),
    )

    assert decision.action == TapAction(NormalizedPoint(0.9, 0.1))
    assert decision.context.attempt_count == 1
    assert decision.context.last_action_revision == 4


def test_same_observation_after_action_can_only_request_observation() -> None:
    """A dismissal action cannot repeat until State supplies a newer observation."""

    policy = AdvertisementPolicy()
    first = policy.decide(
        _observation(evidence=(_close(0.9, 0.1),)),
        AdvertisementContext(observation_revision=7),
    )

    repeated = policy.decide(_observation(evidence=(_close(0.9, 0.1),)), first.context)

    assert repeated.action == ObserveAction(after_revision=7)
    assert repeated.context == first.context


def test_new_non_ad_observation_verifies_completion() -> None:
    """Only a newer known non-advertisement State observation confirms dismissal."""

    context = AdvertisementContext(
        observation_revision=11,
        attempt_count=1,
        elapsed_seconds=3.0,
        last_action_revision=10,
    )

    decision = AdvertisementPolicy().decide(_observation(GameState.PLAYING), context)

    assert decision.action == CompleteAction(GameState.PLAYING.value)


def test_initial_ad_without_close_control_returns_bounded_wait() -> None:
    """The policy waits for UI controls rather than blindly tapping."""

    policy = AdvertisementPolicy(initial_wait_seconds=3.0, retry_delay_seconds=1.0)

    decision = policy.decide(
        _observation(),
        AdvertisementContext(observation_revision=1, elapsed_seconds=2.5),
    )

    assert decision.action == WaitAction(0.5)
    assert decision.context.last_action_revision == 1


def test_back_fallback_is_configurable_and_typed() -> None:
    """Elapsed ads without controls may request only the configured key action."""

    policy = AdvertisementPolicy(initial_wait_seconds=2.0, back_key_code=4)

    decision = policy.decide(
        _observation(),
        AdvertisementContext(observation_revision=2, elapsed_seconds=2.0),
    )

    assert decision.action == KeyEventAction(4)


@pytest.mark.parametrize(
    ("observation", "reason"),
    [
        (_observation(GameState.UNKNOWN), AdvertisementEscalationReason.AMBIGUOUS),
        (
            _observation(evidence=(_close(0.2, 0.2), _close(0.8, 0.2))),
            AdvertisementEscalationReason.AMBIGUOUS,
        ),
        (
            _observation(evidence=(_close(0.9, 0.1, confidence=0.2),)),
            AdvertisementEscalationReason.AMBIGUOUS,
        ),
    ],
)
def test_ambiguous_observations_escalate_without_guessing(
    observation: StateObservation,
    reason: AdvertisementEscalationReason,
) -> None:
    """Unknown, multiple, and weak control evidence produce safe escalation."""

    decision = AdvertisementPolicy().decide(
        observation,
        AdvertisementContext(observation_revision=1),
    )

    assert isinstance(decision.action, EscalateAction)
    assert decision.action.reason is reason


def test_close_evidence_without_location_escalates() -> None:
    """The policy never invents a coordinate for incomplete Vision evidence."""

    evidence = VisionEvidence(VisionEvidenceKind.ADVERTISEMENT_CLOSE_CONTROL, 0.95)

    decision = AdvertisementPolicy().decide(
        _observation(evidence=(evidence,)),
        AdvertisementContext(observation_revision=1),
    )

    assert isinstance(decision.action, EscalateAction)
    assert decision.action.reason is AdvertisementEscalationReason.AMBIGUOUS


def test_timeout_and_retry_limit_have_distinct_recovery_reasons() -> None:
    """Timing and retry exhaustion are distinguishable to the future recovery owner."""

    policy = AdvertisementPolicy(timeout_seconds=10.0, maximum_attempts=2)
    timeout = policy.decide(
        _observation(),
        AdvertisementContext(observation_revision=3, elapsed_seconds=10.0),
    )
    retry = policy.decide(
        _observation(),
        AdvertisementContext(observation_revision=3, attempt_count=2),
    )

    assert isinstance(timeout.action, EscalateAction)
    assert timeout.action.reason is AdvertisementEscalationReason.TIMEOUT
    assert isinstance(retry.action, EscalateAction)
    assert retry.action.reason is AdvertisementEscalationReason.RETRY_LIMIT


def test_disabled_back_fallback_escalates_unsupported_ad() -> None:
    """An unsupported ad is escalated instead of receiving a guessed interaction."""

    decision = AdvertisementPolicy(
        initial_wait_seconds=0.0,
        allow_back_fallback=False,
    ).decide(
        _observation(),
        AdvertisementContext(observation_revision=1),
    )

    assert isinstance(decision.action, EscalateAction)
    assert decision.action.reason is AdvertisementEscalationReason.UNSUPPORTED


def test_policy_configuration_comes_from_settings() -> None:
    """Runtime settings control advertisement timing and fallback behavior."""

    policy = AdvertisementPolicy.from_settings(
        Settings(ad_initial_wait_seconds=0.0, ad_allow_back_fallback=True, ad_back_key_code=9)
    )

    decision = policy.decide(
        _observation(),
        AdvertisementContext(observation_revision=1),
    )

    assert decision.action == KeyEventAction(9)


def test_new_ad_observation_allows_next_bounded_attempt() -> None:
    """A strictly newer revision satisfies verification and permits one retry."""

    policy = AdvertisementPolicy()
    first = policy.decide(
        _observation(evidence=(_close(0.9, 0.1),)),
        AdvertisementContext(observation_revision=1),
    )
    newer_context = replace(first.context, observation_revision=2, elapsed_seconds=1.0)

    second = policy.decide(_observation(evidence=(_close(0.9, 0.1),)), newer_context)

    assert isinstance(second.action, TapAction)
    assert second.context.attempt_count == 2
    assert second.context.last_action_revision == 2
