"""Integration scenarios across typed State evidence and advertisement policy actions."""

from dataclasses import replace

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


def _state(
    state: GameState,
    evidence: tuple[VisionEvidence, ...] = (),
) -> StateObservation:
    return StateObservation(
        state=state,
        confidence=0.95,
        evidence=evidence,
        reason_codes=(StateReasonCode.STABILIZED,),
    )


def test_close_control_scenario_requires_observation_then_completes() -> None:
    """Supported close-control flow is tap, observe, then verified completion."""

    policy = AdvertisementPolicy.from_settings(Settings())
    close = VisionEvidence(
        VisionEvidenceKind.ADVERTISEMENT_CLOSE_CONTROL,
        0.95,
        normalized_location=NormalizedPoint(0.92, 0.08),
    )
    first = policy.decide(
        _state(GameState.ADVERTISEMENT, (close,)),
        AdvertisementContext(observation_revision=10),
    )
    blocked = policy.decide(_state(GameState.ADVERTISEMENT, (close,)), first.context)
    verified_context = replace(
        first.context,
        observation_revision=11,
        elapsed_seconds=1.0,
    )
    complete = policy.decide(_state(GameState.PLAYING), verified_context)

    assert first.action == TapAction(NormalizedPoint(0.92, 0.08))
    assert blocked.action == ObserveAction(after_revision=10)
    assert complete.action == CompleteAction(GameState.PLAYING.value)


def test_delayed_back_fallback_scenario_is_wait_observe_key_observe_complete() -> None:
    """Supported no-control flow remains bounded and verifies every returned action."""

    policy = AdvertisementPolicy.from_settings(
        Settings(ad_initial_wait_seconds=2.0, ad_retry_delay_seconds=1.0)
    )
    ad = _state(GameState.ADVERTISEMENT)
    first = policy.decide(ad, AdvertisementContext(observation_revision=1))
    blocked_after_wait = policy.decide(ad, first.context)
    after_wait = replace(first.context, observation_revision=2, elapsed_seconds=2.0)
    key = policy.decide(ad, after_wait)
    blocked_after_key = policy.decide(ad, key.context)
    after_key = replace(key.context, observation_revision=3, elapsed_seconds=3.0)
    complete = policy.decide(_state(GameState.HOME), after_key)

    assert first.action == WaitAction(1.0)
    assert blocked_after_wait.action == ObserveAction(after_revision=1)
    assert key.action == KeyEventAction(4)
    assert blocked_after_key.action == ObserveAction(after_revision=2)
    assert complete.action == CompleteAction(GameState.HOME.value)


def test_unsupported_and_ambiguous_scenarios_escalate_without_input_actions() -> None:
    """Unsafe ad variants produce typed escalation rather than guessed taps or keys."""

    policy = AdvertisementPolicy.from_settings(
        Settings(ad_initial_wait_seconds=0.0, ad_allow_back_fallback=False)
    )
    unsupported = policy.decide(
        _state(GameState.ADVERTISEMENT),
        AdvertisementContext(observation_revision=1),
    )
    ambiguous = policy.decide(
        _state(
            GameState.ADVERTISEMENT,
            (
                VisionEvidence(
                    VisionEvidenceKind.ADVERTISEMENT_CLOSE_CONTROL,
                    0.95,
                    normalized_location=NormalizedPoint(0.1, 0.1),
                ),
                VisionEvidence(
                    VisionEvidenceKind.ADVERTISEMENT_CLOSE_CONTROL,
                    0.96,
                    normalized_location=NormalizedPoint(0.9, 0.1),
                ),
            ),
        ),
        AdvertisementContext(observation_revision=2),
    )

    assert isinstance(unsupported.action, EscalateAction)
    assert unsupported.action.reason is AdvertisementEscalationReason.UNSUPPORTED
    assert isinstance(ambiguous.action, EscalateAction)
    assert ambiguous.action.reason is AdvertisementEscalationReason.AMBIGUOUS
