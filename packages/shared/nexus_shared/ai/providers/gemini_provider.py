"""Google Gemini Model Provider Adapter.

Connects to the Google Generative Language v1beta REST API for Gemini 1.5/2.0 models
and text embedding models via direct asynchronous HTTP.
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


class GeminiProvider(LLMProvider, EmbeddingProvider):
    """Google Gemini API Provider."""

    def __init__(
        self,
        api_key: str = "",
        base_url: str = "https://generativelanguage.googleapis.com/v1beta",
        default_model: str = "gemini-1.5-pro",
        default_embedding_model: str = "text-embedding-004",
        timeout_sec: float = 60.0,
    ) -> None:
        self.api_key = api_key
        self.base_url = base_url.rstrip("/")
        self.default_model = default_model
        self.default_embedding_model = default_embedding_model
        self.timeout_sec = timeout_sec

    @property
    def provider_name(self) -> str:
        return "gemini"

    def _get_headers(self) -> dict[str, str]:
        headers = {"Content-Type": "application/json"}
        if self.api_key:
            headers["x-goog-api-key"] = self.api_key
        return headers

    def _map_http_error(self, err: Exception) -> Exception:
        if isinstance(err, httpx.TimeoutException):
            return ModelTimeoutError(f"Gemini request timed out: {err}")
        if isinstance(err, httpx.HTTPStatusError):
            status = err.response.status_code
            text = err.response.text
            if status == 429:
                return ModelRateLimitError(f"Gemini rate limit exceeded (HTTP 429): {text}")
            return ModelProviderError(f"Gemini HTTP error {status}: {text}")
        if isinstance(err, httpx.RequestError):
            return ModelProviderError(f"Gemini connection error: {err}")
        return err

    async def complete(self, request: CompletionRequest) -> CompletionResponse:
        start_time = time.perf_counter()
        model_name = request.model or self.default_model

        payload: dict[str, Any] = {
            "contents": [
                {
                    "role": "user",
                    "parts": [{"text": request.prompt}],
                }
            ],
            "generationConfig": {
                "temperature": request.temperature,
            },
        }
        if request.max_tokens is not None:
            payload["generationConfig"]["maxOutputTokens"] = request.max_tokens
        if request.stop:
            payload["generationConfig"]["stopSequences"] = request.stop
        if request.system_prompt:
            payload["systemInstruction"] = {
                "parts": [{"text": request.system_prompt}],
            }

        url = f"{self.base_url}/models/{model_name}:generateContent"

        try:
            async with httpx.AsyncClient(timeout=self.timeout_sec) as client:
                res = await client.post(
                    url,
                    headers=self._get_headers(),
                    json=payload,
                )
                res.raise_for_status()
                data = res.json()
        except Exception as exc:
            raise self._map_http_error(exc) from exc

        candidates = data.get("candidates", [])
        content = ""
        finish_reason = "stop"
        if candidates:
            parts = candidates[0].get("content", {}).get("parts", [])
            content = "".join(p.get("text", "") for p in parts)
            finish_reason = candidates[0].get("finishReason", "STOP").lower()

        usage_meta = data.get("usageMetadata", {})
        prompt_tokens = usage_meta.get("promptTokenCount", len(request.prompt.split()))
        completion_tokens = usage_meta.get("candidatesTokenCount", len(content.split()))
        total_tokens = usage_meta.get("totalTokenCount", prompt_tokens + completion_tokens)

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
        payload: dict[str, Any] = {
            "contents": [
                {
                    "role": "user",
                    "parts": [{"text": request.prompt}],
                }
            ],
            "generationConfig": {
                "temperature": request.temperature,
            },
        }
        if request.max_tokens is not None:
            payload["generationConfig"]["maxOutputTokens"] = request.max_tokens
        if request.system_prompt:
            payload["systemInstruction"] = {
                "parts": [{"text": request.system_prompt}],
            }

        url = f"{self.base_url}/models/{model_name}:streamGenerateContent?alt=sse"

        try:
            async with (
                httpx.AsyncClient(timeout=self.timeout_sec) as client,
                client.stream(
                    "POST",
                    url,
                    headers=self._get_headers(),
                    json=payload,
                ) as response,
            ):
                response.raise_for_status()
                async for line in response.aiter_lines():
                    if not line or not line.startswith("data: "):
                        continue
                    data_str = line[6:].strip()
                    try:
                        chunk = json.loads(data_str)
                        candidates = chunk.get("candidates", [])
                        if candidates:
                            parts = candidates[0].get("content", {}).get("parts", [])
                            for p in parts:
                                text = p.get("text", "")
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
        clean_model = model_name if model_name.startswith("models/") else f"models/{model_name}"

        url = f"{self.base_url}/{clean_model}:batchEmbedContents"
        requests = [
            {
                "model": clean_model,
                "content": {"parts": [{"text": text}]},
            }
            for text in request.texts
        ]

        try:
            async with httpx.AsyncClient(timeout=self.timeout_sec) as client:
                res = await client.post(
                    url,
                    headers=self._get_headers(),
                    json={"requests": requests},
                )
                res.raise_for_status()
                data = res.json()
        except Exception as exc:
            raise self._map_http_error(exc) from exc

        embeddings = [item.get("values", []) for item in data.get("embeddings", [])]
        total_tokens = sum(len(t.split()) for t in request.texts) * 2

        return EmbeddingResponse(
            embeddings=embeddings,
            model=model_name,
            provider=self.provider_name,
            total_tokens=total_tokens,
        )
