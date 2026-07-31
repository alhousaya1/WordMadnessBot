"""Integration test for application metrics, health, and diagnostics output."""

import json
from pathlib import Path

from word_madness_bot.config import Settings
from word_madness_bot.observability.health import DiagnosticsReporter, HealthReporter
from word_madness_bot.observability.metrics import MetricName, MetricsCollector


def test_subsystem_metrics_flow_into_production_diagnostics(tmp_path: Path) -> None:
    settings = Settings(
        project_root=tmp_path,
        metrics_enabled=True,
        diagnostics_enabled=True,
        diagnostic_artifacts_enabled=True,
    )
    metrics = MetricsCollector(settings.metrics_enabled)
    for metric in MetricName:
        metrics.increment(metric)
        metrics.record_timing(metric, 0.002)
    health = HealthReporter(metrics, settings.health_stale_after_seconds)
    health.heartbeat()
    output = DiagnosticsReporter(settings, metrics, health).generate()
    assert output is not None
    payload = json.loads(output.read_text(encoding="utf-8"))
    assert payload["health"]["healthy"] is True
    assert payload["metrics"]["timings"]["decision_engine"]["count"] == 1
    assert payload["metrics"]["timings"]["screenshot_capture"]["count"] == 1
