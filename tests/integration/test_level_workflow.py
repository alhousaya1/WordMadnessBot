"""Fake-backed integration of repository, planner, and Android port."""

from pathlib import Path
from typing import Any

from word_madness_bot.application.game_loop import GameLoop
from word_madness_bot.domain.geometry import NormalizedPoint, ScreenSize
from word_madness_bot.domain.models import LetterPosition, SwipeExecutionReceipt
from word_madness_bot.gameplay.swipe_generator import SwipePathPlanner
from word_madness_bot.infrastructure.levels.json_repository import JsonLevelRepository


class Android:
    def __init__(self) -> None:
        self.paths: list[Any] = []

    def swipe(self, path: Any) -> SwipeExecutionReceipt:
        self.paths.append(path)
        return SwipeExecutionReceipt(("fake",), (0, path.duration_ms))

    def __getattr__(self, name: str) -> Any:
        return lambda *args, **kwargs: None


def test_known_level_workflow_with_real_repository_and_planner() -> None:
    repository = JsonLevelRepository.load(
        Path(__file__).parents[1] / "fixtures" / "levels" / "valid.json"
    )
    android = Android()
    workflow = GameLoop(android, repository, SwipePathPlanner())
    letters = tuple(
        LetterPosition(c, p)
        for c, p in zip(
            "CAT",
            (NormalizedPoint(0, 0), NormalizedPoint(0.5, 0.5), NormalizedPoint(1, 1)),
            strict=True,
        )
    )
    result = workflow.play_level(1, letters, ScreenSize(1080, 2400))
    assert result.submitted_words == ("CAT", "ACT")
    assert len(android.paths) == 2
