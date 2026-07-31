"""Application lifecycle services independent of CLI parsing and concrete adapters."""

import logging
import threading
from dataclasses import dataclass, replace
from pathlib import Path
from time import monotonic
from typing import Protocol

from word_madness_bot.config.settings import Settings
from word_madness_bot.contracts.capture import ScreenshotCapture
from word_madness_bot.contracts.database import LevelRepository
from word_madness_bot.contracts.device import DeviceGateway
from word_madness_bot.contracts.input import InputExecutor
from word_madness_bot.domain.models import CapturedFrame, RuntimeObservation
from word_madness_bot.gameplay.actions import (
    CompleteAction,
    EscalateAction,
    KeyEventAction,
    ObserveAction,
    TapAction,
    WaitAction,
)
from word_madness_bot.gameplay.commands import (
    AdvertisementActionDecision,
    CommandOutcome,
    EngineCommand,
    EscalateDecision,
    ObserveDecision,
    RetryDecision,
    SubmitWordDecision,
)
from word_madness_bot.gameplay.decision_engine import DecisionEngine
from word_madness_bot.observability.events import EventName, StructuredEvent, log_event
from word_madness_bot.observability.health import DiagnosticsReporter, HealthReport, HealthReporter
from word_madness_bot.observability.metrics import MetricName, MetricsCollector
from word_madness_bot.vision.geometry import to_pixel_point

_LOGGER = logging.getLogger(__name__)


class ObservationPipeline(Protocol):
    """Produce one typed runtime observation from an acquired frame."""

    def observe(self, frame: CapturedFrame, revision: int) -> RuntimeObservation:
        """Analyze one captured frame without executing gameplay input."""

        ...


@dataclass(frozen=True, slots=True)
class ApplicationDependencies:
    """All replaceable boundaries required by the application lifecycle."""

    settings: Settings
    repository: LevelRepository
    devices: DeviceGateway
    capture: ScreenshotCapture
    inputs: InputExecutor
    observations: ObservationPipeline
    decision_engine: DecisionEngine


