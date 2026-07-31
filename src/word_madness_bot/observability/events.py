"""Stable structured event vocabulary shared by production subsystems."""

import logging
from collections.abc import Mapping
from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any


class EventName(StrEnum):
    """Machine-readable names for major subsystem lifecycle events."""

    APPLICATION_START = "application.start"
    APPLICATION_STOP = "application.stop"
    SCREENSHOT_CAPTURE = "capture.screenshot"
    VISION_PIPELINE = "vision.pipeline"
    STATE_CLASSIFICATION = "state.classification"
    DATABASE_LOOKUP = "database.lookup"
    SWIPE_PLANNING = "swipe.planning"
    DECISION_ENGINE = "decision.engine"
    COMMAND_EXECUTION = "command.execution"
    HEALTH_REPORT = "health.report"
    DIAGNOSTICS_REPORT = "diagnostics.report"
    ARTIFACT_SAVED = "artifact.saved"


@dataclass(frozen=True, slots=True)
class StructuredEvent:
    """A validated event name and serializable structured fields."""

    name: EventName
    fields: Mapping[str, Any] = field(default_factory=dict)


def log_event(logger: logging.Logger, level: int, event: StructuredEvent, message: str) -> None:
    """Emit one structured event through standard logging without formatting payload text."""

    logger.log(level, message, extra={"event": event.name.value, **dict(event.fields)})
