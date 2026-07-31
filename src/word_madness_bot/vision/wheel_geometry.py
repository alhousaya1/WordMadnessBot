"""Computer-vision detection and debug rendering for the circular letter wheel."""

from __future__ import annotations

import json
import math
from dataclasses import dataclass
from importlib import import_module
from pathlib import Path
from typing import Any, Protocol

from word_madness_bot.domain.errors import WheelGeometryDetectionError
from word_madness_bot.domain.geometry import PixelPoint
from word_madness_bot.domain.models import ScreenCapture

cv2: Any = import_module("cv2")
np: Any = import_module("numpy")


@dataclass(frozen=True, slots=True)
class LetterPosition:
    """One detected glyph position with a stable clockwise index."""

    index: int
    point: PixelPoint

    def __post_init__(self) -> None:
        if self.index < 0:
            raise ValueError("Letter position index cannot be negative")


@dataclass(frozen=True, slots=True)
class LetterWheelGeometry:
    """Detected wheel circle and clockwise letter positions."""

    center: PixelPoint
    radius: int
    letters: tuple[LetterPosition, ...]

    def __post_init__(self) -> None:
        if self.radius <= 0:
            raise ValueError("Wheel radius must be positive")
        if tuple(position.index for position in self.letters) != tuple(range(len(self.letters))):
            raise ValueError("Letter position indexes must be contiguous from zero")

    def to_dict(self) -> dict[str, object]:
        """Return a JSON-compatible debug representation."""
        return {
            "wheel_center": {"x": self.center.x, "y": self.center.y},
            "radius": self.radius,
            "letter_coordinates": [
                {"index": item.index, "x": item.point.x, "y": item.point.y}
                for item in self.letters
            ],
            "number_of_letters": len(self.letters),
        }


class WheelGeometryDetector(Protocol):
    """Runtime boundary for replaceable wheel geometry detection."""

    def detect(self, capture: ScreenCapture) -> LetterWheelGeometry: ...

    def annotate(self, capture: ScreenCapture, geometry: LetterWheelGeometry) -> bytes: ...


