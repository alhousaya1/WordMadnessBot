"""Unit tests for bounded level orchestration."""

from typing import Any

import pytest

from word_madness_bot.application.decision_engine import Action
from word_madness_bot.application.game_loop import GameLoop
from word_madness_bot.domain.errors import WorkflowCancelledError, WorkflowTimeoutError
from word_madness_bot.domain.geometry import NormalizedPoint, ScreenSize
from word_madness_bot.domain.models import (
    LetterPosition,
    Level,
    StateObservation,
    SwipeExecutionReceipt,
)
from word_madness_bot.domain.states import GameState
from word_madness_bot.gameplay.swipe_generator import SwipePathPlanner


class Android:
    def __init__(self) -> None:
        self.paths: list[Any] = []

    def swipe(self, path: Any) -> SwipeExecutionReceipt:
        self.paths.append(path)
        return SwipeExecutionReceipt(("fake",), (0, path.duration_ms))

    def __getattr__(self, name: str) -> Any:
        return lambda *args, **kwargs: None


class Levels:
    def get_level(self, number: int) -> Level:
        return Level(number, ("CAT", "DOG"))


def loop() -> tuple[GameLoop, Android]:
    android = Android()
    return GameLoop(android, Levels(), SwipePathPlanner()), android


def test_level_submits_mappable_and_reports_rejected_words() -> None:
    workflow, android = loop()
    letters = tuple(
        LetterPosition(c, p)
        for c, p in zip(
            "CAT",
            (NormalizedPoint(0, 0), NormalizedPoint(0.5, 0.5), NormalizedPoint(1, 1)),
            strict=True,
        )
    )
    result = workflow.play_level(1, letters, ScreenSize(100, 200))
    assert result.submitted_words == ("CAT",)
    assert result.rejected_words == ("DOG",)
    assert len(android.paths) == 1


def test_bounded_polling_returns_action() -> None:
    workflow, _ = loop()
    assert (
        workflow.await_action(
            lambda: StateObservation(GameState.VICTORY, 1, stable=True), max_polls=1
        ).action
        is Action.ADVANCE
    )


def test_polling_timeout_and_cancellation_are_typed() -> None:
    workflow, _ = loop()
    def observe() -> StateObservation:
        return StateObservation(GameState.UNKNOWN, 0, stable=True)
    with pytest.raises(WorkflowTimeoutError):
        workflow.await_action(observe, max_polls=2)
    with pytest.raises(WorkflowCancelledError):
        workflow.await_action(observe, max_polls=2, cancelled=lambda: True)
