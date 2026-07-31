"""Typed policies that do not depend on the future gameplay state machine."""

from word_madness_bot.gameplay.actions import AdvertisementDecision
from word_madness_bot.gameplay.ad_policy import AdvertisementPolicy

__all__ = ["AdvertisementDecision", "AdvertisementPolicy"]
