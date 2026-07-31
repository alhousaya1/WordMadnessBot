from typing import Any

from word_madness_bot.domain.geometry import NormalizedPoint, ScreenSize
from word_madness_bot.gameplay.ads import (
    AdvertisementActionType,
    AdvertisementDetection,
    AdvertisementPolicy,
    AdvertisementType,
)


class Android:
    def __init__(self) -> None:
        self.taps: list[Any] = []
        self.backs = 0

    def tap(self, point: Any) -> None:
        self.taps.append(point)

    def press_back(self) -> None:
        self.backs += 1

    def __getattr__(self, name: str) -> Any:
        return lambda *args, **kwargs: None


def test_close_control_prefers_top_right() -> None:
    detection = AdvertisementDetection(
        AdvertisementType.INTERSTITIAL, 0.9, (NormalizedPoint(0.1, 0.1), NormalizedPoint(0.9, 0.05))
    )
    assert AdvertisementPolicy().select(detection).point == NormalizedPoint(0.9, 0.05)


def test_low_confidence_and_unknown_prevent_false_positive() -> None:
    assert (
        AdvertisementPolicy()
        .select(AdvertisementDetection(AdvertisementType.INTERSTITIAL, 0.2))
        .kind
        is AdvertisementActionType.WAIT
    )
    assert (
        AdvertisementPolicy().select(AdvertisementDetection(AdvertisementType.UNKNOWN, 1)).kind
        is AdvertisementActionType.WAIT
    )


def test_back_fallback_and_bounded_attempts() -> None:
    android = Android()
    visible = iter([True, False])
    result = AdvertisementPolicy().dismiss(
        android,
        AdvertisementDetection(AdvertisementType.REWARDED, 0.9),
        ScreenSize(100, 200),
        max_attempts=2,
        is_visible=lambda: next(visible),
    )
    assert result.dismissed and android.backs == 1


def test_tap_dismissal_uses_scaled_control() -> None:
    android = Android()
    visible = iter([True, False])
    detection = AdvertisementDetection(
        AdvertisementType.INTERSTITIAL, 0.9, (NormalizedPoint(1, 0),)
    )
    assert (
        AdvertisementPolicy()
        .dismiss(
            android,
            detection,
            ScreenSize(100, 200),
            max_attempts=1,
            is_visible=lambda: next(visible),
        )
        .dismissed
    )
    assert android.taps[0].x == 99