class LetterWheelDetector:
    """Detect wheel and glyph positions using contours and image proportions."""

    def detect(self, capture: ScreenCapture) -> LetterWheelGeometry:
        """Detect the wheel circle and clockwise glyph centers."""
        image = _decode(capture.data)
        gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
        center, radius = _detect_wheel(gray)
        points = _detect_letter_positions(gray, center, radius)
        if len(points) < 3:
            raise WheelGeometryDetectionError(
                f"Expected at least three letter positions, detected {len(points)}"
            )
        ordered = sorted(points, key=lambda point: _clockwise_angle(point, center))
        return LetterWheelGeometry(
            center=center,
            radius=radius,
            letters=tuple(
                LetterPosition(index=index, point=point)
                for index, point in enumerate(ordered)
            ),
        )

    def annotate(self, capture: ScreenCapture, geometry: LetterWheelGeometry) -> bytes:
        """Render the detected circle, center, and numbered positions as PNG."""
        image = _decode(capture.data)
        center = (geometry.center.x, geometry.center.y)
        thickness = max(2, geometry.radius // 100)
        cv2.circle(image, center, geometry.radius, (0, 255, 0), thickness)
        cv2.circle(image, center, max(5, thickness * 2), (0, 0, 255), -1)
        font_scale = max(0.7, geometry.radius / 450)
        for position in geometry.letters:
            point = (position.point.x, position.point.y)
            cv2.circle(image, point, max(8, thickness * 3), (255, 0, 0), thickness)
            cv2.putText(
                image,
                str(position.index),
                (point[0] + 12, point[1] - 12),
                cv2.FONT_HERSHEY_SIMPLEX,
                font_scale,
                (0, 0, 255),
                max(2, thickness),
                cv2.LINE_AA,
            )
        success, encoded = cv2.imencode(".png", image)
        if not success:
            raise WheelGeometryDetectionError("Unable to encode annotated wheel image")
        return bytes(encoded)


def save_wheel_debug_artifacts(
    directory: Path,
    capture: ScreenCapture,
    geometry: LetterWheelGeometry,
    detector: WheelGeometryDetector,
) -> tuple[Path, Path]:
    """Save annotated PNG and stable JSON geometry debug artifacts."""
    annotated_path = directory / "letter-wheel-annotated.png"
    json_path = directory / "letter-wheel-geometry.json"
    try:
        directory.mkdir(parents=True, exist_ok=True)
        annotated_path.write_bytes(detector.annotate(capture, geometry))
        json_path.write_text(
            json.dumps(geometry.to_dict(), indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
    except OSError as error:
        raise WheelGeometryDetectionError("Unable to save wheel debug artifacts") from error
    return annotated_path, json_path


def _decode(data: bytes) -> Any:
    encoded = np.frombuffer(data, dtype=np.uint8)
    image = cv2.imdecode(encoded, cv2.IMREAD_COLOR)
    if image is None:
        raise WheelGeometryDetectionError("Unable to decode screenshot for wheel detection")
    return image


def _detect_wheel(gray: Any) -> tuple[PixelPoint, int]:
    height, width = gray.shape[:2]
    roi_top = height // 2
    roi = gray[roi_top:, :]
    otsu_threshold, _ = cv2.threshold(
        roi, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU
    )
    bright_threshold = max(150, min(210, round(otsu_threshold) + 40))
    _, binary = cv2.threshold(roi, bright_threshold, 255, cv2.THRESH_BINARY)
    kernel_size = max(5, round(width * 0.02))
    if kernel_size % 2 == 0:
        kernel_size += 1
    kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (kernel_size, kernel_size))
    binary = cv2.morphologyEx(binary, cv2.MORPH_CLOSE, kernel)
    contours, _ = cv2.findContours(binary, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

    candidates: list[tuple[float, Any]] = []
    for contour in contours:
        area = float(cv2.contourArea(contour))
        perimeter = float(cv2.arcLength(contour, True))
        if perimeter <= 0:
            continue
        (_, _), enclosing_radius = cv2.minEnclosingCircle(contour)
        circularity = 4 * math.pi * area / (perimeter * perimeter)
        if (
            width * 0.15 <= enclosing_radius <= width * 0.48
            and circularity >= 0.7
            and area >= width * width * 0.15
        ):
            candidates.append((area * circularity, contour))
    if not candidates:
        raise WheelGeometryDetectionError("Circular letter wheel was not detected")

    contour = max(candidates, key=lambda item: item[0])[1]
    (center_x, center_y), radius = cv2.minEnclosingCircle(contour)
    return PixelPoint(round(center_x), round(center_y) + roi_top), round(radius)


def _detect_letter_positions(
    gray: Any,
    center: PixelPoint,
    radius: int,
) -> tuple[PixelPoint, ...]:
    mask = np.zeros(gray.shape, dtype=np.uint8)
    cv2.circle(mask, (center.x, center.y), round(radius * 0.82), 255, -1)
    dark = cv2.inRange(gray, 0, 115)
    dark = cv2.bitwise_and(dark, mask)
    contours, _ = cv2.findContours(dark, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

    candidates: list[tuple[float, PixelPoint]] = []
    for contour in contours:
        area = float(cv2.contourArea(contour))
        left, top, width, height = cv2.boundingRect(contour)
        point = PixelPoint(left + width // 2, top + height // 2)
        distance = math.hypot(point.x - center.x, point.y - center.y)
        aspect_ratio = width / height if height else 0.0
        if (
            radius * radius * 0.00025 <= area <= radius * radius * 0.15
            and radius * 0.008 <= width <= radius * 0.4
            and radius * 0.035 <= height <= radius * 0.4
            and 0.04 <= aspect_ratio <= 2.0
            and radius * 0.2 <= distance <= radius * 0.9
        ):
            candidates.append((area, point))

    selected: list[tuple[float, PixelPoint]] = []
    for area, point in sorted(candidates, reverse=True, key=lambda item: item[0]):
        if all(
            math.hypot(point.x - existing.x, point.y - existing.y) >= radius * 0.16
            for _, existing in selected
        ):
            selected.append((area, point))
    return tuple(point for _, point in selected)


def _clockwise_angle(point: PixelPoint, center: PixelPoint) -> float:
    """Return an angle with zero at twelve o'clock, increasing clockwise."""
    return math.atan2(point.x - center.x, center.y - point.y) % (2 * math.pi)
