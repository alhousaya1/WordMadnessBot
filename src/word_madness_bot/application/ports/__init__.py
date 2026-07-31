"""Replaceable boundaries used by the production application layer."""

from word_madness_bot.application.ports.android import AndroidPort
from word_madness_bot.application.ports.levels import LevelRepository
from word_madness_bot.application.ports.vision import VisionPort

__all__ = ["AndroidPort", "LevelRepository", "VisionPort"]
