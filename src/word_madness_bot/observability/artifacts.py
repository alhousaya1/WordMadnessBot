"""Configuration-controlled diagnostic artifact storage and retention."""

import logging
from pathlib import Path

from word_madness_bot.observability.events import EventName, StructuredEvent, log_event

_LOGGER = logging.getLogger(__name__)


class ArtifactManager:
    """Persist bounded diagnostic artifacts only when explicitly enabled."""

    def __init__(
        self,
        directory: Path,
        *,
        enabled: bool,
        maximum_files: int = 100,
        maximum_bytes: int = 100_000_000,
    ) -> None:
        if maximum_files <= 0 or maximum_bytes <= 0:
            raise ValueError("artifact retention limits must be positive")
        self._directory = directory.expanduser().resolve()
        self._enabled = enabled
        self._maximum_files = maximum_files
        self._maximum_bytes = maximum_bytes

    def save(self, filename: str, data: bytes) -> Path | None:
        """Atomically save bytes under a safe basename and enforce retention."""

        if not self._enabled:
            return None
        if not data:
            raise ValueError("diagnostic artifact cannot be empty")
        safe_name = Path(filename).name
        if safe_name in {"", ".", ".."}:
            raise ValueError("diagnostic artifact filename is invalid")
        self._directory.mkdir(parents=True, exist_ok=True)
        destination = self._directory / safe_name
        temporary = destination.with_suffix(f"{destination.suffix}.tmp")
        temporary.write_bytes(data)
        temporary.replace(destination)
        self._enforce_retention()
        log_event(
            _LOGGER,
            logging.DEBUG,
            StructuredEvent(
                EventName.ARTIFACT_SAVED, {"path": str(destination), "bytes": len(data)}
            ),
            "Diagnostic artifact saved",
        )
        return destination

    def _enforce_retention(self) -> None:
        files = sorted(
            (
                path
                for path in self._directory.iterdir()
                if path.is_file() and not path.name.endswith(".tmp")
            ),
            key=lambda path: (path.stat().st_mtime_ns, path.name),
        )
        total_bytes = sum(path.stat().st_size for path in files)
        while files and (len(files) > self._maximum_files or total_bytes > self._maximum_bytes):
            oldest = files.pop(0)
            size = oldest.stat().st_size
            oldest.unlink(missing_ok=True)
            total_bytes -= size
