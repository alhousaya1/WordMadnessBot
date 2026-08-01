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
    """Confirm that an answer-board change persists after gesture animations settle."""

    def verify(
        self,
        before: ScreenCapture,
        after: ScreenCapture,
        confirmation: ScreenCapture,
    ) -> AcceptanceResult: ...


class ImageDifferenceWordAcceptanceVerifier:
    """Accept only persistent answer-board changes observed in two post-swipe frames."""

    def __init__(self, *, minimum_changed_ratio: float = 0.0005) -> None:
        if not 0.0 < minimum_changed_ratio < 1.0:
            raise ValueError("minimum_changed_ratio must be between zero and one")
        self.minimum_changed_ratio = minimum_changed_ratio

    def verify(
        self,
        before: ScreenCapture,
        after: ScreenCapture,
        confirmation: ScreenCapture,
    ) -> AcceptanceResult:
        """Reject transient traces by requiring the board change in both later frames."""
        if before.size != after.size or before.size != confirmation.size:
            raise WordExecutionError("Acceptance screenshots have different sizes")
        before_gray = _decode_grayscale(before)
        after_gray = _decode_grayscale(after)
        confirmation_gray = _decode_grayscale(confirmation)
        height, width = before_gray.shape
        left, right = round(width * 0.12), round(width * 0.88)
        top, bottom = round(height * 0.08), round(height * 0.60)
        before_board = before_gray[top:bottom, left:right]
        after_board = after_gray[top:bottom, left:right]
        confirmation_board = confirmation_gray[top:bottom, left:right]
        first_change = cv2.absdiff(before_board, after_board) >= 25
        confirmed_change = cv2.absdiff(before_board, confirmation_board) >= 25
        persistent_change = np.logical_and(first_change, confirmed_change)
        persistent_ratio = float(np.count_nonzero(persistent_change) / persistent_change.size)
        persistent_difference = np.where(
            persistent_change,
            cv2.absdiff(before_board, confirmation_board),
            0,
        )
        return AcceptanceResult(
            persistent_ratio >= self.minimum_changed_ratio,
            persistent_ratio,
            float(np.mean(persistent_difference)),
        )

@dataclass(frozen=True, slots=True)
class WordExecutionResult:
    """Complete evidence for exactly one attempted solution word."""

    word: str
    duration_ms: int
    coordinates: tuple[PixelPoint, ...]
    acceptance: AcceptanceResult
    elapsed_seconds: float
    timestamps_ms: tuple[int, ...]
    backend_command: tuple[str, ...]

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
            "timestamps_ms": list(self.timestamps_ms),
            "backend_command": list(self.backend_command),
        }


class SingleWordExecutor:
    """Execute only the first planned word, capture evidence, and then return."""

    def __init__(
        self,
        android: AndroidPort,
        verifier: WordAcceptanceVerifier,
        *,
        animation_wait_seconds: float = 1.5,
        confirmation_wait_seconds: float = 0.5,
        sleeper: Sleeper = time.sleep,
        clock: Clock = time.monotonic,
    ) -> None:
        if animation_wait_seconds < 0:
            raise ValueError("animation_wait_seconds cannot be negative")
        if confirmation_wait_seconds < 0:
            raise ValueError("confirmation_wait_seconds cannot be negative")
        self.android = android
        self.verifier = verifier
        self.animation_wait_seconds = animation_wait_seconds
        self.confirmation_wait_seconds = confirmation_wait_seconds
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
        confirmation_path = debug_directory / "word_confirmed.png"
        swipe_path = debug_directory / "swipe.json"
        try:
            save_screenshot(before.data, before_path)
            receipt = self.android.swipe(
                SwipePath(first.coordinates, first.duration_ms)
            )
            self.sleeper(self.animation_wait_seconds)
            after = self.android.capture_screenshot()
            save_screenshot(after.data, after_path)
            self.sleeper(self.confirmation_wait_seconds)
            confirmation = self.android.capture_screenshot()
            save_screenshot(confirmation.data, confirmation_path)
            acceptance = self.verifier.verify(before, after, confirmation)
            result = WordExecutionResult(
                first.word,
                first.duration_ms,
                first.coordinates,
                acceptance,
                self.clock() - started,
                receipt.timestamps_ms,
                receipt.backend_command,
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
