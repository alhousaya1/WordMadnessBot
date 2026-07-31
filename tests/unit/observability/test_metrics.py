"""Unit tests for runtime metrics, health, and diagnostics."""

import json
from pathlib import Path

from word_madness_bot.config import Settings
from word_madness_bot.observability.health import DiagnosticsReporter, HealthReporter
from word_madness_bot.observability.metrics import MetricName, MetricsCollector


def test_all_required_subsystems_support_timing() -> None:
    metrics = MetricsCollector()
    required = (
        MetricName.SCREENSHOT_CAPTURE,
        MetricName.VISION_PIPELINE,
        MetricName.STATE_CLASSIFICATION,
        MetricName.DATABASE_LOOKUP,
        MetricName.SWIPE_PLANNING,
        MetricName.DECISION_ENGINE,
    )
    for metric in required:
        metrics.record_timing(metric, 0.01)
    snapshot = metrics.snapshot()
    assert set(snapshot.timings) == {metric.value for metric in required}
    assert all(timing.average_seconds == 0.01 for timing in snapshot.timings.values())


def test_disabled_metrics_are_complete_no_ops() -> None:
    metrics = MetricsCollector(enabled=False)
    metrics.increment(MetricName.OBSERVATIONS)
    with metrics.time(MetricName.VISION_PIPELINE):
        pass
    assert metrics.snapshot().counters == {}
    assert metrics.snapshot().timings == {}


def test_health_uses_metrics_and_heartbeat() -> None:
    metrics = MetricsCollector()
    metrics.increment(MetricName.OBSERVATIONS, 3)
    health = HealthReporter(metrics, stale_after_seconds=10.0)
    health.heartbeat()
    report = health.report()
    assert report.healthy
    assert report.observation_count == 3


def test_diagnostics_report_is_configuration_controlled(tmp_path: Path) -> None:
    metrics = MetricsCollector()
    health = HealthReporter(metrics)
    disabled = DiagnosticsReporter(Settings(project_root=tmp_path), metrics, health)
    assert disabled.generate() is None
    assert not (tmp_path / "diagnostics").exists()

    enabled = DiagnosticsReporter(
        Settings(project_root=tmp_path, diagnostics_enabled=True), metrics, health
    )
    output = enabled.generate()
    assert output is not None
    payload = json.loads(output.read_text(encoding="utf-8"))
    assert payload["health"]["healthy"] is True
    assert payload["configuration"]["diagnostics_enabled"] is True
