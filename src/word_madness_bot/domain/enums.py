"""Enumerations shared across application boundaries."""

from enum import StrEnum


class GameState(StrEnum):
    """Logical screen states recognized by the game-state layer."""

    HOME = "home"
    PLAYING = "playing"
    VICTORY = "victory"
    ADVERTISEMENT = "advertisement"
    UNKNOWN = "unknown"


class InputActionKind(StrEnum):
    """Kinds of completed input actions accepted by an input adapter."""

    TAP = "tap"
    SWIPE = "swipe"
    KEY_EVENT = "key_event"


class VisionEvidenceKind(StrEnum):
    """Stable kinds of visual evidence consumed by state classification."""

    HOME_INDICATOR = "home_indicator"
    PLAYING_BOARD = "playing_board"
    LETTER_WHEEL = "letter_wheel"
    LEVEL_NUMBER = "level_number"
    VICTORY_BANNER = "victory_banner"
    ADVERTISEMENT_INDICATOR = "advertisement_indicator"
    ADVERTISEMENT_CLOSE_CONTROL = "advertisement_close_control"


class StateReasonCode(StrEnum):
    """Machine-readable reasons accompanying every state observation."""

    CLASSIFIED = "classified"
    NO_EVIDENCE = "no_evidence"
    NO_RECOGNIZED_EVIDENCE = "no_recognized_evidence"
    WEAK_EVIDENCE = "weak_evidence"
    CONFLICTING_EVIDENCE = "conflicting_evidence"
    DEBOUNCING = "debouncing"
    STABILIZED = "stabilized"
    UNKNOWN_INPUT = "unknown_input"


class EngineState(StrEnum):
    """Explicit internal states of the decision-engine finite-state machine."""

    OBSERVING = "observing"
    SOLVING_LEVEL = "solving_level"
    VERIFYING_WORD = "verifying_word"
    HANDLING_ADVERTISEMENT = "handling_advertisement"
    RECOVERING = "recovering"
    STOPPED = "stopped"


class RecoveryFailure(StrEnum):
    """Recoverable failure categories understood by the decision engine."""

    UNKNOWN_STATE = "unknown_state"
    LEVEL_READ_FAILED = "level_read_failed"
    LEVEL_NOT_FOUND = "level_not_found"
    LETTERS_UNAVAILABLE = "letters_unavailable"
    WORD_COMMAND_FAILED = "word_command_failed"
    VERIFICATION_FAILED = "verification_failed"
