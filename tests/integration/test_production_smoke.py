"""Final-cutover smoke and package-resource verification."""

from __future__ import annotations

from importlib.resources import files
from pathlib import Path
from typing import Any

from word_madness_bot.application.game_loop import GameLoop
from word_madness_bot.application.recovery import RecoveryStrategy, RetryPolicy, TimeoutPolicy
from word_madness_bot.cli import main
from word_madness_bot.domain.geometry import NormalizedPoint, ScreenSize
from word_madness_bot.domain.models import LetterPosition, SwipeExecutionReceipt
from word_madness_bot.gameplay.ads import (
    AdvertisementDetection,
    AdvertisementPolicy,
    AdvertisementType,
)
from word_madness_bot.gameplay.swipe_generator import SwipePathPlanner
from word_madness_bot.infrastructure.levels.json_repository import JsonLevelRepository


class FakeAndroid:
    def __init__(self) -> None:
        self.swipes: list[Any] = []
        self.taps: list[Any] = []

    def swipe(self, path: Any) -> SwipeExecutionReceipt:
        self.swipes.append(path)
        return SwipeExecutionReceipt(("fake",), (0, path.duration_ms))

    def tap(self, point: Any) -> None:
        self.taps.append(point)

    def __getattr__(self, name: str) -> Any:
        return lambda *args, **kwargs: None


def test_production_cli_dry_run() -> None:
    assert main(["--dry-run"], environ={}) == 0


def test_packaged_levels_and_templates_are_present() -> None:
    levels = files("word_madness_bot.resources.levels").joinpath("levels.json")
    templates = files("word_madness_bot.resources.templates").joinpath("__init__.py")
    assert levels.is_file()
    assert templates.is_file()
    packaged_levels = JsonLevelRepository.from_package().all_levels()
    assert len(packaged_levels) == 1010
    assert packaged_levels[0].number == 1
    assert packaged_levels[89].number == 90
    assert packaged_levels[89].words == (
        "DON", "DUN", "DUO", "FUN", "NOD", "FOND", "FUND", "FOUND"
    )
    assert packaged_levels[-1].number == 1010

def test_fake_backed_level_and_ad_workflow() -> None:
    android = FakeAndroid()
    repository = JsonLevelRepository.from_json(
        '{"levels": [{"number": 1, "words": ["CAT"]}]}'
    )
    letters = tuple(
        LetterPosition(character, point)
        for character, point in zip(
            "CAT",
            (NormalizedPoint(0.2, 0.5), NormalizedPoint(0.5, 0.2), NormalizedPoint(0.8, 0.5)),
            strict=True,
        )
    )
    result = GameLoop(android, repository, SwipePathPlanner()).play_level(
        1, letters, ScreenSize(1080, 2400)
    )
    detection = AdvertisementDetection(
        AdvertisementType.INTERSTITIAL, 0.95, (NormalizedPoint(0.95, 0.05),)
    )
    recovery = RecoveryStrategy(
        RetryPolicy(max_attempts=2, initial_delay_seconds=0),
        TimeoutPolicy(timeout_seconds=1),
        sleeper=lambda _: None,
        clock=lambda: 0,
    )
    visible = iter((True, False))
    ad_result = recovery.execute(
        lambda: AdvertisementPolicy().dismiss(
            android,
            detection,
            ScreenSize(1080, 2400),
            max_attempts=1,
            is_visible=lambda: next(visible),
        ),
        recoverable=(OSError,),
    )
    assert result.submitted_words == ("CAT",)
    assert len(android.swipes) == 1
    assert ad_result.dismissed
    assert len(android.taps) == 1

def test_repository_contains_no_prototype_runtime_or_imports() -> None:
    root = Path(__file__).parents[2]
    assert not any((root / name).exists() for name in ("core", "config", "tools", "main.py"))
    forbidden = ("from core", "import core", "from config", "import config")
    production_python = tuple((root / "src" / "word_madness_bot").rglob("*.py"))
    assert all(
        not any(token in path.read_text(encoding="utf-8") for token in forbidden)
        for path in production_python
    )
