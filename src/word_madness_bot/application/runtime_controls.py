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
    """Locate a generic popup close control."""

    def detect(self, capture: ScreenCapture) -> PixelRect | None: ...


class CompletionOverlayPort(Protocol):
    """Detect post-level overlays without involving gameplay OCR."""

    def tap_to_continue_visible(self, capture: ScreenCapture) -> bool: ...

    def daily_celebration_visible(self, capture: ScreenCapture) -> bool: ...


class CompletionOverlayDetector:
    """Detect bright post-level controls in their stable normalized regions."""

    def tap_to_continue_visible(self, capture: ScreenCapture) -> bool:
        gray = cv2.cvtColor(_decode_color(capture), cv2.COLOR_BGR2GRAY)
        height, width = gray.shape
        region = gray[
            round(height * 0.75) : round(height * 0.95),
            round(width * 0.18) : round(width * 0.82),
        ]
        return _has_text_line(region, minimum_components=6)

    def daily_celebration_visible(self, capture: ScreenCapture) -> bool:
        gray = cv2.cvtColor(_decode_color(capture), cv2.COLOR_BGR2GRAY)
        height, width = gray.shape
        arrow_region = gray[
            round(height * 0.02) : round(height * 0.18),
            round(width * 0.01) : round(width * 0.16),
        ]
        heading_region = gray[
            round(height * 0.04) : round(height * 0.24),
            round(width * 0.18) : round(width * 0.82),
        ]
        return _has_back_arrow(arrow_region) and _has_text_line(
            heading_region, minimum_components=8
        )


def _has_text_line(region: Any, *, minimum_components: int) -> bool:
    _, mask = cv2.threshold(region, 210, 255, cv2.THRESH_BINARY)
    count, _, stats, _ = cv2.connectedComponentsWithStats(mask, connectivity=8)
    region_height, region_width = region.shape
    components = 0
    for left, top, width, height, area in stats[1:count]:
        del left, top
        if (
            area >= 6
            and height >= max(2, round(region_height * 0.025))
            and height <= round(region_height * 0.35)
            and width <= round(region_width * 0.20)
        ):
            components += 1
    return components >= minimum_components


def _has_back_arrow(region: Any) -> bool:
    _, mask = cv2.threshold(region, 210, 255, cv2.THRESH_BINARY)
    contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    region_area = float(region.shape[0] * region.shape[1])
    return any(0.002 <= cv2.contourArea(contour) / region_area <= 0.20 for contour in contours)


class UpperRightPopupCloseDetector:
    """Find supported X-button appearances only in the upper-right screen region."""

    def __init__(self, *, minimum_confidence: float = 0.72) -> None:
        if not 0.0 <= minimum_confidence <= 1.0:
            raise ValueError("minimum_confidence must be between zero and one")
        resource = files("word_madness_bot.resources.templates").joinpath("daily_dash_close.png")
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
