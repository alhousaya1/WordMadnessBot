"""Resolution-independent recognition of level numbers shown by the game."""

from __future__ import annotations

import io
import itertools
import re
import shutil
import subprocess
from dataclasses import dataclass
from importlib import import_module
from importlib.resources import files
from pathlib import Path
from typing import Any, Protocol

from PIL import Image, ImageDraw

from word_madness_bot.domain.errors import OcrError
from word_madness_bot.domain.geometry import PixelRect, ScreenSize
from word_madness_bot.domain.models import ScreenCapture

cv2: Any = import_module("cv2")
np: Any = import_module("numpy")

REFERENCE_SIZE = ScreenSize(1440, 3120)
# Tight text band inside the Home yellow button. The old 228,1805,984,344 crop
# also contained the difficulty banner, button edges, and coin badge.
HOME_LEVEL_TEXT_REFERENCE = PixelRect(360, 1940, 720, 170)
LEVEL_TITLE_REFERENCE = PixelRect(504, 109, 432, 219)
_LEVEL_PATTERN = re.compile(r"(?i)(?:LEVEL\s+)?([0-9]+)")


class LevelNumberRecognitionPort(Protocol):
    """Runtime boundary for extracting a level identifier from a screenshot."""

    def recognize(self, capture: ScreenCapture) -> int: ...


@dataclass(frozen=True, slots=True)
class _Glyph:
    left: int
    width: int
    height: int
    mask: Any

    @property
    def right(self) -> int:
        return self.left + self.width


def scale_reference_rect(rect: PixelRect, size: ScreenSize) -> PixelRect:
    """Scale a 1440x3120 reference rectangle to an arbitrary capture size."""
    left = round(rect.left * size.width / REFERENCE_SIZE.width)
    top = round(rect.top * size.height / REFERENCE_SIZE.height)
    right = round((rect.left + rect.width) * size.width / REFERENCE_SIZE.width)
    bottom = round((rect.top + rect.height) * size.height / REFERENCE_SIZE.height)
    return PixelRect(left, top, max(1, right - left), max(1, bottom - top))


def parse_level_number(text: str) -> int | None:
    """Strictly parse either ``Level N`` or digits alone."""
    match = _LEVEL_PATTERN.fullmatch(text.strip())
    if match is None:
        return None
    number = int(match.group(1))
    return number if number > 0 else None


def _candidate_digits(text: str) -> str | None:
    """Return the complete detected digit sequence for one OCR candidate."""
    match = _LEVEL_PATTERN.fullmatch(text.strip())
    if match is None:
        return None
    digits = match.group(1)
    return digits if digits and int(digits) > 0 else None


def _select_best_level_candidate(
    candidates: list[str],
    supported_levels: frozenset[int] | None,
) -> int | None:
    """Select a complete supported level and reject shorter OCR fragments.

    A candidate such as ``4`` is considered a likely fragment when the same
    recognition pass also produced a supported candidate such as ``418``.
    The function does not invent, increment, or otherwise guess a level.
    """
    parsed: list[tuple[str, int, int]] = []

    for candidate in candidates:
        digits = _candidate_digits(candidate)
        if digits is None:
            continue

        number = int(digits)
        if supported_levels is not None and number not in supported_levels:
            continue

        parsed.append((digits, number, candidates.count(candidate)))

    if not parsed:
        return None

    def score(item: tuple[str, int, int]) -> tuple[int, int, int]:
        digits, _number, occurrences = item

        fragment_of_longer = any(
            digits != other_digits
            and len(other_digits) > len(digits)
            and digits in other_digits
            for other_digits, _other_number, _other_occurrences in parsed
        )

        complete_over_fragment = 0 if fragment_of_longer else 1

        return (
            complete_over_fragment,
            occurrences,
            len(digits),
        )

    return max(parsed, key=score)[1]


