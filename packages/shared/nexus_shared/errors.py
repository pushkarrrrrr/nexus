"""
NEXUS Standardized Domain Exceptions
"""

from typing import Any


class NexusError(Exception):
    """Base exception for all NEXUS domain errors."""

    def __init__(self, message: str, details: dict[str, Any] | None = None):
        super().__init__(message)
        self.message = message
        self.details = details or {}


class ConfigError(NexusError):
    """Raised when environment or runtime configuration is invalid."""


class DatabaseConnectionError(NexusError):
    """Raised when database connection or health check fails."""


class PolicyViolationError(NexusError):
    """Raised when an action violates safety policy or risk gating."""


class ToolExecutionError(NexusError):
    """Raised when a tool execution fails or encounters a timeout."""


class SnapshotNotFoundError(NexusError):
    """Raised when attempting rollback but pre-execution snapshot is missing."""


class RollbackFailedError(NexusError):
    """Raised when a state restoration operation fails."""


class InvalidStateTransitionError(NexusError):
    """Raised when an invalid task or step state transition is attempted."""


class TaskNotFoundError(NexusError):
    """Raised when a requested task or step cannot be found."""


class ModelProviderError(NexusError):
    """Raised when an external model provider encounters an unrecoverable failure."""


class ModelTimeoutError(NexusError):
    """Raised when a model completion or embedding request times out."""


class ModelRateLimitError(NexusError):
    """Raised when a model provider returns a rate limit (HTTP 429)."""


class StructuredOutputValidationError(NexusError):
    """Raised when an LLM response cannot be validated against the requested Pydantic schema."""


class PromptTemplateError(NexusError):
    """Raised when prompt interpolation fails due to missing or invalid variables."""
