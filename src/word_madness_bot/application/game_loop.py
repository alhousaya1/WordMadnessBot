"""Bounded level workflow composed exclusively over production boundaries."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

from word_madness_bot.application.decision_engine import Action, Decision, DecisionEngine
from word_madness_bot.application.ports.android import AndroidPort
from word_madness_bot.application.ports.levels import LevelRepository
from word_madness_bot.domain.errors import (
    SwipePlanningError,
    WorkflowCancelledError,
    WorkflowTimeoutError,
)
from word_madness_bot.domain.geometry import ScreenSize
from word_madness_bot.domain.models import LetterPosition, StateObservation
from word_madness_bot.gameplay.swipe_generator import SwipePathPlanner


@dataclass(frozen=True, slots=True)
class LevelWorkflowResult:
    """Observable result of planning and submitting one known level."""

    level_number: int
    submitted_words: tuple[str, ...]
    rejected_words: tuple[str, ...]


class GameLoop:
    """Minimal bounded orchestration for the documented level workflow."""

    def __init__(
        self,
        android: AndroidPort,
        levels: LevelRepository,
        planner: SwipePathPlanner,
        decisions: DecisionEngine | None = None,
    ) -> None:
        self.android = android
        self.levels = levels
        self.planner = planner
        self.decisions = decisions or DecisionEngine()

    def play_level(
        self, number: int, letters: tuple[LetterPosition, ...], screen: ScreenSize
    ) -> LevelWorkflowResult:
        """Load, plan, and submit every mappable word through AndroidPort."""
        level = self.levels.get_level(number)
        submitted: list[str] = []
        rejected: list[str] = []
        for word in level.words:
            try:
                path = self.planner.plan(letters, word, screen)
            except SwipePlanningError:
                rejected.append(word)
                continue
            self.android.swipe(path)
            submitted.append(word)
        return LevelWorkflowResult(number, tuple(submitted), tuple(rejected))

    def await_action(
        self,
        observe: Callable[[], StateObservation],
        *,
        max_polls: int,
        cancelled: Callable[[], bool] = lambda: False,
    ) -> Decision:
        """Poll within a hard bound until an actionable stable state appears."""
        if max_polls <= 0:
            raise ValueError("max_polls must be positive")
        for _ in range(max_polls):
            if cancelled():
                raise WorkflowCancelledError("Game workflow was cancelled")
            decision = self.decisions.decide(observe())
            if decision.action is not Action.WAIT:
                return decision
        raise WorkflowTimeoutError("No actionable state before polling limit")
