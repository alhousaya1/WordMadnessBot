from __future__ import annotations

import pytest

from word_madness_bot.application.runtime_dispatcher import (
    RuntimeScreenDispatcher,
    RuntimeScreenState,
)
from word_madness_bot.domain.geometry import PixelPoint, PixelRect, ScreenSize
from word_madness_bot.domain.models import ScreenCapture
from word_madness_bot.vision.screen_classifier import ScreenClassification, ScreenType

CAPTURE = ScreenCapture(b"capture", ScreenSize(400, 800))


class Classifier:
    def __init__(self, screen: ScreenType) -> None:
        self.result = ScreenClassification(screen, 0.99)
        self.calls = 0

    def classify(self, capture: ScreenCapture) -> ScreenClassification:
        self.calls += 1
        return self.result


class Overlays:
    def __init__(
        self,
        *,
        completion_home: bool = False,
        tap_to_continue: bool = False,
        daily_celebration: bool = False,
        settings: bool = False,
    ) -> None:
        self.completion_home = completion_home
        self.tap_to_continue = tap_to_continue
        self.daily_celebration = daily_celebration
        self.settings = settings

    def completion_home_visible(self, capture: ScreenCapture) -> bool:
        return self.completion_home

    def tap_to_continue_visible(self, capture: ScreenCapture) -> bool:
        return self.tap_to_continue

    def daily_celebration_visible(self, capture: ScreenCapture) -> bool:
        return self.daily_celebration

    def settings_visible(self, capture: ScreenCapture) -> bool:
        return self.settings


class Popup:
    def __init__(self, result: PixelRect | None = None) -> None:
        self.result = result

    def detect(self, capture: ScreenCapture) -> PixelRect | None:
        return self.result


@pytest.mark.parametrize(
    ("screen", "overlays", "expected", "point"),
    [
        (
            ScreenType.UNKNOWN,
            Overlays(completion_home=True),
            RuntimeScreenState.COMPLETION_HOME,
            PixelPoint(200, 523),
        ),
        (
            ScreenType.HOME_SCREEN,
            Overlays(),
            RuntimeScreenState.NORMAL_HOME,
            PixelPoint(200, 523),
        ),
        (ScreenType.LEVEL_SCREEN, Overlays(), RuntimeScreenState.LEVEL, None),
        (
            ScreenType.UNKNOWN,
            Overlays(tap_to_continue=True),
            RuntimeScreenState.TAP_TO_CONTINUE,
            PixelPoint(200, 719),
        ),
        (
            ScreenType.UNKNOWN,
            Overlays(daily_celebration=True),
            RuntimeScreenState.DAILY_CELEBRATION,
            PixelPoint(20, 56),
        ),
        (
            ScreenType.UNKNOWN,
            Overlays(settings=True),
            RuntimeScreenState.SETTINGS,
            PixelPoint(20, 56),
        ),
    ],
)
def test_dispatches_supported_startup_states(
    screen: ScreenType,
    overlays: Overlays,
    expected: RuntimeScreenState,
    point: PixelPoint | None,
) -> None:
    classifier = Classifier(screen)
    result = RuntimeScreenDispatcher(classifier.classify, overlays, Popup()).dispatch(CAPTURE)

    assert result.state is expected
    assert result.action_point == point


def test_completion_home_is_primary_and_never_classifies_for_arrow() -> None:
    classifier = Classifier(ScreenType.LEVEL_SCREEN)
    result = RuntimeScreenDispatcher(
        classifier.classify,
        Overlays(completion_home=True, daily_celebration=True, settings=True),
        Popup(PixelRect(300, 20, 40, 40)),
    ).dispatch(CAPTURE)

    assert result.state is RuntimeScreenState.COMPLETION_HOME
    assert classifier.calls == 0


def test_dispatches_generic_x_popup_to_its_center() -> None:
    result = RuntimeScreenDispatcher(
        Classifier(ScreenType.UNKNOWN).classify,
        Overlays(),
        Popup(PixelRect(300, 20, 40, 40)),
    ).dispatch(CAPTURE)

    assert result.state is RuntimeScreenState.GENERIC_X_POPUP
    assert result.action_point == PixelPoint(320, 40)
