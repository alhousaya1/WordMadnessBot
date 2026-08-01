"""Runtime-only visual controls for popup recovery."""

from __future__ import annotations

from importlib import import_module
from importlib.resources import files
from typing import Any, Protocol

from word_madness_bot.domain.errors import RuntimeNavigationError
from word_madness_bot.domain.geometry import PixelRect
from word_madness_bot.domain.models import ScreenCapture

cv2: Any = import_module("cv2")
np: Any = import_module("numpy")


class PopupCloseButtonPort(Protocol):
    def detect(self, capture: ScreenCapture) -> PixelRect | None: ...


class UpperRightPopupCloseDetector:
    """Find supported X-button appearances only in the upper-right screen region."""

    def __init__(self, *, minimum_confidence: float = 0.72) -> None:
        if not 0.0 <= minimum_confidence <= 1.0:
            raise ValueError("minimum_confidence must be between zero and one")
        resource = files("word_madness_bot.resources.templates").joinpath(
            "daily_dash_close.png"
        )
        template = cv2.imdecode(
            np.frombuffer(resource.read_bytes(), dtype=np.uint8),
            cv2.IMREAD_GRAYSCALE,
        )
        if template is None:
            raise RuntimeNavigationError("Unable to decode popup close template")
        self.template = template
        self.minimum_confidence = minimum_confidence

    def detect(self, capture: ScreenCapture) -> PixelRect | None:
        image = cv2.cvtColor(_decode_color(capture), cv2.COLOR_BGR2GRAY)
        height, width = image.shape
        crop_left = round(width * 0.55)
        crop_bottom = round(height * 0.40)
        search = image[:crop_bottom, crop_left:]
        best: tuple[float, PixelRect] | None = None
        for scale in (0.65, 0.8, 1.0, 1.2, 1.35):
            template_width = max(1, round(self.template.shape[1] * scale))
            template_height = max(1, round(self.template.shape[0] * scale))
            if template_width > search.shape[1] or template_height > search.shape[0]:
                continue
            template = cv2.resize(
                self.template,
                (template_width, template_height),
                interpolation=cv2.INTER_AREA,
            )
            result = cv2.matchTemplate(search, template, cv2.TM_CCOEFF_NORMED)
            _, confidence, _, location = cv2.minMaxLoc(result)
            region = PixelRect(
                crop_left + int(location[0]),
                int(location[1]),
                template_width,
                template_height,
            )
            if best is None or confidence > best[0]:
                best = float(confidence), region
        if best is None or best[0] < self.minimum_confidence:
            return None
        return best[1]


def _decode_color(capture: ScreenCapture) -> Any:
    encoded = np.frombuffer(capture.data, dtype=np.uint8)
    image = cv2.imdecode(encoded, cv2.IMREAD_COLOR)
    if image is None:
        raise RuntimeNavigationError("Unable to decode runtime control screenshot")
    return image