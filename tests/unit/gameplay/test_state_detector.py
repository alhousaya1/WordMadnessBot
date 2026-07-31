"""Unit tests for game-state detection and stabilization."""

import pytest

from word_madness_bot.domain.states import GameState
from word_madness_bot.gameplay.state_detector import StateDetector, is_valid_transition
from word_madness_bot.vision.classifier import Classification


@pytest.mark.parametrize(
    ("label", "state"),
    [
        ("home", GameState.HOME),
        ("playing", GameState.PLAYING),
        ("victory", GameState.VICTORY),
        ("advertisement", GameState.ADVERTISEMENT),
        ("other", GameState.UNKNOWN),
    ],
)
def test_each_documented_state_and_unknown(label: str, state: GameState) -> None:
    assert StateDetector(stable_observations=1).observe(Classification(label, 0.9)).state is state


def test_confidence_boundary() -> None:
    detector = StateDetector(minimum_confidence=0.7, stable_observations=1)
    assert detector.observe(Classification("home", 0.7)).state is GameState.HOME
    assert detector.observe(Classification("home", 0.699)).state is GameState.UNKNOWN


def test_missing_vision_evidence_is_unknown() -> None:
    observation = StateDetector(stable_observations=1).observe(None)
    assert observation.state is GameState.UNKNOWN
    assert observation.confidence == 0


def test_state_requires_consecutive_observations() -> None:
    detector = StateDetector(stable_observations=2)
    first = detector.observe(Classification("home", 0.9))
    second = detector.observe(Classification("home", 0.8))
    assert not first.stable
    assert second.stable
    assert detector.stable_state is GameState.HOME


def test_conflicting_evidence_resets_stability() -> None:
    detector = StateDetector(stable_observations=2)
    detector.observe(Classification("home", 0.9))
    result = detector.observe(Classification("playing", 0.9))
    assert not result.stable
    assert result.consecutive_observations == 1


def test_invalid_transition_falls_back_to_unknown() -> None:
    detector = StateDetector(stable_observations=1)
    detector.observe(Classification("home", 0.9))
    result = detector.observe(Classification("victory", 0.9))
    assert result.state is GameState.UNKNOWN
    assert not result.transition_valid


def test_transition_contract() -> None:
    assert is_valid_transition(GameState.PLAYING, GameState.VICTORY)
    assert not is_valid_transition(GameState.HOME, GameState.VICTORY)


def test_evidence_is_stable_and_sorted() -> None:
    result = StateDetector(stable_observations=1).observe(
        Classification("home", 0.9), evidence={"template": "home", "ocr": "ready"}
    )
    assert result.evidence == (("ocr", "ready"), ("template", "home"))