class LevelNumberRecognizer:
    """Recognize a supported level using templates and optional Tesseract."""

    def __init__(
        self,
        *,
        minimum_confidence: float = 0.72,
        supported_levels: frozenset[int] | None = None,
        debug_directory: Path = Path("debug"),
    ) -> None:
        if not 0.0 <= minimum_confidence <= 1.0:
            raise ValueError("minimum_confidence must be between zero and one")
        package = files("word_madness_bot.resources.digits")
        self._templates = {
            digit: _normalize_mask(
                Image.open(io.BytesIO(package.joinpath(f"{digit}.png").read_bytes()))
            )
            for digit in "0123456789"
        }
        self.minimum_confidence = minimum_confidence
        self.supported_levels = supported_levels
        self.debug_directory = debug_directory
        self.last_candidates: tuple[str, ...] = ()
        self.last_crop: PixelRect | None = None

    def recognize_home(self, capture: ScreenCapture) -> int:
        """Recognize the level specifically from a confirmed home screen."""
        self._prefer_home_crop = True
        try:
            return self.recognize(capture)
        finally:
            self._prefer_home_crop = False

    def recognize(self, capture: ScreenCapture) -> int:
        """Return a database-supported level number without guessing."""
        try:
            source = Image.open(io.BytesIO(capture.data)).convert("RGB")
        except (OSError, ValueError) as error:
            raise OcrError("Unable to decode screenshot for level recognition") from error
        button = _yellow_level_button(source)
        prefer_home_crop = bool(getattr(self, "_prefer_home_crop", False))

        if button is not None:
            crop_rect = PixelRect(
                button.left + round(button.width * 0.11),
                button.top + round(button.height * 0.05),
                max(1, round(button.width * 0.79)),
                max(1, round(button.height * 0.85)),
            )
        elif prefer_home_crop:
            crop_rect = scale_reference_rect(
                HOME_LEVEL_TEXT_REFERENCE,
                capture.size,
            )
        else:
            crop_rect = scale_reference_rect(
                LEVEL_TITLE_REFERENCE,
                capture.size,
            )
        self.last_crop = crop_rect
        crop = source.crop(
            (
                crop_rect.left,
                crop_rect.top,
                crop_rect.left + crop_rect.width,
                crop_rect.top + crop_rect.height,
            )
        )
        variants = _preprocess(crop)
        self._save_debug(source, crop_rect, crop, variants)

        candidates: list[str] = []
        for name in ("threshold", "inverted"):
            template = self._recognize_template(np.asarray(variants[name], dtype=np.uint8))
            if template is not None:
                candidates.append(template)
        candidates.extend(_recognize_with_tesseract(variants))

        self.last_candidates = tuple(dict.fromkeys(candidates))

        selected = _select_best_level_candidate(
            candidates,
            self.supported_levels,
        )
        if selected is not None:
            return selected

        if not self.last_candidates:
            raise OcrError("No level-number OCR candidates were returned")
        raise OcrError("Home level OCR did not return a supported 'Level <integer>'")

    def _recognize_template(self, binary: Any) -> str | None:
        contours, _ = cv2.findContours(binary, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        glyphs: list[_Glyph] = []
        for contour in contours:
            x, y, glyph_width, glyph_height = cv2.boundingRect(contour)
            if not 0.18 * binary.shape[0] <= glyph_height <= 0.90 * binary.shape[0]:
                continue
            if glyph_width < 2 or glyph_width > glyph_height * 1.25:
                continue
            glyphs.append(
                _Glyph(
                    x,
                    glyph_width,
                    glyph_height,
                    binary[y : y + glyph_height, x : x + glyph_width],
                )
            )
        glyphs.sort(key=lambda item: item.left)
        numeric = _numeric_suffix(glyphs)
        if not numeric:
            return None
        output: list[str] = []
        for glyph in numeric:
            source = _normalize_array(glyph.mask)
            scores = {
                digit: float(cv2.matchTemplate(source, template, cv2.TM_CCOEFF_NORMED)[0, 0])
                for digit, template in self._templates.items()
            }
            digit, score = max(scores.items(), key=lambda item: (item[1], item[0]))
            confidence = min(1.0, max(0.0, (score + 1.0) / 2.0))
            if confidence < self.minimum_confidence:
                return None
            output.append(digit)
        return "".join(output)

    def _save_debug(
        self,
        source: Image.Image,
        rect: PixelRect,
        crop: Image.Image,
        variants: dict[str, Image.Image],
    ) -> None:
        try:
            self.debug_directory.mkdir(parents=True, exist_ok=True)
            annotated = source.copy()
            ImageDraw.Draw(annotated).rectangle(
                (rect.left, rect.top, rect.left + rect.width, rect.top + rect.height),
                outline="red",
                width=max(2, round(source.width / 240)),
            )
            annotated.save(self.debug_directory / "home_level_annotated.png")
            crop.save(self.debug_directory / "home_level_crop.png")
            for name, image in variants.items():
                image.save(self.debug_directory / f"home_level_{name}.png")
        except OSError as error:
            raise OcrError("Unable to save home level OCR debug artifacts") from error


def _preprocess(crop: Image.Image) -> dict[str, Image.Image]:
    """Create multiple OCR views while preserving the UI font."""
    scale = max(2, round(1200 / max(1, crop.width)))
    upscaled = crop.resize(
        (crop.width * scale, crop.height * scale),
        Image.Resampling.LANCZOS,
    )

    gray = upscaled.convert("L")
    gray_array = np.asarray(gray, dtype=np.uint8)

    clahe = cv2.createCLAHE(
        clipLimit=2.5,
        tileGridSize=(8, 8),
    ).apply(gray_array)

    blurred = cv2.GaussianBlur(clahe, (0, 0), 1.1)
    sharpened = cv2.addWeighted(clahe, 1.8, blurred, -0.8, 0)

    _, threshold = cv2.threshold(
        sharpened,
        0,
        255,
        cv2.THRESH_BINARY + cv2.THRESH_OTSU,
    )

    adaptive = cv2.adaptiveThreshold(
        sharpened,
        255,
        cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
        cv2.THRESH_BINARY,
        41,
        9,
    )

    return {
        "original": upscaled,
        "upscaled": upscaled,
        "gray": gray,
        "clahe": Image.fromarray(clahe),
        "sharpened": Image.fromarray(sharpened),
        "threshold": Image.fromarray(threshold),
        "inverted": Image.fromarray(cv2.bitwise_not(threshold)),
        "adaptive": Image.fromarray(adaptive),
        "adaptive_inverted": Image.fromarray(
            cv2.bitwise_not(adaptive)
        ),
    }


def _recognize_with_tesseract(
    variants: dict[str, Image.Image],
) -> list[str]:
    executable = shutil.which("tesseract")
    if executable is None:
        return []

    candidates: list[str] = []

    for name in (
        "original",
        "gray",
        "clahe",
        "sharpened",
        "threshold",
        "inverted",
        "adaptive",
        "adaptive_inverted",
    ):
        image = variants.get(name)
        if image is None:
            continue

        encoded = io.BytesIO()
        image.save(encoded, format="PNG")
        image_bytes = encoded.getvalue()

        for page_mode in ("6", "7", "11", "13"):
            for whitelist in (
                "LevelLEVEL 0123456789",
                "0123456789",
            ):
                try:
                    result = subprocess.run(
                        [
                            executable,
                            "stdin",
                            "stdout",
                            "--psm",
                            page_mode,
                            "-c",
                            f"tessedit_char_whitelist={whitelist}",
                        ],
                        input=image_bytes,
                        capture_output=True,
                        check=False,
                        timeout=5.0,
                    )
                except (OSError, subprocess.SubprocessError):
                    continue

                if result.returncode != 0:
                    continue

                raw_text = result.stdout.decode(
                    "utf-8",
                    errors="replace",
                ).strip()

                if not raw_text:
                    continue

                candidates.append(raw_text)

                for digits in re.findall(r"[0-9]+", raw_text):
                    candidates.append(digits)

    return candidates


def _yellow_level_button(image: Image.Image) -> PixelRect | None:
    hsv = cv2.cvtColor(np.asarray(image), cv2.COLOR_RGB2HSV)
    mask = cv2.inRange(
        hsv, np.array((15, 100, 120), dtype=np.uint8), np.array((42, 255, 255), dtype=np.uint8)
    )
    height, width = mask.shape
    region = mask[
        round(height * 0.52) : round(height * 0.78), round(width * 0.15) : round(width * 0.85)
    ]
    contours, _ = cv2.findContours(region, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    candidates: list[tuple[float, PixelRect]] = []
    region_left = round(width * 0.15)
    region_top = round(height * 0.52)
    for contour in contours:
        area = float(cv2.contourArea(contour))
        if area < width * height * 0.015:
            continue
        left, top, candidate_width, candidate_height = cv2.boundingRect(contour)
        candidates.append(
            (
                area,
                PixelRect(
                    region_left + int(left),
                    region_top + int(top),
                    int(candidate_width),
                    int(candidate_height),
                ),
            )
        )
    return max(candidates, key=lambda item: item[0])[1] if candidates else None


def _numeric_suffix(glyphs: list[_Glyph]) -> list[_Glyph]:
    if len(glyphs) < 2:
        return []
    gaps = [right.left - left.right for left, right in itertools.pairwise(glyphs)]
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

