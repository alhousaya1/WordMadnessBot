"""Typed exceptions reported across production architecture boundaries."""


class WordMadnessError(Exception):
    """Base exception for expected production failures."""


class ConfigurationError(WordMadnessError):
    """Raised when runtime configuration is invalid."""


class DomainValidationError(WordMadnessError, ValueError):
    """Raised when a domain value violates an invariant."""


class PortError(WordMadnessError):
    """Base exception for replaceable boundary failures."""
