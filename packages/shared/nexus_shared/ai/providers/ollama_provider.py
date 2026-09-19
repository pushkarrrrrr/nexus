"""Ollama Local Model Provider Adapter.

Connects to local Ollama daemon for open-weights models (e.g., Llama 3.1, Mistral,
DeepSeek, Qwen) and local embeddings (nomic-embed-text) via asynchronous HTTP.
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


class OllamaProvider(LLMProvider, EmbeddingProvider):
    """Local Ollama Provider."""

    def __init__(
        self,
        base_url: str = "http://localhost:11434",
        default_model: str = "llama3.1",
        default_embedding_model: str = "nomic-embed-text",
        timeout_sec: float = 120.0,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.default_model = default_model
        self.default_embedding_model = default_embedding_model
        self.timeout_sec = timeout_sec

    @property
    def provider_name(self) -> str:
        return "ollama"

    def _map_http_error(self, err: Exception) -> Exception:
        if isinstance(err, httpx.TimeoutException):
            return ModelTimeoutError(f"Ollama request timed out: {err}")
        if isinstance(err, httpx.HTTPStatusError):
            status = err.response.status_code
            text = err.response.text
            if status == 429:
                return ModelRateLimitError(f"Ollama rate limit exceeded (HTTP 429): {text}")
            return ModelProviderError(f"Ollama HTTP error {status}: {text}")
        if isinstance(err, httpx.RequestError):
            return ModelProviderError(f"Ollama connection error (is daemon running?): {err}")
        return err

    async def complete(self, request: CompletionRequest) -> CompletionResponse:
        start_time = time.perf_counter()
        model_name = request.model or self.default_model

        messages: list[dict[str, str]] = []
        if request.system_prompt:
            messages.append({"role": "system", "content": request.system_prompt})
        messages.append({"role": "user", "content": request.prompt})

        options: dict[str, Any] = {"temperature": request.temperature}
        if request.max_tokens is not None:
            options["num_predict"] = request.max_tokens
        if request.stop:
            options["stop"] = request.stop

        payload: dict[str, Any] = {
            "model": model_name,
            "messages": messages,
            "stream": False,
            "options": options,
        }

        try:
            async with httpx.AsyncClient(timeout=self.timeout_sec) as client:
                res = await client.post(f"{self.base_url}/api/chat", json=payload)
                res.raise_for_status()
                data = res.json()
        except Exception as exc:
            raise self._map_http_error(exc) from exc

        content = data.get("message", {}).get("content", "")
        prompt_tokens = data.get("prompt_eval_count", len(request.prompt.split()))
        completion_tokens = data.get("eval_count", len(content.split()))
        total_tokens = prompt_tokens + completion_tokens

        latency_ms = (time.perf_counter() - start_time) * 1000.0
        # Local models have 0.0 dollar cost
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
            finish_reason="stop",
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
            "stream": True,
            "options": {"temperature": request.temperature},
        }
        if request.max_tokens is not None:
            payload["options"]["num_predict"] = request.max_tokens

        try:
            async with (
                httpx.AsyncClient(timeout=self.timeout_sec) as client,
                client.stream(
                    "POST",
                    f"{self.base_url}/api/chat",
                    json=payload,
                ) as response,
            ):
                response.raise_for_status()
                async for line in response.aiter_lines():
                    if not line:
                        continue
                    try:
                        chunk = json.loads(line)
                        msg = chunk.get("message", {})
                        text = msg.get("content")
                        if text:
                            yield text
                    except (json.JSONDecodeError, KeyError):
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

        # Support Ollama /api/embed (batch)
        payload = {
            "model": model_name,
            "input": request.texts,
        }

        try:
            async with httpx.AsyncClient(timeout=self.timeout_sec) as client:
                res = await client.post(f"{self.base_url}/api/embed", json=payload)
                if res.status_code == 200:
                    data = res.json()
                    embeddings = data.get("embeddings", [])
                else:
                    # Fallback to single /api/embeddings endpoint in sequence
                    embeddings = []
                    for text in request.texts:
                        single_res = await client.post(
                            f"{self.base_url}/api/embeddings",
                            json={"model": model_name, "prompt": text},
                        )
                        single_res.raise_for_status()
                        embeddings.append(single_res.json().get("embedding", []))
        except Exception as exc:
            raise self._map_http_error(exc) from exc

        total_tokens = sum(len(t.split()) for t in request.texts) * 2

        return EmbeddingResponse(
            embeddings=embeddings,
            model=model_name,
            provider=self.provider_name,
            total_tokens=total_tokens,
        )
