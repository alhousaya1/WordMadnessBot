"""Dependency-inversion contracts for replaceable application layers."""

from word_madness_bot.contracts.capture import ScreenshotCapture
from word_madness_bot.contracts.database import LevelRepository
from word_madness_bot.contracts.device import DeviceGateway
from word_madness_bot.contracts.input import InputExecutor
from word_madness_bot.contracts.state import GameStateDetector
from word_madness_bot.contracts.swipe import SwipeGenerator
from word_madness_bot.contracts.vision import VisionEngine

__all__ = [
    "DeviceGateway",
    "GameStateDetector",
    "InputExecutor",
    "LevelRepository",
    "ScreenshotCapture",
    "SwipeGenerator",
    "VisionEngine",
]
