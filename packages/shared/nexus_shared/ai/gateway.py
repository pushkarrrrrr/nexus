"""NEXUS Model Gateway Orchestrator.

The central model abstraction layer for NEXUS. Coordinates LLM providers,
embedding providers, structured output validation, retry with exponential backoff,
timeout enforcement, multi-provider fallback cascading, and telemetry accounting.
"""

import asyncio
import logging
import time
from collections.abc import AsyncIterator
from typing import Any, TypeVar

import httpx
from pydantic import BaseModel

from packages.config.nexus_config.settings import NexusSettings, get_settings
from packages.shared.nexus_shared.ai.base import EmbeddingProvider, LLMProvider
from packages.shared.nexus_shared.ai.providers.anthropic_provider import AnthropicProvider
from packages.shared.nexus_shared.ai.providers.gemini_provider import GeminiProvider
from packages.shared.nexus_shared.ai.providers.mock_provider import MockProvider
from packages.shared.nexus_shared.ai.providers.ollama_provider import OllamaProvider
from packages.shared.nexus_shared.ai.providers.openai_provider import OpenAIProvider
from packages.shared.nexus_shared.errors import (
    ModelProviderError,
    ModelRateLimitError,
    ModelTimeoutError,
    StructuredOutputValidationError,
)
from packages.types.nexus_types.schemas import (
    CompletionRequest,
    CompletionResponse,
    EmbeddingRequest,
    EmbeddingResponse,
    GatewayTelemetry,
    ModelUsage,
)

logger = logging.getLogger("nexus.ai.gateway")
T = TypeVar("T", bound=BaseModel)


