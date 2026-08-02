from __future__ import annotations

import json
from pathlib import Path

import pytest

from word_madness_bot.application.solution_planning import (
    LevelSolutionPlanner,
    save_level_solution,
)
from word_madness_bot.domain.errors import SolutionPlanningError
from word_madness_bot.domain.geometry import PixelPoint, ScreenSize
from word_madness_bot.gameplay.swipe_generator import SwipePathPlanner
from word_madness_bot.infrastructure.levels.json_repository import JsonLevelRepository
from word_madness_bot.vision.letter_recognition import RecognizedLetter, WheelLetterRecognition
from word_madness_bot.vision.wheel_geometry import LetterPosition, LetterWheelGeometry


def _inputs(tmp_path: Path) -> tuple[WheelLetterRecognition, LetterWheelGeometry]:
    points = (
        PixelPoint(500, 200),
        PixelPoint(800, 500),
        PixelPoint(500, 800),
        PixelPoint(200, 500),
    )
    recognition = WheelLetterRecognition(
        tuple(
            RecognizedLetter(index, character, 0.99, 0.01, tmp_path / f"{index}.png")
            for index, character in enumerate("ABBA")
        )
    )
    geometry = LetterWheelGeometry(
        PixelPoint(500, 500),
        300,
        tuple(LetterPosition(index, point) for index, point in enumerate(points)),
    )
    return recognition, geometry


def test_plans_indices_and_interpolated_coordinates_for_every_word(tmp_path: Path) -> None:
    repository = JsonLevelRepository.from_json('{"levels":[{"number":7,"words":["AB","BABA"]}]}')
    recognition, geometry = _inputs(tmp_path)
    plan = LevelSolutionPlanner(repository, SwipePathPlanner()).plan(
        7, recognition, geometry, ScreenSize(1000, 1000)
    )
    assert plan.level == 7
    assert plan.recognized_letters == tuple("ABBA")
    assert [solution.word for solution in plan.solutions] == ["AB", "BABA"]
    assert plan.solutions[0].indices == (0, 1)
    assert plan.solutions[1].indices == (1, 0, 2, 3)
    assert plan.solutions[0].coordinates[0] == PixelPoint(500, 200)
    assert plan.solutions[0].coordinates[-1] == PixelPoint(800, 500)
    assert len(plan.solutions[0].coordinates) == len(plan.solutions[0].word)
    assert plan.solutions[0].duration_ms == 150
    assert plan.solutions[1].duration_ms == 450


def test_rejects_repository_word_that_cannot_be_formed(tmp_path: Path) -> None:
    repository = JsonLevelRepository.from_json('{"levels":[{"number":7,"words":["AAA"]}]}')
    recognition, geometry = _inputs(tmp_path)
    with pytest.raises(SolutionPlanningError, match="cannot be formed"):
        LevelSolutionPlanner(repository, SwipePathPlanner()).plan(
            7, recognition, geometry, ScreenSize(1000, 1000)
        )


def test_saves_stable_json_debug_artifact(tmp_path: Path) -> None:
    repository = JsonLevelRepository.from_json('{"levels":[{"number":7,"words":["AB"]}]}')
    recognition, geometry = _inputs(tmp_path)
    plan = LevelSolutionPlanner(repository, SwipePathPlanner()).plan(
        7, recognition, geometry, ScreenSize(1000, 1000)
    )
    destination = save_level_solution(plan, tmp_path)
    payload = json.loads(destination.read_text(encoding="utf-8"))
    assert payload["level"] == 7
    assert payload["recognized_letters"] == list("ABBA")
    assert payload["solutions"][0]["indices"] == [0, 1]
    assert payload["solutions"][0]["coordinates"][0] == {"x": 500, "y": 200}
