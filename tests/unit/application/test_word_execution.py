from __future__ import annotations

import io
import json
from pathlib import Path

import pytest
from PIL import Image, ImageDraw

from word_madness_bot.application.solution_planning import LevelSolutionPlan, PlannedSolution
from word_madness_bot.application.word_execution import (
    ImageDifferenceWordAcceptanceVerifier,
    SingleWordExecutor,
)
from word_madness_bot.domain.errors import WordExecutionError
from word_madness_bot.domain.geometry import PixelPoint, ScreenSize
from word_madness_bot.domain.models import (
    ScreenCapture,
    SwipeExecutionReceipt,
    SwipePath,
)


def _capture(*, changed: bool = False) -> ScreenCapture:
    image = Image.new("L", (400, 800), 80)
    if changed:
        ImageDraw.Draw(image).rectangle((100, 150, 180, 210), fill=240)
    output = io.BytesIO()
    image.save(output, format="PNG")
    return ScreenCapture(output.getvalue(), ScreenSize(400, 800))


def _plan() -> LevelSolutionPlan:
    return LevelSolutionPlan(
        1,
        tuple("ABC"),
        (
            PlannedSolution(
                "AB",
                (0, 1),
                (PixelPoint(100, 600), PixelPoint(200, 650)),
                250,
            ),
            PlannedSolution(
                "CAB",
                (2, 0, 1),
                (PixelPoint(300, 600), PixelPoint(100, 600), PixelPoint(200, 650)),
                360,
            ),
        ),
    )


class Android:
    def __init__(self, after: ScreenCapture | tuple[ScreenCapture, ...]) -> None:
        self.afters = iter(after if isinstance(after, tuple) else (after,))
        self.swipes: list[SwipePath] = []
        self.captures = 0

    def swipe(self, path: SwipePath) -> SwipeExecutionReceipt:
        self.swipes.append(path)
        return SwipeExecutionReceipt(("fake",), (0, path.duration_ms))

    def capture_screenshot(self) -> ScreenCapture:
        self.captures += 1
        return next(self.afters)

    def __getattr__(self, name: str) -> object:
        return lambda *args, **kwargs: None


def test_verifier_accepts_answer_board_change_and_rejects_identical_state() -> None:
    verifier = ImageDifferenceWordAcceptanceVerifier()
    before = _capture()
    changed = _capture(changed=True)
    assert verifier.verify(before, changed, changed).accepted is True
    assert verifier.verify(before, changed, before).accepted is False


def test_executor_attempts_only_first_word_and_saves_all_evidence(tmp_path: Path) -> None:
    android = Android(_capture(changed=True))
    sleeps: list[float] = []
    executor = SingleWordExecutor(
        android,  # type: ignore[arg-type]
        ImageDifferenceWordAcceptanceVerifier(),
        sleeper=sleeps.append,
        clock=iter((1.0, 2.0)).__next__,
    )
    result = executor.execute(_plan(), _capture(), tmp_path)
    assert result.word == "AB"
    assert result.acceptance.accepted is True
    assert android.swipes == [SwipePath((PixelPoint(100, 600), PixelPoint(200, 650)), 250)]
    assert android.captures == 1
    assert sleeps == [1.2]
    assert (tmp_path / "word_before.png").exists()
    assert (tmp_path / "word_after.png").exists()
    assert (tmp_path / "word_confirmed.png").exists()
    payload = json.loads((tmp_path / "swipe.json").read_text(encoding="utf-8"))
    assert payload["word"] == "AB"
    assert payload["accepted"] is True
    assert payload["duration_ms"] == 250
    assert payload["timestamps_ms"] == [0, 250]
    assert payload["backend_command"] == ["fake"]


def test_executor_retries_once_after_rejection(tmp_path: Path) -> None:
    before = _capture()
    android = Android((before, _capture(changed=True)))
    sleeps: list[float] = []
    executor = SingleWordExecutor(
        android,  # type: ignore[arg-type]
        ImageDifferenceWordAcceptanceVerifier(),
        sleeper=sleeps.append,
        clock=iter((1.0, 2.0, 3.0)).__next__,
    )

    result = executor.execute(_plan(), before, tmp_path)

    expected_path = SwipePath(
        (PixelPoint(100, 600), PixelPoint(200, 650)),
        250,
    )
    assert result.acceptance.accepted is True
    assert android.swipes == [expected_path, expected_path]
    assert android.captures == 2
    assert sleeps == [1.2, 1.2]


def test_verifier_rejects_mismatched_screen_sizes() -> None:
    before = _capture()
    image = Image.new("L", (200, 400), 80)
    output = io.BytesIO()
    image.save(output, format="PNG")
    after = ScreenCapture(output.getvalue(), ScreenSize(200, 400))
    with pytest.raises(WordExecutionError, match="different sizes"):
        ImageDifferenceWordAcceptanceVerifier().verify(before, after, after)
