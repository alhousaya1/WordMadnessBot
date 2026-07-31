"""Integration tests for application startup, dry-run wiring, and graceful shutdown."""

import threading
from datetime import UTC, datetime
from io import BytesIO
from pathlib import Path

from PIL import Image

from word_madness_bot.application import Application, ApplicationDependencies
from word_madness_bot.config import Settings
from word_madness_bot.domain.enums import GameState, StateReasonCode
from word_madness_bot.domain.models import (
    CapturedFrame,
    RuntimeObservation,
    ScreenGeometry,
    StateObservation,
)
from word_madness_bot.gameplay.commands import CommandOutcome, EngineCommand, ObserveDecision


class Repository:
    def all_levels(self) -> tuple[object, ...]:
        return (object(),)


class Device:
    def list_devices(self) -> tuple[str, ...]:
        return ("device-1",)


class Capture:
    def capture(self, serial: str) -> CapturedFrame:
        output = BytesIO()
        Image.new("RGB", (4, 4)).save(output, format="PNG")
        return CapturedFrame(output.getvalue(), ScreenGeometry(4, 4, 320), datetime.now(UTC))


class Observer:
    def observe(self, frame: CapturedFrame, revision: int) -> RuntimeObservation:
        state = StateObservation(
            GameState.UNKNOWN,
            1.0,
            reason_codes=(StateReasonCode.NO_EVIDENCE,),
        )
        return RuntimeObservation(revision, state)


class Inputs:
    def tap(self, serial: str, point: object) -> None:
        pass

    def swipe(self, serial: str, path: object) -> None:
        pass

    def key_event(self, serial: str, key_code: int) -> None:
        pass


class Engine:
    def decide(self, observation: RuntimeObservation) -> ObserveDecision:
        return ObserveDecision("test")

    def create_command(self, decision: object, revision: int) -> EngineCommand:
        return EngineCommand(1, revision, ObserveDecision("test"))

    def verify(
        self, command: EngineCommand, outcome: CommandOutcome, observation: RuntimeObservation
    ) -> bool:
        return outcome.succeeded and observation.revision > command.observation_revision

def _application(tmp_path: Path) -> Application:
    dependencies = ApplicationDependencies(
        settings=Settings(project_root=tmp_path, run_interval_seconds=0.01),
        repository=Repository(),  # type: ignore[arg-type]
        devices=Device(),  # type: ignore[arg-type]
        capture=Capture(),
        inputs=Inputs(),  # type: ignore[arg-type]
        observations=Observer(),
        decision_engine=Engine(),  # type: ignore[arg-type]
    )
    return Application(dependencies)


def test_startup_validation_and_dry_run_observation(tmp_path: Path) -> None:
    app = _application(tmp_path)
    app.validate_configuration()
    assert app.validate_database() == 1
    assert app.check_device() == "device-1"
    assert app.observe_once().revision == 1
    assert app.observe_once().revision == 2


def test_diagnostic_capture_is_explicit(tmp_path: Path) -> None:
    app = _application(tmp_path)
    output = app.capture_diagnostic()
    assert output == tmp_path / "screenshots" / "diagnostic.png"
    assert output.is_file()


def test_continuous_run_stops_gracefully(tmp_path: Path) -> None:
    app = _application(tmp_path)
    result: list[int] = []
    thread = threading.Thread(target=lambda: result.append(app.run_continuous()))
    thread.start()
    while app.observe_once().revision < 2:
        pass
    app.request_shutdown()
    thread.join(timeout=2.0)
    assert not thread.is_alive()
    assert result and result[0] >= 0
