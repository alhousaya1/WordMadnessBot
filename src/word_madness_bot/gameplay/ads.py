"""Bounded advertisement action selection and dismissal orchestration."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from enum import StrEnum

from word_madness_bot.application.ports.android import AndroidPort
from word_madness_bot.domain.geometry import NormalizedPoint, ScreenSize


class AdvertisementType(StrEnum):
    INTERSTITIAL = "interstitial"
    REWARDED = "rewarded"
    UNKNOWN = "unknown"


class AdvertisementActionType(StrEnum):
    TAP_CLOSE = "tap_close"
    PRESS_BACK = "press_back"
    WAIT = "wait"


@dataclass(frozen=True, slots=True)
class AdvertisementDetection:
    ad_type: AdvertisementType
    confidence: float
    close_controls: tuple[NormalizedPoint, ...] = ()

    def __post_init__(self) -> None:
        if not 0 <= self.confidence <= 1:
            raise ValueError("Advertisement confidence must be between zero and one")


@dataclass(frozen=True, slots=True)
class AdvertisementAction:
    kind: AdvertisementActionType
    point: NormalizedPoint | None = None


@dataclass(frozen=True, slots=True)
class AdvertisementResult:
    dismissed: bool
    attempts: int
    actions: tuple[AdvertisementAction, ...]


class AdvertisementPolicy:
    """Select safe dismissal actions from vision evidence."""

    def __init__(self, *, minimum_confidence: float = 0.8) -> None:
        if not 0 <= minimum_confidence <= 1:
            raise ValueError("minimum_confidence must be between zero and one")
        self.minimum_confidence = minimum_confidence

    def select(self, detection: AdvertisementDetection) -> AdvertisementAction:
        if (
            detection.confidence < self.minimum_confidence
            or detection.ad_type is AdvertisementType.UNKNOWN
        ):
            return AdvertisementAction(AdvertisementActionType.WAIT)
        if detection.close_controls:
            point = max(detection.close_controls, key=lambda item: (item.x - item.y, item.x))
            return AdvertisementAction(AdvertisementActionType.TAP_CLOSE, point)
        return AdvertisementAction(AdvertisementActionType.PRESS_BACK)

    def dismiss(
        self,
        android: AndroidPort,
        detection: AdvertisementDetection,
        screen: ScreenSize,
        *,
        max_attempts: int,
        is_visible: Callable[[], bool],
    ) -> AdvertisementResult:
        if max_attempts <= 0:
            raise ValueError("max_attempts must be positive")
        actions: list[AdvertisementAction] = []
        for attempt in range(1, max_attempts + 1):
            if not is_visible():
                return AdvertisementResult(True, attempt - 1, tuple(actions))
            action = self.select(detection)
            actions.append(action)
            if action.kind is AdvertisementActionType.WAIT:
                return AdvertisementResult(False, attempt, tuple(actions))
            if action.kind is AdvertisementActionType.TAP_CLOSE:
                assert action.point is not None
                android.tap(action.point.to_pixels(screen))
            else:
                android.press_back()
        return AdvertisementResult(not is_visible(), max_attempts, tuple(actions))
