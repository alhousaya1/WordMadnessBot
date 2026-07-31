"""Health state and production diagnostics report generation."""

import json
import logging
import platform
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from pathlib import Path
from time import monotonic

from word_madness_bot.config.settings import Settings
from word_madness_bot.observability.events import EventName, StructuredEvent, log_event
from word_madness_bot.observability.metrics import MetricsCollector

_LOGGER = logging.getLogger(__name__)


@dataclass(frozen=True, slots=True)
class HealthReport:
    """Immutable health assessment for the long-running application."""

    healthy: bool
    status: str
    uptime_seconds: float
    seconds_since_heartbeat: float
    observation_count: int
    failure_count: int


class HealthReporter:
    """Track process heartbeat and derive health from configured staleness limits."""

    def __init__(self, metrics: MetricsCollector, stale_after_seconds: float = 30.0) -> None:
        if stale_after_seconds <= 0.0:
            raise ValueError("health staleness threshold must be positive")
        self._metrics = metrics
        self._stale_after_seconds = stale_after_seconds
        self._started = monotonic()
        self._heartbeat = self._started

    def heartbeat(self) -> None:
        """Record evidence that the application loop is responsive."""

        self._heartbeat = monotonic()

    def report(self) -> HealthReport:
        """Return current health without performing I/O or external probes."""

        now = monotonic()
        age = now - self._heartbeat
        snapshot = self._metrics.snapshot()
        observations = snapshot.counters.get("observations", 0)
        failures = snapshot.counters.get("failures", 0)
        healthy = age <= self._stale_after_seconds
        report = HealthReport(
            healthy,
            "healthy" if healthy else "stale",
            now - self._started,
            age,
            observations,
            failures,
        )
        log_event(
            _LOGGER,
            logging.DEBUG,
            StructuredEvent(EventName.HEALTH_REPORT, {"healthy": healthy, "status": report.status}),
            "Health report generated",
        )
        return report


class DiagnosticsReporter:
    """Generate an atomic JSON report when diagnostics are enabled."""

    def __init__(
        self,
        settings: Settings,
        metrics: MetricsCollector,
        health: HealthReporter,
    ) -> None:
        self._settings = settings
        self._metrics = metrics
        self._health = health

    def generate(self, destination: Path | None = None) -> Path | None:
        """Write a production-safe report or return none when disabled."""

        if not self._settings.diagnostics_enabled:
            return None
        output = destination or self._settings.diagnostics_directory / "diagnostics.json"
        output = output.expanduser().resolve()
        output.parent.mkdir(parents=True, exist_ok=True)
        metrics = self._metrics.snapshot()
        payload = {
            "generated_at": datetime.now(UTC).isoformat(),
            "application": {"version": "0.1.0", "python": platform.python_version()},
            "health": asdict(self._health.report()),
            "metrics": {
                "counters": metrics.counters,
                "timings": {name: asdict(value) for name, value in metrics.timings.items()},
            },
            "configuration": {
                "debug_images_enabled": self._settings.save_debug_images,
                "metrics_enabled": self._settings.metrics_enabled,
                "diagnostics_enabled": self._settings.diagnostics_enabled,
            },
        }
        temporary = output.with_suffix(f"{output.suffix}.tmp")
        temporary.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
        temporary.replace(output)
        log_event(
            _LOGGER,
            logging.INFO,
            StructuredEvent(EventName.DIAGNOSTICS_REPORT, {"path": str(output)}),
            "Diagnostics report generated",
        )
        return output
