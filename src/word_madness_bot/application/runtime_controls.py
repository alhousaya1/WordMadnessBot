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

    def completion_home_visible(self, capture: ScreenCapture) -> bool: ...

    def settings_visible(self, capture: ScreenCapture) -> bool: ...


class CompletionOverlayDetector:
    """Detect post-level controls in their stable normalized regions."""

    def tap_to_continue_visible(self, capture: ScreenCapture) -> bool:
        image = _decode_color(capture)
        if _has_yellow_level_button(image):
            return False
        gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
        height, width = gray.shape
        region = gray[
            round(height * 0.60) : round(height * 0.96),
            round(width * 0.12) : round(width * 0.88),
        ]
        return _has_text_line(region, minimum_components=6)

    def daily_celebration_visible(self, capture: ScreenCapture) -> bool:
        image = _decode_color(capture)
        if _has_yellow_level_button(image):
            return False
        gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
        height, width = gray.shape
        heading_region = gray[
            round(height * 0.04) : round(height * 0.24),
            round(width * 0.18) : round(width * 0.82),
        ]
        return _has_back_arrow(_back_arrow_region(gray)) and _has_text_line(
            heading_region, minimum_components=8
        )

    def completion_home_visible(self, capture: ScreenCapture) -> bool:
        image = _decode_color(capture)
        return _has_intelligent_heading(image) or _has_yellow_level_button(image)

    def completion_home_button(self, capture: ScreenCapture) -> PixelRect | None:
        """Return the actual yellow Level button rectangle when it is visible."""
        return _find_yellow_level_button(_decode_color(capture))

    def settings_visible(self, capture: ScreenCapture) -> bool:
        image = _decode_color(capture)
        if _has_yellow_level_button(image):
            return False
        gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
        height, width = gray.shape
        content = gray[
            round(height * 0.10) : round(height * 0.88),
            round(width * 0.10) : round(width * 0.78),
        ]
        return _has_back_arrow(_back_arrow_region(gray)) and _text_row_count(content) >= 4


def _has_text_line(region: Any, *, minimum_components: int) -> bool:
    _, mask = cv2.threshold(region, 165, 255, cv2.THRESH_BINARY)
    count, _, stats, _ = cv2.connectedComponentsWithStats(mask, connectivity=8)
    region_height, region_width = region.shape
    centers: list[int] = []
    for left, top, width, height, area in stats[1:count]:
        del left
        if (
            area >= 6
            and height >= max(2, round(region_height * 0.008))
            and height <= round(region_height * 0.18)
            and width <= round(region_width * 0.20)
        ):
            centers.append(top + height // 2)
    row_tolerance = max(4, round(region_height * 0.04))
    return any(
        sum(abs(candidate - center) <= row_tolerance for candidate in centers) >= minimum_components
        for center in centers
    )


def _text_row_count(region: Any) -> int:
    _, mask = cv2.threshold(region, 165, 255, cv2.THRESH_BINARY)
    horizontal_kernel = cv2.getStructuringElement(
        cv2.MORPH_RECT,
        (max(3, round(region.shape[1] * 0.04)), 3),
    )
    joined = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, horizontal_kernel)
    contours, _ = cv2.findContours(joined, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    return sum(
        width >= round(region.shape[1] * 0.12) and height <= round(region.shape[0] * 0.12)
        for _, _, width, height in (cv2.boundingRect(contour) for contour in contours)
    )


def _back_arrow_region(gray: Any) -> Any:
    height, width = gray.shape
    return gray[
        round(height * 0.02) : round(height * 0.18),
        round(width * 0.01) : round(width * 0.16),
    ]


def _has_intelligent_heading(image: Any) -> bool:
    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    height, width = gray.shape
    region = gray[
        round(height * 0.08) : round(height * 0.30),
        round(width * 0.12) : round(width * 0.88),
    ]
    _, mask = cv2.threshold(region, 165, 255, cv2.THRESH_BINARY)
    count, _, stats, _ = cv2.connectedComponentsWithStats(mask, connectivity=8)
    centers: list[int] = []
    for _, top, glyph_width, glyph_height, area in stats[1:count]:
        if (
            area >= 12
            and round(height * 0.018) <= glyph_height <= round(height * 0.10)
            and glyph_width <= round(width * 0.12)
        ):
            centers.append(top + glyph_height // 2)
    tolerance = max(4, round(height * 0.012))
    return any(
        sum(abs(candidate - center) <= tolerance for candidate in centers) >= 10
        for center in centers
    )


def _has_yellow_level_button(image: Any) -> bool:
    return _find_yellow_level_button(image) is not None


def _find_yellow_level_button(image: Any) -> PixelRect | None:
    height, width = image.shape[:2]
    crop_left = round(width * 0.15)
    crop_top = round(height * 0.52)
    region = image[
        crop_top : round(height * 0.78),
        crop_left : round(width * 0.85),
    ]
    hsv = cv2.cvtColor(region, cv2.COLOR_BGR2HSV)
    mask = cv2.inRange(
        hsv,
        np.array((15, 100, 120), dtype=np.uint8),
        np.array((42, 255, 255), dtype=np.uint8),
    )
    contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    candidates: list[tuple[float, PixelRect]] = []
    for contour in contours:
        left, top, candidate_width, candidate_height = cv2.boundingRect(contour)
        if candidate_height == 0:
            continue
        fill_ratio = cv2.contourArea(contour) / (candidate_width * candidate_height)
        if (
            candidate_width >= round(width * 0.18)
            and round(height * 0.035) <= candidate_height <= round(height * 0.14)
            and candidate_width / candidate_height >= 2.0
            and fill_ratio >= 0.55
        ):
            candidates.append(
                (
                    cv2.contourArea(contour),
                    PixelRect(
                        crop_left + left,
                        crop_top + top,
                        candidate_width,
                        candidate_height,
                    ),
                )
            )
    if not candidates:
        return None
    return max(candidates, key=lambda candidate: candidate[0])[1]


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
