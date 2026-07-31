"""OpenCV screen classification for bounded runtime integration."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from importlib import import_module
from importlib.resources import files
from typing import Any, ClassVar

from word_madness_bot.domain.errors import ImageDecodeError, VisionError
from word_madness_bot.domain.geometry import PixelRect
from word_madness_bot.domain.models import ScreenCapture


class ScreenType(StrEnum):
    """Screen labels supported by the Phase 2 runtime boundary."""

    DAILY_DASH_POPUP = "daily_dash_popup"
    HOME_SCREEN = "home_screen"
    LEVEL_SCREEN = "level_screen"
    UNKNOWN = "unknown"


@dataclass(frozen=True, slots=True)
class ScreenClassification:
    """One screen decision and optional Daily Dash close control."""

    screen: ScreenType
    confidence: float
    close_button: PixelRect | None = None

    def __post_init__(self) -> None:
        if not 0 <= self.confidence <= 1:
            raise ValueError("Screen confidence must be between zero and one")


cv2: Any = import_module("cv2")
np: Any = import_module("numpy")


class ScreenClassifier:
    """Classify screenshots and locate Daily Dash close controls with OpenCV."""

    TEMPLATE_NAMES: ClassVar[dict[ScreenType, str]] = {
        ScreenType.DAILY_DASH_POPUP: "daily_dash_popup.png",
        ScreenType.HOME_SCREEN: "home_screen.png",
        ScreenType.LEVEL_SCREEN: "level_screen.png",
    }

    def __init__(self, *, minimum_confidence: float = 0.9) -> None:
        if not 0 <= minimum_confidence <= 1:
            raise ValueError("minimum_confidence must be between zero and one")
        self.minimum_confidence = minimum_confidence
        self._templates = {
            screen: _load_template(name) for screen, name in self.TEMPLATE_NAMES.items()
        }
        self._close_template = _load_template("daily_dash_close.png")

    def classify(self, capture: ScreenCapture) -> ScreenClassification:
        """Return the strongest supported screen and close-button location."""
        source = _decode_png(capture.data)
        popup_confidence, _ = _match(
            source, self._templates[ScreenType.DAILY_DASH_POPUP]
        )
        if popup_confidence >= self.minimum_confidence:
            confidence, screen = popup_confidence, ScreenType.DAILY_DASH_POPUP
        else:
            ranked = [
                (_match(source, self._templates[candidate])[0], candidate)
                for candidate in (ScreenType.HOME_SCREEN, ScreenType.LEVEL_SCREEN)
            ]
            confidence, screen = max(ranked, key=lambda item: item[0])
        if confidence < self.minimum_confidence:
            return ScreenClassification(ScreenType.UNKNOWN, confidence)
        close_button = None
        if screen is ScreenType.DAILY_DASH_POPUP:
            close_confidence, region = _match(source, self._close_template)
            if close_confidence >= self.minimum_confidence:
                close_button = region
        return ScreenClassification(screen, confidence, close_button)


def _decode_png(data: bytes) -> Any:
    encoded = np.frombuffer(data, dtype=np.uint8)
    image = cv2.imdecode(encoded, cv2.IMREAD_GRAYSCALE)
    if image is None:
        raise ImageDecodeError("Unable to decode screenshot for screen classification")
    return image


def _load_template(name: str) -> Any:
    resource = files("word_madness_bot.resources.templates").joinpath(name)
    try:
        return _decode_png(resource.read_bytes())
    except OSError as error:
        raise VisionError(f"Unable to load production template: {name}") from error


def _match(source: Any, template: Any) -> tuple[float, PixelRect]:
    height, width = template.shape[:2]
    source_height, source_width = source.shape[:2]
    if width > source_width or height > source_height:
        return 0.0, PixelRect(0, 0, 1, 1)
    result = cv2.matchTemplate(source, template, cv2.TM_CCOEFF_NORMED)
    _, maximum, _, location = cv2.minMaxLoc(result)
    confidence = min(1.0, max(0.0, float(maximum)))
    return confidence, PixelRect(int(location[0]), int(location[1]), int(width), int(height))
