from typing import Any

from word_madness_bot.application.recovery import RecoveryStrategy, RetryPolicy, TimeoutPolicy
from word_madness_bot.domain.geometry import NormalizedPoint, ScreenSize
from word_madness_bot.gameplay.ads import (
    AdvertisementDetection,
    AdvertisementPolicy,
    AdvertisementType,
)


class Android:
    def __init__(self) -> None:
        self.calls = 0

    def tap(self, point: Any) -> None:
        self.calls += 1
        if self.calls == 1:
            raise OSError("disconnected")

    def __getattr__(self, name: str) -> Any:
        return lambda *args, **kwargs: None


def test_disconnect_recovery_then_ad_dismissal() -> None:
    android = Android()
    detection = AdvertisementDetection(
        AdvertisementType.INTERSTITIAL, 0.9, (NormalizedPoint(1, 0),)
    )
    policy = AdvertisementPolicy()
    recovery = RecoveryStrategy(
        RetryPolicy(2, 0), TimeoutPolicy(2), sleeper=lambda _: None, clock=lambda: 0
    )
    result = recovery.execute(
        lambda: policy.dismiss(
            android,
            detection,
            ScreenSize(100, 200),
            max_attempts=1,
            is_visible=lambda: android.calls < 2,
        ),
        recoverable=(OSError,),
    )
    assert result.dismissed and android.calls == 2
