"""Runtime-only visual controls for Home navigation and popup recovery."""

from __future__ import annotations

import io
import itertools
import time
from collections.abc import Callable
from dataclasses import dataclass
from importlib import import_module
from importlib.resources import files
from pathlib import Path
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
    ocr_crop_size: tuple[int, int] = (0, 0)


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

    def __init__(
        self,
        debug_directory: Path = Path("debug"),
        *,
        minimum_digit_confidence: float = 0.72,
        recapture: Callable[[], ScreenCapture] | None = None,
        retry_wait_seconds: float = 0.5,
        sleeper: Callable[[float], None] = time.sleep,
    ) -> None:
        if not 0.0 <= minimum_digit_confidence <= 1.0:
            raise ValueError("minimum_digit_confidence must be between zero and one")
        if retry_wait_seconds < 0:
            raise ValueError("retry_wait_seconds must not be negative")
        package = files("word_madness_bot.resources.digits")
        self._templates = {
            digit: _normalize_mask(
                Image.open(io.BytesIO(package.joinpath(f"{digit}.png").read_bytes()))
            )
            for digit in "0123456789"
        }
        self.minimum_digit_confidence = minimum_digit_confidence
        self.debug_directory = debug_directory
        self.recapture = recapture
        self.retry_wait_seconds = retry_wait_seconds
        self.sleeper = sleeper
    def detect(self, capture: ScreenCapture) -> HomeLevelButton:
        current = capture
        while True:
            image = _decode_color(current)
            region, mask, candidates = self._locate(image)
            if region is None:
                self._save_failure_debug(current, image, mask, candidates)
                raise RuntimeNavigationError("Yellow level button was not detected")
            self._save_success_debug(current, image, mask, region)
            try:
                level = self._read_level(image, region)
            except OcrError:
                if self.recapture is None:
                    raise
                self.sleeper(self.retry_wait_seconds)
                current = self.recapture()
                continue
            return HomeLevelButton(region, level, self.ocr_crop_size(region))

    def locate(self, capture: ScreenCapture) -> PixelRect:
        """Locate the button independently of its changing text."""
        region, _, _ = self._locate(_decode_color(capture))
        if region is None:
            raise RuntimeNavigationError("Yellow level button was not detected")
        return region

    def ocr_crop_size(self, region: PixelRect) -> tuple[int, int]:
        """Return the exact interior dimensions supplied to level-number OCR."""
        inset_x = max(2, round(region.width * 0.02))
        inset_y = max(2, round(region.height * 0.08))
        return region.width - 2 * inset_x, region.height - 2 * inset_y

    def _locate(
        self, image: Any
    ) -> tuple[PixelRect | None, Any, list[tuple[int, int, int, int, float]]]:
        hsv = cv2.cvtColor(image, cv2.COLOR_BGR2HSV)
        height, width = hsv.shape[:2]
        crop_left, crop_right = round(width * 0.15), round(width * 0.85)
        crop_top, crop_bottom = round(height * 0.55), round(height * 0.78)
        search_mask = cv2.inRange(
            hsv[crop_top:crop_bottom, crop_left:crop_right],
            np.array((10, 70, 120), dtype=np.uint8),
            np.array((45, 255, 255), dtype=np.uint8),
        )
        kernel_size = max(3, round(min(search_mask.shape) * 0.008))
        kernel = cv2.getStructuringElement(
            cv2.MORPH_ELLIPSE, (kernel_size, kernel_size)
        )
        search_mask = cv2.morphologyEx(search_mask, cv2.MORPH_CLOSE, kernel)
        contours, _ = cv2.findContours(
            search_mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE
        )
        mask = np.zeros((height, width), dtype=np.uint8)
        mask[crop_top:crop_bottom, crop_left:crop_right] = search_mask
        candidates = []
        for contour in contours:
            left, top, candidate_width, candidate_height = cv2.boundingRect(contour)
            candidates.append((
                crop_left + left, crop_top + top, candidate_width,
                candidate_height, float(cv2.contourArea(contour)),
            ))
        if not contours:
            return None, mask, candidates
        contour = max(contours, key=cv2.contourArea)
        if cv2.contourArea(contour) < search_mask.size * 0.01:
            return None, mask, candidates
        left, top, button_width, button_height = cv2.boundingRect(contour)
        return (
            PixelRect(crop_left + left, crop_top + top, button_width, button_height),
            mask,
            candidates,
        )

    def _save_success_debug(
        self, capture: ScreenCapture, image: Any, mask: Any, region: PixelRect
    ) -> None:
        self._save_base_debug(capture, mask)
        annotated = image.copy()
        _draw_box(annotated, region, (0, 0, 255))
        _save_png(self.debug_directory / "button_box.png", annotated)

    def _save_failure_debug(
        self,
        capture: ScreenCapture,
        image: Any,
        mask: Any,
        candidates: list[tuple[int, int, int, int, float]],
    ) -> None:
        self._save_base_debug(capture, mask)
        annotated = image.copy()
        for index, (left, top, width, height, area) in enumerate(candidates):
            _draw_box(annotated, PixelRect(left, top, width, height), (0, 0, 255))
            cv2.putText(
                annotated, f"{index}: {area:.0f}", (left, max(20, top - 8)),
                cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 0, 255), 2, cv2.LINE_AA,
            )
        _save_png(self.debug_directory / "button_candidates.png", annotated)

    def _save_base_debug(self, capture: ScreenCapture, mask: Any) -> None:
        self.debug_directory.mkdir(parents=True, exist_ok=True)
        (self.debug_directory / "home_screen.png").write_bytes(capture.data)
        _save_png(self.debug_directory / "yellow_mask.png", mask)
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


def _draw_box(image: Any, region: PixelRect, color: tuple[int, int, int]) -> None:
    cv2.rectangle(
        image,
        (region.left, region.top),
        (region.left + region.width - 1, region.top + region.height - 1),
        color,
        max(2, round(min(image.shape[:2]) * 0.003)),
    )


def _save_png(path: Path, image: Any) -> None:
    encoded, data = cv2.imencode(".png", image)
    if not encoded:
        raise RuntimeNavigationError(f"Unable to encode debug image: {path}")
    path.write_bytes(data.tobytes())

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
