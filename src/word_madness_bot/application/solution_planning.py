"""Pure level-solution validation and swipe-path planning workflow."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

from word_madness_bot.application.ports.levels import LevelRepository
from word_madness_bot.domain.errors import SolutionPlanningError, SwipePlanningError
from word_madness_bot.domain.geometry import NormalizedPoint, PixelPoint, ScreenSize
from word_madness_bot.domain.models import LetterPosition
from word_madness_bot.gameplay.swipe_generator import SwipePathPlanner
from word_madness_bot.vision.letter_recognition import WheelLetterRecognition
from word_madness_bot.vision.wheel_geometry import LetterWheelGeometry


@dataclass(frozen=True, slots=True)
class PlannedSolution:
    """A solution word mapped to wheel indices and an interpolated pixel path."""

    word: str
    indices: tuple[int, ...]
    coordinates: tuple[PixelPoint, ...]
    duration_ms: int

    def to_dict(self) -> dict[str, object]:
        return {
            "word": self.word,
            "indices": list(self.indices),
            "coordinates": [{"x": point.x, "y": point.y} for point in self.coordinates],
            "duration_ms": self.duration_ms,
        }


@dataclass(frozen=True, slots=True)
class LevelSolutionPlan:
    """Complete, input-free plan for a detected level."""

    level: int
    recognized_letters: tuple[str, ...]
    solutions: tuple[PlannedSolution, ...]

    def to_dict(self) -> dict[str, object]:
        return {
            "level": self.level,
            "recognized_letters": list(self.recognized_letters),
            "solutions": [solution.to_dict() for solution in self.solutions],
        }


class LevelSolutionPlanner:
    """Load one level and produce validated paths without executing device input."""

    def __init__(self, repository: LevelRepository, path_planner: SwipePathPlanner) -> None:
        self.repository = repository
        self.path_planner = path_planner

    def plan(
        self,
        level_number: int,
        recognition: WheelLetterRecognition,
        geometry: LetterWheelGeometry,
        screen: ScreenSize,
    ) -> LevelSolutionPlan:
        """Map every repository word to detected indices and planned coordinates."""
        by_index = {letter.index: letter for letter in recognition.letters}
        if tuple(sorted(by_index)) != tuple(range(len(geometry.letters))):
            raise SolutionPlanningError("Recognized letter indices must be contiguous")
        geometry_by_index = {position.index: position for position in geometry.letters}
        if set(by_index) != set(geometry_by_index):
            raise SolutionPlanningError("Recognition and geometry indices do not match")
        letters = tuple(
            LetterPosition(
                by_index[index].character,
                NormalizedPoint(
                    geometry_by_index[index].point.x / (screen.width - 1),
                    geometry_by_index[index].point.y / (screen.height - 1),
                ),
            )
            for index in sorted(by_index)
        )
        level = self.repository.get_level(level_number)
        solutions: list[PlannedSolution] = []
        for word in level.words:
            indices = _map_indices(letters, word)
            try:
                path = self.path_planner.plan(letters, word, screen, interpolate=False)
            except SwipePlanningError as error:
                raise SolutionPlanningError(str(error)) from error
            solutions.append(PlannedSolution(word, indices, path.points, path.duration_ms))
        return LevelSolutionPlan(
            level.number,
            tuple(letter.character for letter in letters),
            tuple(solutions),
        )


def save_level_solution(plan: LevelSolutionPlan, debug_directory: Path) -> Path:
    """Persist a stable JSON debug representation of a plan."""
    destination = debug_directory / "level_solution.json"
    try:
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_text(
            json.dumps(plan.to_dict(), indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
    except OSError as error:
        raise SolutionPlanningError(f"Unable to save level solution: {destination}") from error
    return destination


def _map_indices(letters: tuple[LetterPosition, ...], word: str) -> tuple[int, ...]:
    normalized = word.strip().upper()

    def search(offset: int, used: frozenset[int]) -> tuple[int, ...] | None:
        if offset == len(normalized):
            return ()
        for index, letter in enumerate(letters):
            if index not in used and letter.character == normalized[offset]:
                remainder = search(offset + 1, used | {index})
                if remainder is not None:
                    return (index, *remainder)
        return None

    result = search(0, frozenset())
    if result is None:
        raise SolutionPlanningError(f"Solution cannot be formed from recognized letters: {word}")
    return result
