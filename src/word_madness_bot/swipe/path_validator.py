"""Safety validation for complete normalized swipe paths."""

import math
from itertools import pairwise

from word_madness_bot.domain.errors import SwipePlanningError
from word_madness_bot.domain.models import SwipePath


class PathValidator:
    """Reject unsafe, stationary, discontinuous, or out-of-policy swipe paths."""

    def __init__(self, maximum_step_fraction: float = 0.25) -> None:
        if not 0.0 < maximum_step_fraction <= 1.0:
            raise ValueError("maximum step fraction must be above zero and at most one")
        self._maximum_step_fraction = maximum_step_fraction

    def validate(self, path: SwipePath) -> SwipePath:
        """Return the same typed path after all safety invariants pass."""

        travelled = 0.0
        for index, (start, end) in enumerate(pairwise(path.points)):
            distance = math.hypot(end.x - start.x, end.y - start.y)
            if distance <= 0.0:
                raise SwipePlanningError(f"path segment {index} is stationary")
            if distance > self._maximum_step_fraction:
                raise SwipePlanningError(
                    f"path segment {index} exceeds maximum normalized step "
                    f"{self._maximum_step_fraction:.3f}"
                )
            travelled += distance
        if travelled <= 0.0:
            raise SwipePlanningError("swipe path has no travel distance")
        return path
