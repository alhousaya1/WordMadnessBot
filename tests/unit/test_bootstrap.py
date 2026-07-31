"""Unit tests for the single production composition root."""

import json
from pathlib import Path

from word_madness_bot.bootstrap import (
    AdbInputExecutor,
    AdbRuntimeAdapter,
    ProductionObservationPipeline,
    build_application,
)
from word_madness_bot.config import Settings
from word_madness_bot.gameplay.decision_engine import DecisionEngine


def test_composition_root_wires_concrete_boundaries(tmp_path: Path) -> None:
    database = tmp_path / "database"
    database.mkdir()
    (database / "levels.json").write_text(
        json.dumps(
            {
                "schema_version": 1,
                "levels": [{"number": 1, "letters": ["A", "T"], "words": ["AT"]}],
            }
        ),
        encoding="utf-8",
    )

    app = build_application(Settings(project_root=tmp_path))

    assert isinstance(app.dependencies.devices, AdbRuntimeAdapter)
    assert app.dependencies.capture is app.dependencies.devices
    assert isinstance(app.dependencies.inputs, AdbInputExecutor)
    assert isinstance(app.dependencies.observations, ProductionObservationPipeline)
    assert isinstance(app.dependencies.decision_engine, DecisionEngine)
    assert app.validate_database() == 1
