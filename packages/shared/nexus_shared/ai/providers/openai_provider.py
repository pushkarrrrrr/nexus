"""OpenAI Model Provider Adapter.

Supports direct communication with OpenAI API and OpenAI-compatible endpoints
(e.g., vLLM, LM Studio, Azure OpenAI, OpenRouter) via asynchronous HTTP.
"""

import json
import re
import time
from collections.abc import AsyncIterator
from typing import Any, TypeVar

import httpx
from pydantic import BaseModel, ValidationError

from packages.shared.nexus_shared.ai.base import EmbeddingProvider, LLMProvider
from packages.shared.nexus_shared.ai.pricing import calculate_cost
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
    ModelUsage,
)

T = TypeVar("T", bound=BaseModel)


class OpenAIProvider(LLMProvider, EmbeddingProvider):
    """OpenAI and OpenAI-compatible API Provider."""

    def __init__(
        self,
        api_key: str = "",
        base_url: str = "https://api.openai.com/v1",
        default_model: str = "gpt-4o",
        default_embedding_model: str = "text-embedding-3-small",
        timeout_sec: float = 60.0,
    ) -> None:
        self.api_key = api_key
        self.base_url = base_url.rstrip("/")
        self.default_model = default_model
        self.default_embedding_model = default_embedding_model
        self.timeout_sec = timeout_sec

    @property
    def provider_name(self) -> str:
        return "openai"

    def _get_headers(self) -> dict[str, str]:
        headers = {"Content-Type": "application/json"}
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"
        return headers

    def _map_http_error(self, err: Exception) -> Exception:
        if isinstance(err, httpx.TimeoutException):
            return ModelTimeoutError(f"OpenAI request timed out: {err}")
        if isinstance(err, httpx.HTTPStatusError):
            status = err.response.status_code
            text = err.response.text
            if status == 429:
                return ModelRateLimitError(f"OpenAI rate limit exceeded (HTTP 429): {text}")
            return ModelProviderError(f"OpenAI HTTP error {status}: {text}")
        if isinstance(err, httpx.RequestError):
            return ModelProviderError(f"OpenAI connection error: {err}")
        return err

    async def complete(self, request: CompletionRequest) -> CompletionResponse:
        start_time = time.perf_counter()
        model_name = request.model or self.default_model

        messages: list[dict[str, str]] = []
        if request.system_prompt:
            messages.append({"role": "system", "content": request.system_prompt})
        messages.append({"role": "user", "content": request.prompt})

        payload: dict[str, Any] = {
            "model": model_name,
            "messages": messages,
            "temperature": request.temperature,
        }
        if request.max_tokens is not None:
            payload["max_tokens"] = request.max_tokens
        if request.stop:
            payload["stop"] = request.stop

        try:
            async with httpx.AsyncClient(timeout=self.timeout_sec) as client:
                res = await client.post(
                    f"{self.base_url}/chat/completions",
                    headers=self._get_headers(),
                    json=payload,
                )
                res.raise_for_status()
                data = res.json()
        except Exception as exc:
            raise self._map_http_error(exc) from exc

        content = data["choices"][0]["message"]["content"] or ""
        finish_reason = data["choices"][0].get("finish_reason", "stop")
        raw_usage = data.get("usage", {})
        prompt_tokens = raw_usage.get("prompt_tokens", len(request.prompt.split()))
        completion_tokens = raw_usage.get("completion_tokens", len(content.split()))
        total_tokens = raw_usage.get("total_tokens", prompt_tokens + completion_tokens)

        latency_ms = (time.perf_counter() - start_time) * 1000.0
        cost = calculate_cost(model_name, prompt_tokens, completion_tokens)

        return CompletionResponse(
            content=content,
            model=model_name,
            provider=self.provider_name,
            usage=ModelUsage(
                prompt_tokens=prompt_tokens,
                completion_tokens=completion_tokens,
                total_tokens=total_tokens,
                estimated_cost_usd=cost,
                latency_ms=round(latency_ms, 2),
            ),
            finish_reason=finish_reason,
        )

    async def stream_complete(self, request: CompletionRequest) -> AsyncIterator[str]:
        model_name = request.model or self.default_model
        messages: list[dict[str, str]] = []
        if request.system_prompt:
            messages.append({"role": "system", "content": request.system_prompt})
        messages.append({"role": "user", "content": request.prompt})

        payload: dict[str, Any] = {
            "model": model_name,
            "messages": messages,
            "temperature": request.temperature,
            "stream": True,
        }
        if request.max_tokens is not None:
            payload["max_tokens"] = request.max_tokens

        try:
            async with (
                httpx.AsyncClient(timeout=self.timeout_sec) as client,
                client.stream(
                    "POST",
                    f"{self.base_url}/chat/completions",
                    headers=self._get_headers(),
                    json=payload,
                ) as response,
            ):
                async for line in response.aiter_lines():
                    if not line or not line.startswith("data: "):
                        continue
                    data_str = line[6:].strip()
                    if data_str == "[DONE]":
                        break
                    try:
                        chunk = json.loads(data_str)
                        delta = chunk["choices"][0].get("delta", {})
                        text = delta.get("content")
                        if text:
                            yield text
                    except (json.JSONDecodeError, KeyError, IndexError):
                        continue
        except Exception as exc:
            raise self._map_http_error(exc) from exc

    async def complete_structured(
        self, request: CompletionRequest, response_schema: type[T]
    ) -> tuple[T, ModelUsage]:
        schema_json = json.dumps(response_schema.model_json_schema(), indent=2)
        system_instruction = (
            f"You are a strict structured reasoning engine. You must output only valid JSON "
            f"conforming exactly to the following JSON Schema:\n{schema_json}\n"
            f"Do not include explanation, markdown fences, or comments. Return pure JSON."
        )

        combined_system = (
            f"{request.system_prompt}\n\n{system_instruction}"
            if request.system_prompt
            else system_instruction
        )

        structured_req = CompletionRequest(
            prompt=request.prompt,
            model=request.model,
            system_prompt=combined_system,
            temperature=request.temperature or 0.1,
            max_tokens=request.max_tokens,
        )

        resp = await self.complete(structured_req)
        raw_text = resp.content.strip()

        # Sanitize potential markdown fences
        if raw_text.startswith("```"):
            raw_text = re.sub(r"^```(?:json)?\s*", "", raw_text)
            raw_text = re.sub(r"\s*```$", "", raw_text)
            raw_text = raw_text.strip()

        try:
            parsed_data = response_schema.model_validate_json(raw_text)
        except ValidationError as val_err:
            raise StructuredOutputValidationError(
                f"Failed to validate response against {response_schema.__name__}: {val_err}. "
                f"Raw output: {raw_text[:200]}"
            ) from val_err
        except Exception as parse_err:
            raise StructuredOutputValidationError(
                f"Invalid JSON returned: {parse_err}. Raw output: {raw_text[:200]}"
            ) from parse_err

        return parsed_data, resp.usage

    async def embed(self, request: EmbeddingRequest) -> EmbeddingResponse:
        model_name = request.model or self.default_embedding_model
        payload = {
            "model": model_name,
            "input": request.texts,
        }

        try:
            async with httpx.AsyncClient(timeout=self.timeout_sec) as client:
                res = await client.post(
                    f"{self.base_url}/embeddings",
                    headers=self._get_headers(),
                    json=payload,
                )
                res.raise_for_status()
                data = res.json()
        except Exception as exc:
            raise self._map_http_error(exc) from exc

        embeddings = [item["embedding"] for item in data.get("data", [])]
        total_tokens = data.get("usage", {}).get("total_tokens", 0)

        return EmbeddingResponse(
            embeddings=embeddings,
            model=model_name,
            provider=self.provider_name,
            total_tokens=total_tokens,
        )
