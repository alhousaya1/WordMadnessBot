"""Configuration-controlled rendering of optional vision diagnostics."""

import logging
from pathlib import Path

from PIL import Image, ImageDraw

from word_madness_bot.config.settings import Settings
from word_madness_bot.domain.models import CircleDetection, DetectedLetter, TemplateMatch
from word_madness_bot.vision.preprocessing import ImageArray

_LOGGER = logging.getLogger(__name__)


class DebugRenderer:
    """Persist annotated images only when runtime configuration enables it."""

    def __init__(self, settings: Settings) -> None:
        self._enabled = settings.save_debug_images
        self._output_directory = settings.debug_directory

    @property
    def enabled(self) -> bool:
        """Return whether rendering is enabled by configuration."""

        return self._enabled

    def render(
        self,
        image: ImageArray,
        filename: str,
        *,
        circle: CircleDetection | None = None,
        letters: tuple[DetectedLetter, ...] = (),
        matches: tuple[TemplateMatch, ...] = (),
    ) -> Path | None:
        """Draw supplied detections and return the saved path when enabled."""

        if not self._enabled:
            return None
        safe_name = Path(filename).name
        if not safe_name.lower().endswith(".png"):
            safe_name = f"{safe_name}.png"
        self._output_directory.mkdir(parents=True, exist_ok=True)
        output_path = self._output_directory / safe_name
        canvas = Image.fromarray(image).convert("RGB")
        draw = ImageDraw.Draw(canvas)
        if circle is not None:
            x, y, radius = circle.center.x, circle.center.y, circle.radius
            draw.ellipse((x - radius, y - radius, x + radius, y + radius), outline="lime", width=4)
            draw.text((x - radius, y - radius), f"{circle.confidence:.2f}", fill="lime")
        for letter in letters:
            x, y = letter.center.x, letter.center.y
            draw.ellipse((x - 8, y - 8, x + 8, y + 8), outline="yellow", width=3)
            draw.text((x + 10, y), f"{letter.character} {letter.confidence:.2f}", fill="yellow")
        for match in matches:
            box = match.region
            draw.rectangle((box.left, box.top, box.right, box.bottom), outline="cyan", width=3)
            draw.text((box.left, box.top), f"{match.confidence:.2f}", fill="cyan")
        canvas.save(output_path, format="PNG")
        _LOGGER.debug("Saved vision debug image: %s", output_path)
        return output_path
