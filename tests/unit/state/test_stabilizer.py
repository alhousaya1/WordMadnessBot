"""Unit tests for temporal state stabilization and debouncing."""

from word_madness_bot.config import Settings
from word_madness_bot.domain.enums import GameState, StateReasonCode
from word_madness_bot.domain.models import StateObservation
from word_madness_bot.state.stabilizer import StateStabilizer


def _observation(state: GameState, confidence: float = 0.9) -> StateObservation:
    reason = (
        StateReasonCode.CLASSIFIED
        if state is not GameState.UNKNOWN
        else StateReasonCode.WEAK_EVIDENCE
    )
    return StateObservation(state=state, confidence=confidence, reason_codes=(reason,))


def test_known_state_requires_consecutive_observations() -> None:
    """A single frame cannot expose a known state when two are required."""

    stabilizer = StateStabilizer(required_consecutive=2)

    first = stabilizer.stabilize(_observation(GameState.PLAYING, 0.9))
    second = stabilizer.stabilize(_observation(GameState.PLAYING, 0.8))

    assert first.state is GameState.UNKNOWN
    assert first.reason_codes == (StateReasonCode.DEBOUNCING,)
    assert second.state is GameState.PLAYING
    assert second.confidence == 0.8
    assert second.reason_codes == (StateReasonCode.CLASSIFIED, StateReasonCode.STABILIZED)


def test_state_change_restarts_debounce_window() -> None:
    """A different known candidate cannot inherit the prior candidate's count."""

    stabilizer = StateStabilizer(required_consecutive=2)
    stabilizer.stabilize(_observation(GameState.HOME))

    changed = stabilizer.stabilize(_observation(GameState.ADVERTISEMENT))

    assert changed.state is GameState.UNKNOWN
    assert changed.reason_codes == (StateReasonCode.DEBOUNCING,)


def test_unknown_input_is_immediate_and_resets_history() -> None:
    """Unsafe evidence immediately yields UNKNOWN and clears accumulated state."""

    stabilizer = StateStabilizer(required_consecutive=2)
    stabilizer.stabilize(_observation(GameState.VICTORY))

    unknown = stabilizer.stabilize(_observation(GameState.UNKNOWN, 0.7))
    next_known = stabilizer.stabilize(_observation(GameState.VICTORY))

    assert unknown.state is GameState.UNKNOWN
    assert StateReasonCode.UNKNOWN_INPUT in unknown.reason_codes
    assert next_known.state is GameState.UNKNOWN
    assert next_known.reason_codes == (StateReasonCode.DEBOUNCING,)


def test_single_frame_policy_stabilizes_immediately() -> None:
    """A configured one-frame policy still adds an explicit stabilized reason."""

    result = StateStabilizer(required_consecutive=1).stabilize(_observation(GameState.HOME))

    assert result.state is GameState.HOME
    assert StateReasonCode.STABILIZED in result.reason_codes


def test_stabilizer_policy_is_constructed_from_settings() -> None:
    """Validated runtime settings control the temporal debounce window."""

    stabilizer = StateStabilizer.from_settings(Settings(state_stable_frames=3))

    assert stabilizer.stabilize(_observation(GameState.HOME)).state is GameState.UNKNOWN
    assert stabilizer.stabilize(_observation(GameState.HOME)).state is GameState.UNKNOWN
    assert stabilizer.stabilize(_observation(GameState.HOME)).state is GameState.HOME
