"""Runtime-only visual controls for Home navigation and popup recovery."""

from __future__ import annotations

import re
import shutil
import subprocess
from collections.abc import Callable
from dataclasses import dataclass
from importlib import import_module
from importlib.resources import files
from pathlib import Path
from typing import Any, Protocol

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
    def locate(self, capture: ScreenCapture) -> PixelRect: ...

    def recognize_level(
        self, capture: ScreenCapture, region: PixelRect
    ) -> HomeLevelButton: ...

    def ocr_crop_size(self, region: PixelRect) -> tuple[int, int]: ...


class PopupCloseButtonPort(Protocol):
    def detect(self, capture: ScreenCapture) -> PixelRect | None: ...


class YellowLevelButtonDetector:
    """Locate the yellow rounded rectangle and read only its interior text."""

    def __init__(
        self,
        debug_directory: Path = Path("debug"),
        *,
        tesseract_runner: Callable[..., subprocess.CompletedProcess[bytes]] = subprocess.run,
        tesseract_executable: str | None = None,
        maximum_ocr_attempts: int = 3,
    ) -> None:
        if maximum_ocr_attempts <= 0:
            raise ValueError("maximum_ocr_attempts must be positive")
        self.debug_directory = debug_directory
        self.tesseract_runner = tesseract_runner
        self.tesseract_executable = tesseract_executable or _find_tesseract()
        self.maximum_ocr_attempts = maximum_ocr_attempts

    def detect(self, capture: ScreenCapture) -> HomeLevelButton:
        """Detect and recognize from one supplied Home Screen capture."""
        region = self.locate(capture)
        return self.recognize_level(capture, region)

    def locate(self, capture: ScreenCapture) -> PixelRect:
        """Locate the button once, without performing OCR or recapturing."""
        image = _decode_color(capture)
        region, mask, candidates = self._locate(image)
        if region is None:
            self._save_failure_debug(capture, image, mask, candidates)
            raise RuntimeNavigationError("Yellow level button was not detected")
        self._save_success_debug(capture, image, mask, region)
        return region

    def recognize_level(
        self, capture: ScreenCapture, region: PixelRect
    ) -> HomeLevelButton:
        """Read the level from the tightened interior of the detected button."""
        image = _decode_color(capture)
        ocr_region = self._ocr_region(region)
        crop = image[
            ocr_region.top : ocr_region.top + ocr_region.height,
            ocr_region.left : ocr_region.left + ocr_region.width,
        ]
        _save_png(self.debug_directory / "button_crop.png", crop)
        level = self._read_level(image, ocr_region)
        return HomeLevelButton(region, level, (ocr_region.width, ocr_region.height))

    def ocr_crop_size(self, region: PixelRect) -> tuple[int, int]:
        """Return the tightened rectangle dimensions supplied to OCR."""
        ocr_region = self._ocr_region(region)
        return ocr_region.width, ocr_region.height

    def _ocr_region(self, region: PixelRect) -> PixelRect:
        inset_x = max(1, round(region.width * 0.05))
        inset_y = (
            max(1, round(region.height * 0.30))
            if region.height > region.width * 0.30
            else 0
        )
        return PixelRect(
            region.left + inset_x,
            region.top + inset_y,
            region.width - 2 * inset_x,
            region.height - 2 * inset_y,
        )
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
        roi = image[
            region.top : region.top + region.height,
            region.left : region.left + region.width,
        ]
        gray = cv2.cvtColor(roi, cv2.COLOR_BGR2GRAY)
        upscaled = cv2.resize(
            gray,
            None,
            fx=4.0,
            fy=4.0,
            interpolation=cv2.INTER_CUBIC,
        )
        thresholded = cv2.adaptiveThreshold(
            upscaled,
            255,
            cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
            cv2.THRESH_BINARY,
            31,
            11,
        )
        encoded, png = cv2.imencode(".png", thresholded)
        if not encoded:
            raise OcrError("Unable to encode Home level OCR crop")
        command = [
            self.tesseract_executable,
            "stdin",
            "stdout",
            "--psm",
            "7",
            "-c",
            "tessedit_char_whitelist=0123456789",
        ]
        for _ in range(self.maximum_ocr_attempts):
            try:
                result = self.tesseract_runner(
                    command,
                    input=png.tobytes(),
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    check=False,
                    timeout=10.0,
                )
            except (OSError, subprocess.SubprocessError):
                continue
            digits = re.sub(r"\D", "", result.stdout.decode("utf-8", errors="ignore"))
            if result.returncode == 0 and digits:
                level = int(digits)
                if 1 <= level <= 1010:
                    return level
        raise OcrError("Home level OCR did not return an integer between 1 and 1010")

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


def _find_tesseract() -> str:
    executable = shutil.which("tesseract")
    if executable is not None:
        return executable
    standard_windows_path = Path(r"C:\Program Files\Tesseract-OCR\tesseract.exe")
    if standard_windows_path.is_file():
        return str(standard_windows_path)
    return "tesseract"

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
