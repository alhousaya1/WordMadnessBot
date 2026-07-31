"""Circle detection and letter-region extraction from binary images."""

from __future__ import annotations

from collections import deque
from dataclasses import dataclass

from PIL import Image

from word_madness_bot.domain.geometry import PixelPoint, PixelRect


@dataclass(frozen=True, slots=True)
class Circle:
    """Detected approximately circular foreground component."""

    center: PixelPoint
    radius: int
    bounds: PixelRect


@dataclass(frozen=True, slots=True)
class LetterRegion:
    """Image crop associated with a detected circle."""

    bounds: PixelRect
    image: Image.Image


def detect_circles(
    image: Image.Image, *, minimum_radius: int = 2, tolerance: float = 0.25
) -> tuple[Circle, ...]:
    """Detect filled, approximately square connected components."""
    if minimum_radius <= 0 or not 0 <= tolerance < 1:
        raise ValueError("Invalid circle detection parameters")
    circles: list[Circle] = []
    for bounds, area in _components(image.convert("1")):
        ratio = min(bounds.width, bounds.height) / max(bounds.width, bounds.height)
        fill = area / (bounds.width * bounds.height)
        radius = min(bounds.width, bounds.height) // 2
        if radius >= minimum_radius and ratio >= 1 - tolerance and fill >= 0.5:
            circles.append(
                Circle(
                    PixelPoint(bounds.left + bounds.width // 2, bounds.top + bounds.height // 2),
                    radius,
                    bounds,
                )
            )
    return tuple(sorted(circles, key=lambda circle: (circle.center.y, circle.center.x)))


def extract_letters(image: Image.Image, circles: tuple[Circle, ...]) -> tuple[LetterRegion, ...]:
    """Crop one independent image for every detected circle."""
    return tuple(
        LetterRegion(
            circle.bounds,
            image.crop(
                (circle.bounds.left, circle.bounds.top, circle.bounds.right, circle.bounds.bottom)
            ).copy(),
        )
        for circle in circles
    )


def _components(image: Image.Image) -> tuple[tuple[PixelRect, int], ...]:
    pixels = image.load()
    seen: set[tuple[int, int]] = set()
    found: list[tuple[PixelRect, int]] = []
    for y in range(image.height):
        for x in range(image.width):
            if (x, y) in seen or pixels[x, y] == 0:
                continue
            queue = deque([(x, y)])
            seen.add((x, y))
            points: list[tuple[int, int]] = []
            while queue:
                px, py = queue.popleft()
                points.append((px, py))
                for neighbor in ((px - 1, py), (px + 1, py), (px, py - 1), (px, py + 1)):
                    nx, ny = neighbor
                    if (
                        0 <= nx < image.width
                        and 0 <= ny < image.height
                        and neighbor not in seen
                        and pixels[nx, ny] != 0
                    ):
                        seen.add(neighbor)
                        queue.append(neighbor)
            xs, ys = [p[0] for p in points], [p[1] for p in points]
            found.append(
                (
                    PixelRect(min(xs), min(ys), max(xs) - min(xs) + 1, max(ys) - min(ys) + 1),
                    len(points),
                )
            )
    return tuple(found)
