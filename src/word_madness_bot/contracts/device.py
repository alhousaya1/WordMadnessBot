"""Contract for Android device discovery and metadata access."""

from typing import Protocol

from word_madness_bot.domain.models import DeviceInfo


class DeviceGateway(Protocol):
    """Expose device information without leaking a concrete ADB implementation."""

    def list_devices(self) -> tuple[str, ...]:
        """Return serial numbers for available, authorized devices."""

        ...

    def get_device_info(self, serial: str) -> DeviceInfo:
        """Return metadata for the selected device serial."""

        ...

    def is_available(self, serial: str) -> bool:
        """Return whether the selected device is currently available."""

        ...
