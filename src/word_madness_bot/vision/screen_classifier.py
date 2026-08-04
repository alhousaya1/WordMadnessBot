"""OpenCV screen classification for bounded runtime integration."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from importlib import import_module
from importlib.resources import files
from typing import Any, ClassVar

from word_madness_bot.domain.errors import (
    ImageDecodeError,
    VisionError,
    WheelGeometryDetectionError,
)
from word_madness_bot.domain.geometry import PixelRect
from word_madness_bot.domain.models import ScreenCapture
from word_madness_bot.vision.wheel_geometry import LetterWheelDetector


class ScreenType(StrEnum):
    """Screen labels supported by the bounded production runtime."""

    DAILY_DASH_POPUP = "daily_dash_popup"
    HOME_SCREEN = "home_screen"
    LEVEL_SCREEN = "level_screen"
    UNKNOWN = "unknown"


@dataclass(frozen=True, slots=True)
class ScreenClassification:
    """One screen decision and optional matched action controls."""

    screen: ScreenType
    confidence: float
    close_button: PixelRect | None = None
    start_button: PixelRect | None = None
    start_button_confidence: float | None = None
    home_template_confidence: float | None = None
    level_template_confidence: float | None = None
    level_template_matched: bool | None = None
    wheel_visible: bool | None = None
    wheel_detection_error: str | None = None

    def __post_init__(self) -> None:
        if not 0 <= self.confidence <= 1:
            raise ValueError("Screen confidence must be between zero and one")
        if self.start_button_confidence is not None and not 0 <= self.start_button_confidence <= 1:
            raise ValueError("Start button confidence must be between zero and one")


cv2: Any = import_module("cv2")
np: Any = import_module("numpy")


class ScreenClassifier:
    """Classify screenshots and locate bounded runtime action controls."""

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
        self._start_template = _load_template("start_level_button.png")

    def classify(self, capture: ScreenCapture) -> ScreenClassification:
        """Return the strongest supported screen and matched action control."""
        source = _decode_png(capture.data)
        popup_confidence, _ = _match(source, self._templates[ScreenType.DAILY_DASH_POPUP])
        home_confidence, _ = _match(source, self._templates[ScreenType.HOME_SCREEN])
        level_confidence, _ = _match(source, self._templates[ScreenType.LEVEL_SCREEN])
        try:
            LetterWheelDetector().detect(capture)
        except WheelGeometryDetectionError as error:
            wheel_visible = False
            wheel_detection_error = str(error)
        else:
            wheel_visible = True
            wheel_detection_error = None

            # A false circle on a bright or animated home frame must not
            # override strong home-screen evidence. The previous code
            # returned LEVEL_SCREEN immediately whenever any wheel-like
            # circle was detected.
            if (
                home_confidence >= self.minimum_confidence
                and level_confidence < self.minimum_confidence
            ):
                completion_button = _find_yellow_level_button(
                    _decode_png_color(capture.data)
                )
                if completion_button is None:
                    height, width = source.shape[:2]
                    completion_button = PixelRect(
                        round(width * 263 / 1440),
                        round(height * 2072 / 3120),
                        max(1, round(width * 913 / 1440)),
                        max(1, round(height * 200 / 3120)),
                    )
                return ScreenClassification(
                    ScreenType.HOME_SCREEN,
                    home_confidence,
                    start_button=completion_button,
                    start_button_confidence=(
                        1.0 if completion_button is not None else None
                    ),
                    home_template_confidence=home_confidence,
                    level_template_confidence=level_confidence,
                    level_template_matched=False,
                    wheel_visible=True,
                    wheel_detection_error=(
                        "Wheel-like geometry rejected because strong home "
                        "template evidence conflicts with weak level evidence"
                    ),
                )

            return ScreenClassification(
                ScreenType.LEVEL_SCREEN,
                1.0,
                home_template_confidence=home_confidence,
                level_template_confidence=level_confidence,
                level_template_matched=level_confidence >= self.minimum_confidence,
                wheel_visible=True,
            )

        if popup_confidence >= self.minimum_confidence:
            confidence, screen = popup_confidence, ScreenType.DAILY_DASH_POPUP
        elif home_confidence >= level_confidence:
            confidence, screen = home_confidence, ScreenType.HOME_SCREEN
        else:
            confidence, screen = level_confidence, ScreenType.LEVEL_SCREEN

        if confidence < self.minimum_confidence:
            completion_button = _find_yellow_level_button(_decode_png_color(capture.data))
            if completion_button is not None:
                return ScreenClassification(
                    ScreenType.HOME_SCREEN,
                    1.0,
                    start_button=completion_button,
                    start_button_confidence=1.0,
                    home_template_confidence=home_confidence,
                    level_template_confidence=level_confidence,
                    level_template_matched=False,
                    wheel_visible=wheel_visible,
                    wheel_detection_error=wheel_detection_error,
                )
            return ScreenClassification(
                ScreenType.UNKNOWN,
                confidence,
                home_template_confidence=home_confidence,
                level_template_confidence=level_confidence,
                level_template_matched=False,
                wheel_visible=wheel_visible,
                wheel_detection_error=wheel_detection_error,
            )

        close_button = None
        start_button = None
        start_button_confidence = None
        if screen is ScreenType.DAILY_DASH_POPUP:
            close_confidence, region = _match(source, self._close_template)
            if close_confidence >= self.minimum_confidence:
                close_button = region
        elif screen is ScreenType.HOME_SCREEN:
            start_button_confidence, region = _match(source, self._start_template)
            if start_button_confidence >= self.minimum_confidence:
                start_button = region
        return ScreenClassification(
            screen,
            confidence,
            close_button,
            start_button,
            start_button_confidence,
            home_template_confidence=home_confidence,
            level_template_confidence=level_confidence,
            level_template_matched=level_confidence >= self.minimum_confidence,
            wheel_visible=wheel_visible,
            wheel_detection_error=wheel_detection_error,
        )


def _decode_png(data: bytes) -> Any:
    encoded = np.frombuffer(data, dtype=np.uint8)
    image = cv2.imdecode(encoded, cv2.IMREAD_GRAYSCALE)
    if image is None:
        raise ImageDecodeError("Unable to decode screenshot for screen classification")
    return image


def _decode_png_color(data: bytes) -> Any:
    encoded = np.frombuffer(data, dtype=np.uint8)
    image = cv2.imdecode(encoded, cv2.IMREAD_COLOR)
    if image is None:
        raise ImageDecodeError("Unable to decode screenshot for screen classification")
    return image


def _find_yellow_level_button(source: Any) -> PixelRect | None:
    height, width = source.shape[:2]
    left = round(width * 0.15)
    right = round(width * 0.85)
    top = round(height * 0.52)
    bottom = round(height * 0.78)
    search = source[top:bottom, left:right]
    hsv = cv2.cvtColor(search, cv2.COLOR_BGR2HSV)
    mask = cv2.inRange(
        hsv,
        np.array((15, 100, 120), dtype=np.uint8),
        np.array((42, 255, 255), dtype=np.uint8),
    )
    kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (9, 9))
    mask = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, kernel)
    contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    candidates: list[tuple[float, PixelRect]] = []
    for contour in contours:
        x, y, candidate_width, candidate_height = cv2.boundingRect(contour)
        if candidate_height == 0:
            continue
        aspect_ratio = candidate_width / candidate_height
        fill_ratio = cv2.contourArea(contour) / (candidate_width * candidate_height)
        if (
            candidate_width >= round(width * 0.18)
            and round(height * 0.035) <= candidate_height <= round(height * 0.14)
            and aspect_ratio >= 2.0
            and fill_ratio >= 0.55
        ):
            candidates.append(
                (
                    float(cv2.contourArea(contour)),
                    PixelRect(
                        left + int(x),
                        top + int(y),
                        int(candidate_width),
                        int(candidate_height),
                    ),
                )
            )
    if not candidates:
        return None
    return max(candidates, key=lambda candidate: candidate[0])[1]


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
