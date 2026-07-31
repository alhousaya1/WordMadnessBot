"""ADB transport and screenshot acquisition."""

from word_madness_bot.infrastructure.adb.client import AdbClient
from word_madness_bot.infrastructure.adb.screenshot import save_screenshot

__all__ = ["AdbClient", "save_screenshot"]
