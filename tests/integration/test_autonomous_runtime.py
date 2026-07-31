"""Integration tests for strict command execution and fresh-observation verification."""

from datetime import UTC, datetime
from io import BytesIO
from pathlib import Path

from PIL import Image

from word_madness_bot.application import Application, ApplicationDependencies
from word_madness_bot.config import Settings
from word_madness_bot.domain.enums import GameState, StateReasonCode
from word_madness_bot.domain.models import (
    CapturedFrame,
    DeviceInfo,
    NormalizedPoint,
    RuntimeObservation,
    ScreenGeometry,
    StateObservation,
    SwipePath,
)
from word_madness_bot.gameplay.commands import (
    CommandOutcome,
    EngineCommand,
    SubmitWordDecision,
)


class RuntimeHarness:
    def __init__(self, *, fail_swipe: bool = False) -> None:
        self.events: list[str] = []
        self.fail_swipe = fail_swipe

    def list_devices(self) -> tuple[str, ...]:
        return ("device-1",)

    def get_device_info(self, serial: str) -> DeviceInfo:
        return DeviceInfo(serial, "model", "14", ScreenGeometry(10, 10, 320))

    def is_available(self, serial: str) -> bool:
        return True

    def capture(self, serial: str) -> CapturedFrame:
        self.events.append("capture")
        output = BytesIO()
        Image.new("RGB", (10, 10)).save(output, format="PNG")
        return CapturedFrame(output.getvalue(), ScreenGeometry(10, 10, 320), datetime.now(UTC))

    def swipe(self, serial: str, path: SwipePath) -> None:
        self.events.append("swipe")
        if self.fail_swipe:
            raise RuntimeError("simulated input failure")

    def tap(self, serial: str, point: object) -> None:
        self.events.append("tap")

    def key_event(self, serial: str, key_code: int) -> None:
        self.events.append("key")


class Observer:
    def __init__(self, harness: RuntimeHarness) -> None:
        self._harness = harness

    def observe(self, frame: CapturedFrame, revision: int) -> RuntimeObservation:
        self._harness.events.append(f"observe:{revision}")
        state = StateObservation(
            GameState.PLAYING,
            1.0,
            reason_codes=(StateReasonCode.STABILIZED,),
        )
        return RuntimeObservation(revision, state)


class Engine:
    def __init__(self, harness: RuntimeHarness, *, expected_success: bool = True) -> None:
        self._harness = harness
        self._expected_success = expected_success
        self._decision = SubmitWordDecision(
            "AT", SwipePath((NormalizedPoint(0.1, 0.1), NormalizedPoint(0.9, 0.9)), 10)
        )

    def decide(self, observation: RuntimeObservation) -> SubmitWordDecision:
        self._harness.events.append("decide")
        return self._decision

    def create_command(self, decision: object, revision: int) -> EngineCommand:
        self._harness.events.append("create")
        return EngineCommand(1, revision, self._decision)

    def verify(
        self, command: EngineCommand, outcome: CommandOutcome, observation: RuntimeObservation
    ) -> bool:
        self._harness.events.append(f"verify:{observation.revision}")
        assert outcome.succeeded is self._expected_success
        assert observation.revision > command.observation_revision
        return True


def test_runtime_executes_one_command_then_observes_before_verification(tmp_path: Path) -> None:
    harness = RuntimeHarness()
    app = Application(
        ApplicationDependencies(
            Settings(project_root=tmp_path, run_interval_seconds=0.001),
            object(),  # type: ignore[arg-type]
            harness,
            harness,
            harness,
            Observer(harness),
            Engine(harness),  # type: ignore[arg-type]
        )
    )
    assert app.run_continuous(maximum_cycles=1) == 1
    assert harness.events == [
        "capture",
        "observe:1",
        "decide",
        "create",
        "swipe",
        "capture",
        "observe:2",
        "verify:2",
    ]


def test_failed_command_is_observed_and_verified_before_runtime_can_continue(
    tmp_path: Path,
) -> None:
    harness = RuntimeHarness(fail_swipe=True)
    app = Application(
        ApplicationDependencies(
            Settings(project_root=tmp_path, run_interval_seconds=0.001),
            object(),  # type: ignore[arg-type]
            harness,
            harness,
            harness,
            Observer(harness),
            Engine(harness, expected_success=False),  # type: ignore[arg-type]
        )
    )
    assert app.run_continuous(maximum_cycles=1) == 1
    assert harness.events[-3:] == ["capture", "observe:2", "verify:2"]
    assert harness.events.count("swipe") == 1