class ModelGateway:
    """Enterprise AI Model Gateway with retry, timeout, fallback, and telemetry."""

    def __init__(self, settings: NexusSettings | None = None) -> None:
        self.settings = settings or get_settings()
        self._llm_providers: dict[str, LLMProvider] = {}
        self._embedding_providers: dict[str, EmbeddingProvider] = {}

        # In-memory telemetry accumulator
        self._total_requests: int = 0
        self._successful_requests: int = 0
        self._failed_requests: int = 0
        self._total_prompt_tokens: int = 0
        self._total_completion_tokens: int = 0
        self._total_tokens: int = 0
        self._total_cost_usd: float = 0.0
        self._total_latency_ms: float = 0.0
        self._retries_count: int = 0
        self._fallbacks_triggered: int = 0
        self._errors_by_type: dict[str, int] = {}
        self._requests_by_model: dict[str, int] = {}
        self._requests_by_provider: dict[str, int] = {}

        self._initialize_default_providers()

    def _initialize_default_providers(self) -> None:
        """Instantiate providers based on settings and environment."""
        # Always register mock provider for testing and deterministic fallbacks
        mock = MockProvider()
        self.register_llm_provider("mock", mock)
        self.register_embedding_provider("mock", mock)

        # OpenAI
        openai_p = OpenAIProvider(
            api_key=self.settings.openai_api_key or "",
            timeout_sec=self.settings.ai_request_timeout_sec,
        )
        self.register_llm_provider("openai", openai_p)
        self.register_embedding_provider("openai", openai_p)

        # Anthropic
        anthropic_p = AnthropicProvider(
            api_key=self.settings.anthropic_api_key or "",
            timeout_sec=self.settings.ai_request_timeout_sec,
        )
        self.register_llm_provider("anthropic", anthropic_p)

        # Gemini
        gemini_p = GeminiProvider(
            api_key=self.settings.gemini_api_key or "",
            timeout_sec=self.settings.ai_request_timeout_sec,
        )
        self.register_llm_provider("gemini", gemini_p)
        self.register_embedding_provider("gemini", gemini_p)

        # Ollama (Local)
        ollama_p = OllamaProvider(
            base_url=self.settings.ollama_base_url,
            timeout_sec=self.settings.ai_request_timeout_sec,
        )
        self.register_llm_provider("ollama", ollama_p)
        self.register_embedding_provider("ollama", ollama_p)

    def register_llm_provider(self, name: str, provider: LLMProvider) -> None:
        """Register or replace an LLM provider."""
        self._llm_providers[name.lower()] = provider
        logger.debug("Registered LLM provider: %s", name)

    def register_embedding_provider(self, name: str, provider: EmbeddingProvider) -> None:
        """Register or replace an Embedding provider."""
        self._embedding_providers[name.lower()] = provider
        logger.debug("Registered Embedding provider: %s", name)

    def get_llm_provider(self, name: str | None = None) -> LLMProvider:
        """Resolve LLM provider by name or system default."""
        target_name = (name or self.settings.default_ai_provider).lower()
        provider = self._llm_providers.get(target_name)
        if not provider:
            raise ModelProviderError(
                f"LLM provider '{target_name}' is not registered. Available: {list(self._llm_providers.keys())}"
            )
        # If default provider lacks API key in environment, fall back to mock
        if (
            isinstance(provider, (OpenAIProvider, AnthropicProvider, GeminiProvider))
            and not provider.api_key
            and "mock" in self._llm_providers
            and (name is None or name.lower() == self.settings.default_ai_provider.lower())
        ):
            return self._llm_providers["mock"]
        return provider

    def get_embedding_provider(self, name: str | None = None) -> EmbeddingProvider:
        """Resolve Embedding provider by name or system default."""
        target_name = (name or self.settings.default_ai_provider).lower()
        provider = self._embedding_providers.get(target_name)
        if not provider:
            if "mock" in self._embedding_providers:
                return self._embedding_providers["mock"]
            raise ModelProviderError(
                f"Embedding provider '{target_name}' is not registered. Available: {list(self._embedding_providers.keys())}"
            )
        # If default provider lacks API key in environment, fall back to mock
        if (
            isinstance(provider, (OpenAIProvider, GeminiProvider))
            and not provider.api_key
            and "mock" in self._embedding_providers
            and (name is None or name.lower() == self.settings.default_ai_provider.lower())
        ):
            return self._embedding_providers["mock"]
        return provider

    def list_providers(self) -> list[dict[str, Any]]:
        """List all registered providers and their configured status."""
        providers_meta: list[dict[str, Any]] = []
        for name, p in self._llm_providers.items():
            has_credentials = True
            default_model = "unknown"
            if isinstance(p, (OpenAIProvider, AnthropicProvider, GeminiProvider)):
                has_credentials = bool(p.api_key)
                default_model = p.default_model
            elif isinstance(p, (OllamaProvider, MockProvider)):
                default_model = p.default_model

            providers_meta.append(
                {
                    "name": name,
                    "type": "llm",
                    "default_model": default_model,
                    "is_configured": has_credentials,
                    "supports_embeddings": name in self._embedding_providers,
                    "is_default": name == self.settings.default_ai_provider.lower(),
                }
            )
        return providers_meta

    def _record_error(self, err_type: str) -> None:
        self._failed_requests += 1
        self._errors_by_type[err_type] = self._errors_by_type.get(err_type, 0) + 1

    def _record_success(self, provider_name: str, model_name: str, usage: ModelUsage) -> None:
        self._successful_requests += 1
        self._total_prompt_tokens += usage.prompt_tokens
        self._total_completion_tokens += usage.completion_tokens
        self._total_tokens += usage.total_tokens
        self._total_cost_usd += usage.estimated_cost_usd
        self._total_latency_ms += usage.latency_ms

        self._requests_by_provider[provider_name] = (
            self._requests_by_provider.get(provider_name, 0) + 1
        )
        self._requests_by_model[model_name] = self._requests_by_model.get(model_name, 0) + 1

    async def _execute_with_retry(
        self,
        provider: LLMProvider,
        coro_fn: Any,
        timeout_sec: float,
        max_retries: int,
    ) -> Any:
        """Execute async provider operation with timeout and exponential backoff retry."""
        attempt = 0
        backoff_sec = 0.5

        while True:
            try:
                return await asyncio.wait_for(coro_fn(), timeout=timeout_sec)
            except TimeoutError as te:
                attempt += 1
                self._record_error("timeout")
                logger.warning(
                    "Provider %s timed out after %ss (attempt %s/%s)",
                    provider.provider_name,
                    timeout_sec,
                    attempt,
                    max_retries + 1,
                )
                if attempt > max_retries:
                    raise ModelTimeoutError(
                        f"Provider {provider.provider_name} timed out after {max_retries + 1} attempts"
                    ) from te
                self._retries_count += 1
                await asyncio.sleep(backoff_sec)
                backoff_sec *= 2.0

            except ModelRateLimitError as rle:
                attempt += 1
                self._record_error("rate_limit")
                logger.warning(
                    "Provider %s hit rate limit (attempt %s/%s): %s",
                    provider.provider_name,
                    attempt,
                    max_retries + 1,
                    rle,
                )
                if attempt > max_retries:
                    raise
                self._retries_count += 1
                await asyncio.sleep(backoff_sec)
                backoff_sec *= 2.0

            except (ModelTimeoutError, httpx.TimeoutException) as te_err:
                attempt += 1
                self._record_error("timeout")
                if attempt > max_retries:
                    raise ModelTimeoutError(str(te_err)) from te_err
                self._retries_count += 1
                await asyncio.sleep(backoff_sec)
                backoff_sec *= 2.0

            except Exception as exc:
                self._record_error(type(exc).__name__)
                raise

    async def complete(
        self,
        request: CompletionRequest,
        provider_name: str | None = None,
        fallback_provider: str | None = None,
        timeout_sec: float | None = None,
        max_retries: int | None = None,
    ) -> CompletionResponse:
        """Execute text completion with retry, timeout, fallback cascading, and telemetry."""
        self._total_requests += 1
        timeout = timeout_sec or self.settings.ai_request_timeout_sec
        retries = max_retries if max_retries is not None else self.settings.ai_max_retries
        fallback = fallback_provider or self.settings.default_fallback_provider

        primary_provider = self.get_llm_provider(provider_name)

        try:
            response: CompletionResponse = await self._execute_with_retry(
                primary_provider,
                lambda: primary_provider.complete(request),
                timeout_sec=timeout,
                max_retries=retries,
            )
            self._record_success(response.provider, response.model, response.usage)
            return response

        except Exception as primary_exc:
            logger.error(
                "Primary provider '%s' failed: %s",
                primary_provider.provider_name,
                primary_exc,
            )

            if fallback and fallback.lower() != primary_provider.provider_name.lower():
                try:
                    fallback_p = self.get_llm_provider(fallback)
                    self._fallbacks_triggered += 1
                    logger.info(
                        "Cascading request to fallback provider '%s'",
                        fallback_p.provider_name,
                    )
                    # When cascading to fallback, do not enforce another full retry cycle
                    resp = await asyncio.wait_for(fallback_p.complete(request), timeout=timeout)
                    self._record_success(resp.provider, resp.model, resp.usage)
                    return resp
                except Exception as fb_exc:
                    self._record_error("fallback_failure")
                    raise ModelProviderError(
                        f"Both primary provider '{primary_provider.provider_name}' "
                        f"and fallback provider '{fallback}' failed. "
                        f"Primary: {primary_exc}. Fallback: {fb_exc}"
                    ) from fb_exc

            raise

    async def stream_complete(
        self,
        request: CompletionRequest,
        provider_name: str | None = None,
    ) -> AsyncIterator[str]:
        """Stream token chunks asynchronously from the designated provider."""
        self._total_requests += 1
        provider = self.get_llm_provider(provider_name)
        start_time = time.perf_counter()
        token_count = 0

        try:
            async for token in provider.stream_complete(request):
                token_count += 1
                yield token

            latency_ms = (time.perf_counter() - start_time) * 1000.0
            usage = ModelUsage(
                prompt_tokens=len(request.prompt.split()),
                completion_tokens=token_count,
                total_tokens=len(request.prompt.split()) + token_count,
                latency_ms=round(latency_ms, 2),
            )
            self._record_success(provider.provider_name, request.model or "stream", usage)

        except Exception as exc:
            self._record_error(type(exc).__name__)
            raise

    async def complete_structured(
        self,
        request: CompletionRequest,
        response_schema: type[T],
        provider_name: str | None = None,
        fallback_provider: str | None = None,
        timeout_sec: float | None = None,
        max_retries: int | None = None,
    ) -> tuple[T, ModelUsage]:
        """Execute structured reasoning request validated against a Pydantic schema."""
        self._total_requests += 1
        timeout = timeout_sec or self.settings.ai_request_timeout_sec
        retries = max_retries if max_retries is not None else self.settings.ai_max_retries
        fallback = fallback_provider or self.settings.default_fallback_provider

        primary_provider = self.get_llm_provider(provider_name)

        try:
            parsed_data, usage = await self._execute_with_retry(
                primary_provider,
                lambda: primary_provider.complete_structured(request, response_schema),
                timeout_sec=timeout,
                max_retries=retries,
            )
            self._record_success(
                primary_provider.provider_name, request.model or "structured", usage
            )
            return parsed_data, usage

        except (StructuredOutputValidationError, ModelProviderError, ModelTimeoutError) as exc:
            logger.warning(
                "Structured completion on '%s' encountered error: %s",
                primary_provider.provider_name,
                exc,
            )

            if fallback and fallback.lower() != primary_provider.provider_name.lower():
                try:
                    fallback_p = self.get_llm_provider(fallback)
                    self._fallbacks_triggered += 1
                    logger.info(
                        "Falling back structured completion to '%s'",
                        fallback_p.provider_name,
                    )
                    parsed_data, usage = await asyncio.wait_for(
                        fallback_p.complete_structured(request, response_schema),
                        timeout=timeout,
                    )
                    self._record_success(
                        fallback_p.provider_name, request.model or "structured", usage
                    )
                    return parsed_data, usage
                except Exception as fb_exc:
                    self._record_error("fallback_failure")
                    raise ModelProviderError(
                        f"Both primary '{primary_provider.provider_name}' and fallback '{fallback}' "
                        f"failed structured validation: {fb_exc}"
                    ) from fb_exc

            raise

    async def embed(
        self,
        request: EmbeddingRequest,
        provider_name: str | None = None,
        fallback_provider: str | None = None,
        timeout_sec: float | None = None,
    ) -> EmbeddingResponse:
        """Generate vector embeddings for input texts."""
        self._total_requests += 1
        timeout = timeout_sec or self.settings.ai_request_timeout_sec
        primary_provider = self.get_embedding_provider(provider_name)

        try:
            resp = await asyncio.wait_for(primary_provider.embed(request), timeout=timeout)
            self._successful_requests += 1
            self._total_prompt_tokens += resp.total_tokens
            self._total_tokens += resp.total_tokens
            return resp
        except Exception as exc:
            self._record_error(type(exc).__name__)
            fallback = fallback_provider or self.settings.default_fallback_provider
            if fallback and fallback.lower() != primary_provider.provider_name.lower():
                try:
                    fallback_p = self.get_embedding_provider(fallback)
                    self._fallbacks_triggered += 1
                    resp = await asyncio.wait_for(fallback_p.embed(request), timeout=timeout)
                    self._successful_requests += 1
                    return resp
                except Exception as fb_exc:
                    raise ModelProviderError(
                        f"Embedding failed across providers: {fb_exc}"
                    ) from fb_exc
            raise

    def get_telemetry(self) -> GatewayTelemetry:
        """Return aggregated usage, latency, error, and cost telemetry."""
        avg_latency = (
            (self._total_latency_ms / self._successful_requests)
            if self._successful_requests > 0
            else 0.0
        )

        return GatewayTelemetry(
            total_requests=self._total_requests,
            successful_requests=self._successful_requests,
            failed_requests=self._failed_requests,
            total_prompt_tokens=self._total_prompt_tokens,
            total_completion_tokens=self._total_completion_tokens,
            total_tokens=self._total_tokens,
            total_estimated_cost_usd=round(self._total_cost_usd, 6),
            total_cost_usd=round(self._total_cost_usd, 6),
            average_latency_ms=round(avg_latency, 2),
            active_providers=list(self._llm_providers.keys()),
            error_count=self._failed_requests,
            retry_count=self._retries_count,
            retries_count=self._retries_count,
            fallback_count=self._fallbacks_triggered,
            fallbacks_triggered=self._fallbacks_triggered,
            errors_by_type=dict(self._errors_by_type),
            requests_by_model=dict(self._requests_by_model),
            requests_by_provider=dict(self._requests_by_provider),
        )

    def reset_telemetry(self) -> None:
        """Reset telemetry counters (used in testing and benchmarks)."""
        self._total_requests = 0
        self._successful_requests = 0
        self._failed_requests = 0
        self._total_prompt_tokens = 0
        self._total_completion_tokens = 0
        self._total_tokens = 0
        self._total_cost_usd = 0.0
        self._total_latency_ms = 0.0
        self._retries_count = 0
        self._fallbacks_triggered = 0
        self._errors_by_type.clear()
        self._requests_by_model.clear()
        self._requests_by_provider.clear()


# Global Gateway Singleton
_gateway_instance: ModelGateway | None = None


def get_model_gateway() -> ModelGateway:
    """Get the global ModelGateway instance."""
    global _gateway_instance
    if _gateway_instance is None:
        _gateway_instance = ModelGateway()
    return _gateway_instance