class Application:
    """Coordinate startup, diagnostics, continuous observation, and graceful shutdown."""

    def __init__(self, dependencies: ApplicationDependencies) -> None:
        self._dependencies = dependencies
        self._stop_event = threading.Event()
        self._revision = 0
        self._started_at = monotonic()
        self._metrics = MetricsCollector(dependencies.settings.metrics_enabled)
        self._health = HealthReporter(
            self._metrics, dependencies.settings.health_stale_after_seconds
        )
        self._diagnostics = DiagnosticsReporter(dependencies.settings, self._metrics, self._health)

    @property
    def dependencies(self) -> ApplicationDependencies:
        """Expose immutable dependency wiring for diagnostics and composition tests."""

        return self._dependencies

    def validate_configuration(self) -> None:
        """Confirm settings were constructed and all referenced paths are deterministic."""

        _ = self._dependencies.settings.project_root
        _ = self._dependencies.settings.level_database_file

    def validate_database(self) -> int:
        """Force repository validation and return its deterministic level count."""

        with self._metrics.time(MetricName.DATABASE_LOOKUP):
            return len(self._dependencies.repository.all_levels())

    def check_device(self) -> str:
        """Return the selected available device serial or raise a typed adapter error."""

        serials = self._dependencies.devices.list_devices()
        configured = self._dependencies.settings.device_serial
        if configured is not None:
            if configured not in serials:
                raise RuntimeError(f"configured device is unavailable: {configured}")
            return configured
        if len(serials) != 1:
            raise RuntimeError(f"expected exactly one available device, found {len(serials)}")
        return serials[0]

    def capture_diagnostic(self) -> Path:
        """Capture one screenshot and persist it only for this explicit diagnostic command."""

        with self._metrics.time(MetricName.SCREENSHOT_CAPTURE):
            frame = self._dependencies.capture.capture(self.check_device())
        output = self._dependencies.settings.screenshot_directory / "diagnostic.png"
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_bytes(frame.data)
        return output

    def observe_once(self) -> RuntimeObservation:
        """Capture and analyze one frame without producing or executing input commands."""

        with self._metrics.time(MetricName.SCREENSHOT_CAPTURE):
            frame = self._dependencies.capture.capture(self.check_device())
        self._revision += 1
        with self._metrics.time(MetricName.VISION_PIPELINE):
            observation = self._dependencies.observations.observe(frame, self._revision)
        self._metrics.increment(MetricName.OBSERVATIONS)
        self._health.heartbeat()
        return replace(observation, elapsed_seconds=monotonic() - self._started_at)

    def health_report(self) -> HealthReport:
        """Return current in-process health without requiring diagnostics output."""

        return self._health.report()

    def generate_diagnostics(self, destination: Path | None = None) -> Path | None:
        """Generate a report only when diagnostics are enabled in configuration."""

        return self._diagnostics.generate(destination)

    def run_continuous(self, *, maximum_cycles: int | None = None) -> int:
        """Run the autonomous observe/decide/execute/verify loop until shutdown."""

        cycles = 0
        self._stop_event.clear()
        log_event(
            _LOGGER,
            logging.INFO,
            StructuredEvent(EventName.APPLICATION_START),
            "Application continuous run started",
        )
        observation = self.observe_once()
        while not self._stop_event.is_set():
            with self._metrics.time(MetricName.DECISION_ENGINE):
                decision = self._dependencies.decision_engine.decide(observation)
                command = self._dependencies.decision_engine.create_command(
                    decision, observation.revision
                )
            outcome = self._execute_command(command)
            # Every command, including waits and failures, is followed by fresh evidence.
            new_observation = self.observe_once()
            with self._metrics.time(MetricName.DECISION_ENGINE):
                verified = self._dependencies.decision_engine.verify(
                    command, outcome, new_observation
                )
            cycles += 1
            log_event(
                _LOGGER,
                logging.INFO,
                StructuredEvent(
                    EventName.COMMAND_EXECUTION,
                    {
                        "revision": new_observation.revision,
                        "state": new_observation.state.state.value,
                        "command_id": command.identifier,
                        "command_type": type(command.decision).__name__,
                        "verified": verified,
                    },
                ),
                "Runtime command completed and verified",
            )
            if isinstance(decision, EscalateDecision):
                raise RuntimeError(f"automatic recovery exhausted: {decision.detail}")
            if isinstance(decision, AdvertisementActionDecision) and isinstance(
                decision.action, EscalateAction
            ):
                raise RuntimeError(f"advertisement recovery exhausted: {decision.action.detail}")
            if maximum_cycles is not None and cycles >= maximum_cycles:
                break
            observation = new_observation
            self._stop_event.wait(self._dependencies.settings.run_interval_seconds)
        log_event(
            _LOGGER,
            logging.INFO,
            StructuredEvent(EventName.APPLICATION_STOP, {"cycles": cycles}),
            "Application continuous run stopped",
        )
        return cycles

    def _execute_command(self, command: EngineCommand) -> CommandOutcome:
        """Execute exactly one typed command without selecting subsequent gameplay work."""

        serial = self.check_device()
        decision = command.decision
        try:
            if isinstance(decision, SubmitWordDecision):
                self._dependencies.inputs.swipe(serial, decision.path)
            elif isinstance(decision, RetryDecision):
                self._stop_event.wait(decision.delay_seconds)
            elif isinstance(decision, AdvertisementActionDecision):
                self._execute_advertisement_action(serial, decision)
            elif isinstance(decision, (ObserveDecision, EscalateDecision)):
                pass
            else:  # pragma: no cover - exhaustiveness guard for future command types
                raise TypeError(f"unsupported engine decision: {type(decision).__name__}")
        except Exception as error:
            self._metrics.increment(MetricName.FAILURES)
            _LOGGER.exception(
                "Runtime command execution failed",
                extra={"event": "command.execution", "command_id": command.identifier},
            )
            return CommandOutcome(command.identifier, False, str(error))
        return CommandOutcome(command.identifier, True)

    def _execute_advertisement_action(
        self, serial: str, decision: AdvertisementActionDecision
    ) -> None:
        """Execute only the typed action already selected by AdvertisementPolicy."""

        action = decision.action
        if isinstance(action, WaitAction):
            self._stop_event.wait(action.delay_seconds)
        elif isinstance(action, TapAction):
            geometry = self._dependencies.devices.get_device_info(serial).screen
            self._dependencies.inputs.tap(serial, to_pixel_point(action.point, geometry))
        elif isinstance(action, KeyEventAction):
            self._dependencies.inputs.key_event(serial, action.key_code)
        elif isinstance(action, (ObserveAction, CompleteAction, EscalateAction)):
            pass
        else:  # pragma: no cover - exhaustiveness guard for future action types
            raise TypeError(f"unsupported advertisement action: {type(action).__name__}")

    def request_shutdown(self) -> None:
        """Request cooperative shutdown; safe to call from signal handlers or another thread."""

        self._stop_event.set()
