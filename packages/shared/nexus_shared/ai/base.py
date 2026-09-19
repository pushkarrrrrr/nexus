"""Abstract Base Classes for NEXUS Model Providers.

Strictly decouples the NEXUS operating system and agentic workflows
from any single proprietary or local model vendor.
"""

from abc import ABC, abstractmethod
from collections.abc import AsyncIterator
from typing import TypeVar

from pydantic import BaseModel

from packages.types.nexus_types.schemas import (
    CompletionRequest,
    CompletionResponse,
    EmbeddingRequest,
    EmbeddingResponse,
    ModelUsage,
)

T = TypeVar("T", bound=BaseModel)


class LLMProvider(ABC):
    """Abstract interface for LLM completions, streaming, and structured extraction."""

    @property
    @abstractmethod
    def provider_name(self) -> str:
        """Name of the provider (e.g., 'openai', 'anthropic', 'gemini', 'ollama', 'mock')."""
        ...

    @abstractmethod
    async def complete(self, request: CompletionRequest) -> CompletionResponse:
        """Execute a text completion request."""
        ...

    @abstractmethod
    def stream_complete(self, request: CompletionRequest) -> AsyncIterator[str]:
        """Stream completion tokens asynchronously."""
        ...

    @abstractmethod
    async def complete_structured(
        self, request: CompletionRequest, response_schema: type[T]
    ) -> tuple[T, ModelUsage]:
        """Execute a structured completion request validated against a Pydantic schema."""
        ...


class EmbeddingProvider(ABC):
    """Abstract interface for vector embeddings."""

    @property
    @abstractmethod
    def provider_name(self) -> str:
        """Name of the embedding provider."""
        ...

    @abstractmethod
    async def embed(self, request: EmbeddingRequest) -> EmbeddingResponse:
        """Generate vector embeddings for input texts."""
        ...
