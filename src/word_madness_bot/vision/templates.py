"""Small deterministic template matcher."""

from __future__ import annotations

from dataclasses import dataclass

from PIL import Image, ImageChops, ImageStat

from word_madness_bot.domain.errors import VisionError
from word_madness_bot.domain.geometry import PixelRect


@dataclass(frozen=True, slots=True)
class TemplateMatch:
    """One template match and its normalized confidence."""

    label: str
    region: PixelRect
    confidence: float


class TemplateMatcher:
    """Match grayscale templates by normalized mean absolute difference."""

    def __init__(self, *, threshold: float = 0.9, step: int = 1) -> None:
        if not 0 <= threshold <= 1 or step <= 0:
            raise ValueError("Invalid template matcher configuration")
        self.threshold = threshold
        self.step = step

    def match(
        self, image: Image.Image, template: Image.Image, *, label: str
    ) -> tuple[TemplateMatch, ...]:
        """Return non-overlapping matches at or above the threshold."""
        source, needle = image.convert("L"), template.convert("L")
        tw, th = needle.size
        if not label.strip() or tw == 0 or th == 0 or tw > source.width or th > source.height:
            raise VisionError("Template cannot be matched against this image")
        candidates: list[TemplateMatch] = []
        for y in range(0, source.height - th + 1, self.step):
            for x in range(0, source.width - tw + 1, self.step):
                difference = ImageChops.difference(source.crop((x, y, x + tw, y + th)), needle)
                confidence = 1.0 - ImageStat.Stat(difference).mean[0] / 255.0
                if confidence >= self.threshold:
                    region = PixelRect(x, y, tw, th)
                    if not any(_overlaps(region, item.region) for item in candidates):
                        candidates.append(TemplateMatch(label, region, confidence))
        return tuple(candidates)


def _overlaps(left: PixelRect, right: PixelRect) -> bool:
    return (
        left.left < right.right
        and left.right > right.left
        and left.top < right.bottom
        and left.bottom > right.top
    )
