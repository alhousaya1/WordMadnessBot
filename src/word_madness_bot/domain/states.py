"""Game states described by the production architecture."""

from enum import StrEnum


class GameState(StrEnum):
    """A classified high-level state of the Android game."""

    HOME = "home"
    PLAYING = "playing"
    VICTORY = "victory"
    ADVERTISEMENT = "advertisement"
    UNKNOWN = "unknown"
