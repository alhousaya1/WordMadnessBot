"""Release smoke test for deterministic device availability failure behavior."""

from pathlib import Path

import pytest

from word_madness_bot.application import Application, ApplicationDependencies
from word_madness_bot.config import Settings


class Device:
    def list_devices(self) -> tuple[str, ...]:
        return ("device-1",)


class Unused:
    """Placeholder for dependencies not reached by this connectivity test."""


def test_unavailable_configured_device_fails_without_guessing(tmp_path: Path) -> None:
    dependencies = ApplicationDependencies(
        settings=Settings(project_root=tmp_path, device_serial="missing-device"),
        repository=Unused(),  # type: ignore[arg-type]
        devices=Device(),  # type: ignore[arg-type]
        capture=Unused(),  # type: ignore[arg-type]
        inputs=Unused(),  # type: ignore[arg-type]
        observations=Unused(),  # type: ignore[arg-type]
        decision_engine=Unused(),  # type: ignore[arg-type]
    )
    with pytest.raises(RuntimeError, match="configured device is unavailable"):
        Application(dependencies).check_device()
