"""Level orchestration through Database and Swipe contracts only."""

import logging
from collections.abc import Sequence

from word_madness_bot.contracts.database import LevelRepository
from word_madness_bot.contracts.swipe import SwipeGenerator
from word_madness_bot.domain.errors import SwipePlanningError
from word_madness_bot.domain.models import SwipeLetter
from word_madness_bot.gameplay.commands import SubmitWordDecision
from word_madness_bot.gameplay.progress import LevelProgress

_LOGGER = logging.getLogger(__name__)


class LevelSolver:
    """Load levels through a repository and create paths through a Swipe contract."""

    def __init__(
        self,
        repository: LevelRepository,
        swipe_generator: SwipeGenerator,
        progress: LevelProgress,
        *,
        maximum_word_attempts: int = 2,
    ) -> None:
        if maximum_word_attempts <= 0:
            raise ValueError("maximum word attempts must be positive")
        self._repository = repository
        self._swipe_generator = swipe_generator
        self.progress = progress
        self._maximum_word_attempts = maximum_word_attempts

    def load(self, level_number: int) -> bool:
        """Load an exact level through the contract and preserve same-level progress."""

        level = self._repository.get_level(level_number)
        if level is None:
            return False
        self.progress.begin(level)
        return True

    def next_decision(self, letters: Sequence[SwipeLetter]) -> SubmitWordDecision | None:
        """Create the next unique word decision, or return none when complete/pending."""

        word = self.progress.next_word()
        if word is None:
            return None
        if self.progress.word_attempts.get(word, 0) >= self._maximum_word_attempts:
            raise SwipePlanningError(f"word attempt limit reached: {word}")
        path = self._swipe_generator.generate(word, letters)
        self.progress.mark_pending(word)
        assert self.progress.level is not None
        _LOGGER.debug(
            "Prepared unique level word",
            extra={
                "event": "level_word_prepared",
                "word": word,
                "level": self.progress.level.number,
            },
        )
        return SubmitWordDecision(word, path)

    def verify_word(self, succeeded: bool) -> str | None:
        """Apply external command verification to the pending word exactly once."""

        return self.progress.verify_pending(succeeded)
