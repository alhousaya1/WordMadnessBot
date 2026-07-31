"""Release-level advertisement recovery contract smoke test."""

from word_madness_bot.domain.enums import GameState, StateReasonCode, VisionEvidenceKind
from word_madness_bot.domain.models import (
    AdvertisementContext,
    NormalizedPoint,
    StateObservation,
    VisionEvidence,
)
from word_madness_bot.gameplay.actions import TapAction
from word_madness_bot.gameplay.ad_policy import AdvertisementPolicy


def test_confident_ad_control_produces_typed_normalized_action_only() -> None:
    evidence = VisionEvidence(
        VisionEvidenceKind.ADVERTISEMENT_CLOSE_CONTROL,
        0.95,
        normalized_location=NormalizedPoint(0.9, 0.1),
    )
    state = StateObservation(
        GameState.ADVERTISEMENT,
        0.95,
        (evidence,),
        (StateReasonCode.STABILIZED,),
    )
    decision = AdvertisementPolicy().decide(state, AdvertisementContext(1))
    assert decision.action == TapAction(NormalizedPoint(0.9, 0.1))
