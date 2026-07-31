"""Domain exception taxonomy used to report failures upward."""

from dataclasses import dataclass


class WordMadnessError(Exception):
    """Base class for expected application failures."""


class ConfigurationError(WordMadnessError):
    """Raised when runtime configuration is invalid."""


class DeviceError(WordMadnessError):
    """Raised when an Android device operation cannot complete."""


class CaptureError(WordMadnessError):
    """Raised when a screenshot cannot be acquired or decoded."""


class VisionError(WordMadnessError):
    """Raised when image analysis cannot produce a valid result."""


class RepositoryError(WordMadnessError):
    """Raised when level data cannot be accessed or validated."""


@dataclass(frozen=True, slots=True)
class ValidationIssue:
    """One precise validation failure within an external data document."""

    path: str
    message: str
    code: str

    def __str__(self) -> str:
        """Render the issue as a stable, human-readable diagnostic."""

        return f"{self.path}: {self.message} [{self.code}]"


class DatabaseValidationError(RepositoryError):
    """Raised when a level database violates its schema or semantic rules."""

    def __init__(self, source: str, issues: tuple[ValidationIssue, ...]) -> None:
        if not issues:
            raise ValueError("database validation error requires at least one issue")
        self.source = source
        self.issues = issues
        details = "; ".join(str(issue) for issue in issues)
        super().__init__(f"Invalid level database {source!r}: {details}")


class LevelNotFoundError(RepositoryError):
    """Raised when no stored definition exists for a level."""


class SwipePlanningError(WordMadnessError):
    """Raised when a word cannot be converted into a safe path."""


class InputExecutionError(WordMadnessError):
    """Raised when a completed input action cannot be executed."""
