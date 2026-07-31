"""Unit tests for deterministic, safety-first game-state classification."""

from datetime import UTC, datetime

import pytest

from word_madness_bot.config import Settings
from word_madness_bot.domain.enums import GameState, StateReasonCode, VisionEvidenceKind
from word_madness_bot.domain.models import CapturedFrame, ScreenGeometry, VisionEvidence
from word_madness_bot.state.classifier import StateClassifier
from word_madness_bot.state.evidence_collector import EvidenceCollector


class StubVision:
    """Vision evidence provider with no OCR API exposed to the State layer."""

    def collect_evidence(self, frame: CapturedFrame) -> tuple[VisionEvidence, ...]:
        """Return intentionally unordered evidence."""

        return (
            VisionEvidence(VisionEvidenceKind.LETTER_WHEEL, 0.7),
            VisionEvidence(VisionEvidenceKind.HOME_INDICATOR, 0.8),
            VisionEvidence(VisionEvidenceKind.LETTER_WHEEL, 0.9),
        )


def _evidence(kind: VisionEvidenceKind | str, confidence: float) -> VisionEvidence:
    return VisionEvidence(kind=str(kind), confidence=confidence)


@pytest.mark.parametrize(
    ("kind", "expected_state"),
    [
        (VisionEvidenceKind.HOME_INDICATOR, GameState.HOME),
        (VisionEvidenceKind.PLAYING_BOARD, GameState.PLAYING),
        (VisionEvidenceKind.LETTER_WHEEL, GameState.PLAYING),
        (VisionEvidenceKind.VICTORY_BANNER, GameState.VICTORY),
        (VisionEvidenceKind.ADVERTISEMENT_INDICATOR, GameState.ADVERTISEMENT),
    ],
)
def test_recognized_strong_evidence_classifies_state(
    kind: VisionEvidenceKind,
    expected_state: GameState,
) -> None:
    """Each documented state maps deterministically from strong Vision evidence."""

    result = StateClassifier().classify((_evidence(kind, 0.9),))

    assert result.state is expected_state
    assert result.confidence == 0.9
    assert result.reason_codes == (StateReasonCode.CLASSIFIED,)


def test_empty_and_unrecognized_evidence_return_unknown() -> None:
    """Missing or unsupported Vision evidence never produces a guessed state."""

    classifier = StateClassifier()

    empty = classifier.classify(())
    unsupported = classifier.classify((_evidence("future_signal", 1.0),))

    assert empty.state is GameState.UNKNOWN
    assert empty.reason_codes == (StateReasonCode.NO_EVIDENCE,)
    assert unsupported.state is GameState.UNKNOWN
    assert unsupported.reason_codes == (StateReasonCode.NO_RECOGNIZED_EVIDENCE,)


def test_weak_evidence_returns_unknown() -> None:
    """Evidence below policy threshold is explicitly marked weak."""

    result = StateClassifier(minimum_confidence=0.7).classify(
        (_evidence(VisionEvidenceKind.PLAYING_BOARD, 0.69),)
    )

    assert result.state is GameState.UNKNOWN
    assert result.reason_codes == (StateReasonCode.WEAK_EVIDENCE,)


def test_conflicting_strong_evidence_returns_unknown() -> None:
    """Simultaneous evidence for different known states is never resolved by guessing."""

    result = StateClassifier().classify(
        (
            _evidence(VisionEvidenceKind.HOME_INDICATOR, 0.91),
            _evidence(VisionEvidenceKind.ADVERTISEMENT_INDICATOR, 0.87),
        )
    )

    assert result.state is GameState.UNKNOWN
    assert result.reason_codes == (StateReasonCode.CONFLICTING_EVIDENCE,)


def test_close_scores_inside_conflict_margin_return_unknown() -> None:
    """Near-threshold ambiguity is treated as conflict even if one score is slightly lower."""

    result = StateClassifier(minimum_confidence=0.65, conflict_margin=0.1).classify(
        (
            _evidence(VisionEvidenceKind.VICTORY_BANNER, 0.70),
            _evidence(VisionEvidenceKind.PLAYING_BOARD, 0.64),
        )
    )

    assert result.state is GameState.UNKNOWN
    assert result.reason_codes == (StateReasonCode.CONFLICTING_EVIDENCE,)


def test_evidence_order_does_not_change_result_or_output_order() -> None:
    """Classification and retained evidence are deterministic across input permutations."""

    classifier = StateClassifier()
    first = _evidence(VisionEvidenceKind.LEVEL_NUMBER, 0.75)
    second = _evidence(VisionEvidenceKind.LETTER_WHEEL, 0.92)

    forward = classifier.classify((first, second))
    reverse = classifier.classify((second, first))

    assert forward == reverse
    assert forward.state is GameState.PLAYING


def test_collector_uses_only_provider_and_orders_evidence() -> None:
    """State collection is deterministic and requires only the narrow Vision contract."""

    frame = CapturedFrame(
        data=b"encoded",
        geometry=ScreenGeometry(1, 1, 320),
        captured_at=datetime.now(UTC),
    )

    evidence = EvidenceCollector(StubVision()).collect(frame)

    assert [(item.kind, item.confidence) for item in evidence] == [
        (VisionEvidenceKind.HOME_INDICATOR, 0.8),
        (VisionEvidenceKind.LETTER_WHEEL, 0.9),
        (VisionEvidenceKind.LETTER_WHEEL, 0.7),
    ]


def test_classifier_policy_is_constructed_from_settings() -> None:
    """Validated runtime settings control classification thresholds."""

    classifier = StateClassifier.from_settings(
        Settings(state_minimum_confidence=0.95, state_conflict_margin=0.05)
    )

    result = classifier.classify((_evidence(VisionEvidenceKind.HOME_INDICATOR, 0.9),))

    assert result.state is GameState.UNKNOWN
    assert result.reason_codes == (StateReasonCode.WEAK_EVIDENCE,)
