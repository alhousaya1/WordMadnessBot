"""Single-frame runtime state classification and action dispatch."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from enum import StrEnum

from word_madness_bot.application.runtime_controls import (
    CompletionOverlayPort,
    PopupCloseButtonPort,
)
from word_madness_bot.domain.geometry import NormalizedPoint, PixelPoint, PixelRect
from word_madness_bot.domain.models import ScreenCapture
from word_madness_bot.vision.screen_classifier import ScreenClassification, ScreenType

START_LEVEL_POINT = NormalizedPoint(0.500, 0.654)
BOTTOM_CENTER_POINT = NormalizedPoint(0.500, 0.900)
BACK_POINT = NormalizedPoint(0.050, 0.070)


RuntimeScreenClassifier = Callable[[ScreenCapture], ScreenClassification]


class RuntimeScreenState(StrEnum):
    NORMAL_HOME = "normal_home"
    COMPLETION_HOME = "completion_home"
    LEVEL = "level"
    TAP_TO_CONTINUE = "tap_to_continue"
    DAILY_CELEBRATION = "daily_celebration"
    GENERIC_X_POPUP = "generic_x_popup"
    SETTINGS = "settings"
    UNKNOWN = "unknown"


@dataclass(frozen=True, slots=True)
class RuntimeDispatch:
    state: RuntimeScreenState
    action_point: PixelPoint | None = None
    classification: ScreenClassification | None = None
    action_region: PixelRect | None = None


class RuntimeScreenDispatcher:
    """Give one captured screen to exactly one state handler."""

    def __init__(
        self,
        classifier: RuntimeScreenClassifier,
        overlays: CompletionOverlayPort | None,
        popup_close_detector: PopupCloseButtonPort | None,
    ) -> None:
        self.classifier = classifier
        self.overlays = overlays
        self.popup_close_detector = popup_close_detector

    def dispatch(self, capture: ScreenCapture) -> RuntimeDispatch:
        """Classify one frame with Home and Level protected from arrow actions."""
        if self.overlays is not None and self.overlays.completion_home_visible(capture):
            locate_button = getattr(self.overlays, "completion_home_button", None)
            button = locate_button(capture) if callable(locate_button) else None
            return RuntimeDispatch(
                RuntimeScreenState.COMPLETION_HOME,
                _center(button)
                if button is not None
                else START_LEVEL_POINT.to_pixels(capture.size),
                action_region=button,
            )

        classification = self.classifier(capture)
        if classification.screen is ScreenType.HOME_SCREEN:
            return RuntimeDispatch(
                RuntimeScreenState.NORMAL_HOME,
                START_LEVEL_POINT.to_pixels(capture.size),
                classification,
            )
        if classification.screen is ScreenType.LEVEL_SCREEN:
            return RuntimeDispatch(
                RuntimeScreenState.LEVEL,
                classification=classification,
            )

        if self.overlays is not None and self.overlays.tap_to_continue_visible(capture):
            return RuntimeDispatch(
                RuntimeScreenState.TAP_TO_CONTINUE,
                BOTTOM_CENTER_POINT.to_pixels(capture.size),
                classification,
            )
        if self.overlays is not None and self.overlays.daily_celebration_visible(capture):
            return RuntimeDispatch(
                RuntimeScreenState.DAILY_CELEBRATION,
                BACK_POINT.to_pixels(capture.size),
                classification,
            )

        close_button = classification.close_button
        if close_button is None and self.popup_close_detector is not None:
            close_button = self.popup_close_detector.detect(capture)
        if close_button is not None:
            return RuntimeDispatch(
                RuntimeScreenState.GENERIC_X_POPUP,
                PixelPoint(
                    close_button.left + close_button.width // 2,
                    close_button.top + close_button.height // 2,
                ),
                classification,
            )

        if (
            classification.screen is ScreenType.UNKNOWN
            and self.overlays is not None
            and self.overlays.settings_visible(capture)
        ):
            return RuntimeDispatch(
                RuntimeScreenState.SETTINGS,
                BACK_POINT.to_pixels(capture.size),
                classification,
            )
        return RuntimeDispatch(RuntimeScreenState.UNKNOWN, classification=classification)


def _center(region: PixelRect) -> PixelPoint:
    return PixelPoint(
        region.left + region.width // 2,
        region.top + region.height // 2,
    )
