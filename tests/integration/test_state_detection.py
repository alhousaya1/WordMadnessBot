"""Fixture-backed integration from Milestone 4 evidence to game state."""

from pathlib import Path

from word_madness_bot.domain.states import GameState
from word_madness_bot.gameplay.state_detector import StateDetector
from word_madness_bot.vision.classifier import VisionClassifier
from word_madness_bot.vision.letters import detect_circles
from word_madness_bot.vision.preprocessing import load_image, preprocess


def test_synthetic_visual_evidence_reaches_stable_playing_state() -> None:
    fixture = Path(__file__).parents[1] / "fixtures" / "images" / "shapes.png"
    circles = detect_circles(preprocess(load_image(fixture)))
    classification = VisionClassifier(minimum_confidence=0.5).classify(
        {"playing": len(circles) / 2}
    )
    detector = StateDetector(stable_observations=2)
    detector.observe(classification, evidence={"circles": str(len(circles))})
    result = detector.observe(classification, evidence={"circles": str(len(circles))})
    assert result.state is GameState.PLAYING
    assert result.stable
