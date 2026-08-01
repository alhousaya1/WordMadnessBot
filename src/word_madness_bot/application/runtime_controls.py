"""Runtime-only visual controls for Home navigation and popup recovery."""

from __future__ import annotations

import io
import itertools
from dataclasses import dataclass
from importlib import import_module
from importlib.resources import files
from typing import Any, Protocol

from PIL import Image

from word_madness_bot.domain.errors import OcrError, RuntimeNavigationError
from word_madness_bot.domain.geometry import PixelRect
from word_madness_bot.domain.models import ScreenCapture

cv2: Any = import_module("cv2")
np: Any = import_module("numpy")


@dataclass(frozen=True, slots=True)
class HomeLevelButton:
    """Detected yellow Home button and the level number read inside it."""

    region: PixelRect
    level: int


class HomeLevelButtonPort(Protocol):
    def detect(self, capture: ScreenCapture) -> HomeLevelButton: ...


class PopupCloseButtonPort(Protocol):
    def detect(self, capture: ScreenCapture) -> PixelRect | None: ...


@dataclass(frozen=True, slots=True)
class _Glyph:
    left: int
    width: int
    height: int
    mask: Any

    @property
    def right(self) -> int:
        return self.left + self.width


class YellowLevelButtonDetector:
    """Locate the yellow rounded rectangle and read only its interior text."""

    def __init__(self, *, minimum_digit_confidence: float = 0.72) -> None:
        if not 0.0 <= minimum_digit_confidence <= 1.0:
            raise ValueError("minimum_digit_confidence must be between zero and one")
        package = files("word_madness_bot.resources.digits")
        self._templates = {
            digit: _normalize_mask(
                Image.open(io.BytesIO(package.joinpath(f"{digit}.png").read_bytes()))
            )
            for digit in "0123456789"
        }
        self.minimum_digit_confidence = minimum_digit_confidence

    def detect(self, capture: ScreenCapture) -> HomeLevelButton:
        image = _decode_color(capture)
        hsv = cv2.cvtColor(image, cv2.COLOR_BGR2HSV)
        mask = cv2.inRange(
            hsv,
            np.array((15, 120, 150), dtype=np.uint8),
            np.array((40, 255, 255), dtype=np.uint8),
        )
        height, width = mask.shape
        kernel_size = max(3, round(min(width, height) * 0.008))
        kernel = cv2.getStructuringElement(
            cv2.MORPH_ELLIPSE, (kernel_size, kernel_size)
        )
        mask = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, kernel)
        contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        candidates: list[tuple[float, PixelRect]] = []
        for contour in contours:
            left, top, button_width, button_height = cv2.boundingRect(contour)
            aspect = button_width / button_height
            area_ratio = button_width * button_height / (width * height)
            if (
                top >= height * 0.45
                and 2.5 <= aspect <= 7.0
                and 0.02 <= area_ratio <= 0.15
                and button_width >= width * 0.35
            ):
                fill_ratio = cv2.contourArea(contour) / (button_width * button_height)
                if not 0.80 <= fill_ratio < 0.995:
                    continue
                candidates.append(
                    (
                        fill_ratio * button_width * button_height,
                        PixelRect(left, top, button_width, button_height),
                    )
                )
        if not candidates:
            raise RuntimeNavigationError("Yellow level button was not detected")
        region = max(candidates, key=lambda item: item[0])[1]
        level = self._read_level(image, region)
        return HomeLevelButton(region, level)

    def _read_level(self, image: Any, region: PixelRect) -> int:
        inset_x = max(2, round(region.width * 0.02))
        inset_y = max(2, round(region.height * 0.08))
        roi = image[
            region.top + inset_y : region.top + region.height - inset_y,
            region.left + inset_x : region.left + region.width - inset_x,
        ]
        gray = cv2.cvtColor(roi, cv2.COLOR_BGR2GRAY)
        _, binary = cv2.threshold(
            gray, 0, 255, cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU
        )
        contours, _ = cv2.findContours(
            binary, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE
        )
        glyphs: list[_Glyph] = []
        for contour in contours:
            left, _, glyph_width, glyph_height = cv2.boundingRect(contour)
            if not 0.20 * roi.shape[0] <= glyph_height <= 0.75 * roi.shape[0]:
                continue
            if glyph_width < 2 or glyph_width > glyph_height * 1.25:
                continue
            top = cv2.boundingRect(contour)[1]
            glyphs.append(
                _Glyph(
                    left,
                    glyph_width,
                    glyph_height,
                    binary[top : top + glyph_height, left : left + glyph_width],
                )
            )
        glyphs.sort(key=lambda glyph: glyph.left)
        numeric = _numeric_suffix(glyphs)
        if not numeric:
            raise OcrError("No level number was detected inside the yellow button")
        output: list[str] = []
        for glyph in numeric:
            source = _normalize_array(glyph.mask)
            scores = {
                digit: float(
                    cv2.matchTemplate(source, template, cv2.TM_CCOEFF_NORMED)[0, 0]
                )
                for digit, template in self._templates.items()
            }
            digit, score = max(scores.items(), key=lambda item: (item[1], item[0]))
            confidence = min(1.0, max(0.0, (score + 1.0) / 2.0))
            if confidence < self.minimum_digit_confidence:
                raise OcrError(
                    f"Home level digit confidence is too low: {confidence:.3f}"
                )
            output.append(digit)
        level = int("".join(output))
        if level <= 0:
            raise OcrError("Detected Home level number must be positive")
        return level


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


def _numeric_suffix(glyphs: list[_Glyph]) -> list[_Glyph]:
    if len(glyphs) < 2:
        return []
    gaps = [
        current.left - previous.right
        for previous, current in itertools.pairwise(glyphs)
    ]
    split = max(range(len(gaps)), key=gaps.__getitem__)
    suffix = glyphs[split + 1 :]
    return suffix if gaps[split] > max(3, round(glyphs[split].height * 0.25)) else []


def _normalize_mask(image: Image.Image) -> Any:
    gray = np.asarray(image.convert("L"), dtype=np.uint8)
    _, mask = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
    return _normalize_array(mask)


def _normalize_array(mask: Any) -> Any:
    contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    if not contours:
        raise OcrError("No digit foreground was detected")
    left, top, width, height = cv2.boundingRect(max(contours, key=cv2.contourArea))
    glyph = mask[top : top + height, left : left + width]
    scale = 48 / max(width, height)
    resized = cv2.resize(
        glyph,
        (max(1, round(width * scale)), max(1, round(height * scale))),
        interpolation=cv2.INTER_AREA,
    )
    normalized = np.zeros((64, 64), dtype=np.uint8)
    y = (64 - resized.shape[0]) // 2
    x = (64 - resized.shape[1]) // 2
    normalized[y : y + resized.shape[0], x : x + resized.shape[1]] = resized
    return normalized