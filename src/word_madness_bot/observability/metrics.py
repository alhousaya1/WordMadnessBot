"""Thread-safe configurable counters and performance timing."""

import threading
from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass
from enum import StrEnum
from time import perf_counter


class MetricName(StrEnum):
    """Required production performance and runtime metric names."""

    SCREENSHOT_CAPTURE = "screenshot_capture"
    VISION_PIPELINE = "vision_pipeline"
    STATE_CLASSIFICATION = "state_classification"
    DATABASE_LOOKUP = "database_lookup"
    SWIPE_PLANNING = "swipe_planning"
    DECISION_ENGINE = "decision_engine"
    OBSERVATIONS = "observations"
    FAILURES = "failures"


@dataclass(frozen=True, slots=True)
class TimingSnapshot:
    """Immutable aggregate timing statistics in seconds."""

    count: int
    total_seconds: float
    minimum_seconds: float
    maximum_seconds: float

    @property
    def average_seconds(self) -> float:
        """Return the arithmetic mean, or zero for an empty aggregate."""

        return self.total_seconds / self.count if self.count else 0.0


@dataclass(frozen=True, slots=True)
class MetricsSnapshot:
    """Immutable copy of counters and timing aggregates."""

    counters: dict[str, int]
    timings: dict[str, TimingSnapshot]


class MetricsCollector:
    """Collect bounded in-memory aggregates when enabled, with no-op disabled behavior."""

    def __init__(self, enabled: bool = True) -> None:
        self.enabled = enabled
        self._lock = threading.Lock()
        self._counters: dict[str, int] = {}
        self._timings: dict[str, list[float]] = {}

    def increment(self, metric: MetricName, amount: int = 1) -> None:
        """Increment a counter by a nonnegative amount when collection is enabled."""

        if amount < 0:
            raise ValueError("metric increment cannot be negative")
        if not self.enabled:
            return
        with self._lock:
            self._counters[metric.value] = self._counters.get(metric.value, 0) + amount

    def record_timing(self, metric: MetricName, seconds: float) -> None:
        """Record one nonnegative duration when collection is enabled."""

        if seconds < 0.0:
            raise ValueError("metric duration cannot be negative")
        if not self.enabled:
            return
        with self._lock:
            values = self._timings.setdefault(metric.value, [0.0, 0.0, seconds, seconds])
            values[0] += 1.0
            values[1] += seconds
            values[2] = min(values[2], seconds)
            values[3] = max(values[3], seconds)

    @contextmanager
    def time(self, metric: MetricName) -> Iterator[None]:
        """Measure a block with a monotonic high-resolution clock."""

        started = perf_counter()
        try:
            yield
        finally:
            self.record_timing(metric, perf_counter() - started)

    def snapshot(self) -> MetricsSnapshot:
        """Return an immutable aggregate snapshot without exposing mutable internals."""

        with self._lock:
            timings = {
                name: TimingSnapshot(int(values[0]), values[1], values[2], values[3])
                for name, values in self._timings.items()
            }
            return MetricsSnapshot(dict(self._counters), timings)
