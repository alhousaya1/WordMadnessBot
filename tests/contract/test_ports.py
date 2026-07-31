"""Contract tests proving that boundaries are replaceable with typed fakes."""

from collections.abc import Sequence

from word_madness_bot.application.ports import AndroidPort, LevelRepository, VisionPort
from word_madness_bot.domain.geometry import PixelPoint, ScreenSize
from word_madness_bot.domain.models import (
    DeviceDescriptor,
    DeviceState,
    DisplayMetrics,
    Level,
    ScreenCapture,
    SwipePath,
    VisionObservation,
)
from word_madness_bot.domain.states import GameState


class FakeAndroid:
    def discover_devices(self) -> tuple[DeviceDescriptor, ...]:
        return (DeviceDescriptor("fake", DeviceState.ONLINE),)

    def select_device(self, serial: str | None = None) -> DeviceDescriptor:
        return DeviceDescriptor(serial or "fake", DeviceState.ONLINE)

    def verify_connection(self) -> bool:
        return True

    def get_display_metrics(self) -> DisplayMetrics:
        return DisplayMetrics(ScreenSize(100, 200), 320)

    def capture_screenshot(self) -> ScreenCapture:
        return ScreenCapture(b"png", ScreenSize(100, 200))

    def tap(self, point: PixelPoint) -> None:
        return None

    def swipe(self, path: SwipePath) -> None:
        return None

    def press_back(self) -> None:
        return None

    def press_home(self) -> None:
        return None

    def execute_shell(
        self,
        command: Sequence[str],
        *,
        timeout_seconds: float | None = None,
    ) -> str:
        return " ".join(command)


class FakeLevels:
    def get_level(self, number: int) -> Level | None:
        return Level(number, ("WORD",)) if number > 0 else None


class FakeVision:
    def analyze(self, capture: ScreenCapture) -> VisionObservation:
        return VisionObservation(GameState.UNKNOWN, 0.0)


def test_fakes_satisfy_runtime_checkable_ports() -> None:
    assert isinstance(FakeAndroid(), AndroidPort)
    assert isinstance(FakeLevels(), LevelRepository)
    assert isinstance(FakeVision(), VisionPort)


def test_ports_exchange_domain_values() -> None:
    android = FakeAndroid()
    vision = FakeVision()

    device = android.select_device()
    observation = vision.analyze(android.capture_screenshot())

    assert device.state is DeviceState.ONLINE
    assert observation.state is GameState.UNKNOWN
