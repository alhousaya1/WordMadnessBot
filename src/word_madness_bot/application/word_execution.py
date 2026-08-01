"""Single-word execution and before/after acceptance verification."""

from __future__ import annotations

import io
import json
import time
from collections.abc import Callable
from dataclasses import dataclass
from importlib import import_module
from pathlib import Path
from typing import Any, Protocol

from PIL import Image

from word_madness_bot.application.ports.android import AndroidPort
from word_madness_bot.application.solution_planning import LevelSolutionPlan
from word_madness_bot.domain.errors import WordExecutionError
from word_madness_bot.domain.geometry import PixelPoint
from word_madness_bot.domain.models import ScreenCapture, SwipePath
from word_madness_bot.infrastructure.adb.screenshot import save_screenshot

cv2: Any = import_module("cv2")
np: Any = import_module("numpy")
Clock = Callable[[], float]
Sleeper = Callable[[float], None]


@dataclass(frozen=True, slots=True)
class AcceptanceResult:
    """Visual evidence that the level board changed after a submitted word."""

    accepted: bool
    changed_pixel_ratio: float
    mean_absolute_difference: float


class WordAcceptanceVerifier(Protocol):
    """Compare level state immediately before and after a word gesture."""

    def verify(self, before: ScreenCapture, after: ScreenCapture) -> AcceptanceResult: ...


class ImageDifferenceWordAcceptanceVerifier:
    """Detect accepted words through meaningful changes in the answer-board region."""

    def __init__(self, *, minimum_changed_ratio: float = 0.0005) -> None:
        if not 0.0 < minimum_changed_ratio < 1.0:
            raise ValueError("minimum_changed_ratio must be between zero and one")
        self.minimum_changed_ratio = minimum_changed_ratio

    def verify(self, before: ScreenCapture, after: ScreenCapture) -> AcceptanceResult:
        """Compare resolution-independent answer-board crops from two screenshots."""
        if before.size != after.size:
            raise WordExecutionError("Before and after screenshots have different sizes")
        before_gray = _decode_grayscale(before)
        after_gray = _decode_grayscale(after)
        height, width = before_gray.shape
        left, right = round(width * 0.12), round(width * 0.88)
        top, bottom = round(height * 0.08), round(height * 0.60)
        difference = cv2.absdiff(
            before_gray[top:bottom, left:right],
            after_gray[top:bottom, left:right],
        )
        changed_ratio = float(np.count_nonzero(difference >= 25) / difference.size)
        mean_difference = float(np.mean(difference))
        return AcceptanceResult(
            changed_ratio >= self.minimum_changed_ratio,
            changed_ratio,
            mean_difference,
        )


@dataclass(frozen=True, slots=True)
class WordExecutionResult:
    """Complete evidence for exactly one attempted solution word."""

    word: str
    duration_ms: int
    coordinates: tuple[PixelPoint, ...]
    acceptance: AcceptanceResult
    elapsed_seconds: float

    def to_dict(self) -> dict[str, object]:
        return {
            "word": self.word,
            "duration_ms": self.duration_ms,
            "coordinates": [{"x": point.x, "y": point.y} for point in self.coordinates],
            "accepted": self.acceptance.accepted,
            "verification": {
                "changed_pixel_ratio": self.acceptance.changed_pixel_ratio,
                "mean_absolute_difference": self.acceptance.mean_absolute_difference,
            },
            "elapsed_seconds": self.elapsed_seconds,
        }


class SingleWordExecutor:
    """Execute only the first planned word, capture evidence, and then return."""

    def __init__(
        self,
        android: AndroidPort,
        verifier: WordAcceptanceVerifier,
        *,
        animation_wait_seconds: float = 1.5,
        sleeper: Sleeper = time.sleep,
        clock: Clock = time.monotonic,
    ) -> None:
        if animation_wait_seconds < 0:
            raise ValueError("animation_wait_seconds cannot be negative")
        self.android = android
        self.verifier = verifier
        self.animation_wait_seconds = animation_wait_seconds
        self.sleeper = sleeper
        self.clock = clock

    def execute(
        self,
        plan: LevelSolutionPlan,
        before: ScreenCapture,
        debug_directory: Path,
    ) -> WordExecutionResult:
        """Attempt the first solution and never inspect or execute later solutions."""
        if not plan.solutions:
            raise WordExecutionError("Level solution plan contains no words")
        first = plan.solutions[0]
        started = self.clock()
        before_path = debug_directory / "word_before.png"
        after_path = debug_directory / "word_after.png"
        swipe_path = debug_directory / "swipe.json"
        try:
            save_screenshot(before.data, before_path)
            self.android.swipe(SwipePath(first.coordinates, first.duration_ms))
            self.sleeper(self.animation_wait_seconds)
            after = self.android.capture_screenshot()
            save_screenshot(after.data, after_path)
            acceptance = self.verifier.verify(before, after)
            result = WordExecutionResult(
                first.word,
                first.duration_ms,
                first.coordinates,
                acceptance,
                self.clock() - started,
            )
            swipe_path.write_text(
                json.dumps(result.to_dict(), indent=2, sort_keys=True) + "\n",
                encoding="utf-8",
            )
        except WordExecutionError:
            raise
        except OSError as error:
            raise WordExecutionError("Unable to save single-word debug evidence") from error
        return result


def _decode_grayscale(capture: ScreenCapture) -> Any:
    try:
        return np.asarray(Image.open(io.BytesIO(capture.data)).convert("L"), dtype=np.uint8)
    except (OSError, ValueError) as error:
        raise WordExecutionError(
            "Unable to decode screenshot for acceptance verification"
        ) from error
