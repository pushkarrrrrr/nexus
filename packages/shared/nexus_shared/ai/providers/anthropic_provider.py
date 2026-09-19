"""Anthropic Model Provider Adapter.

Connects to the Anthropic Messages API for Claude-3, Claude-3.5, and Claude-3.7 models
via direct asynchronous HTTP.
"""

import json
import time
from collections.abc import AsyncIterator
from typing import Any, TypeVar

import httpx
from pydantic import BaseModel, ValidationError

from packages.shared.nexus_shared.ai.base import LLMProvider
from packages.shared.nexus_shared.ai.json_extractor import extract_json_from_text
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
    ModelUsage,
)

T = TypeVar("T", bound=BaseModel)


class AnthropicProvider(LLMProvider):
    """Anthropic Claude API Provider."""

    def __init__(
        self,
        api_key: str = "",
        base_url: str = "https://api.anthropic.com/v1",
        default_model: str = "claude-3-5-sonnet-20241022",
        timeout_sec: float = 60.0,
    ) -> None:
        self.api_key = api_key
        self.base_url = base_url.rstrip("/")
        self.default_model = default_model
        self.timeout_sec = timeout_sec

    @property
    def provider_name(self) -> str:
        return "anthropic"

    def _get_headers(self) -> dict[str, str]:
        headers = {
            "Content-Type": "application/json",
            "anthropic-version": "2023-06-01",
        }
        if self.api_key:
            headers["x-api-key"] = self.api_key
        return headers

    def _map_http_error(self, err: Exception) -> Exception:
        if isinstance(err, httpx.TimeoutException):
            return ModelTimeoutError(f"Anthropic request timed out: {err}")
        if isinstance(err, httpx.HTTPStatusError):
            status = err.response.status_code
            text = err.response.text
            if status == 429:
                return ModelRateLimitError(f"Anthropic rate limit exceeded (HTTP 429): {text}")
            return ModelProviderError(f"Anthropic HTTP error {status}: {text}")
        if isinstance(err, httpx.RequestError):
            return ModelProviderError(f"Anthropic connection error: {err}")
        return err

    async def complete(self, request: CompletionRequest) -> CompletionResponse:
        start_time = time.perf_counter()
        model_name = request.model or self.default_model

        payload: dict[str, Any] = {
            "model": model_name,
            "messages": [{"role": "user", "content": request.prompt}],
            "max_tokens": request.max_tokens or 4096,
            "temperature": request.temperature,
        }
        if request.system_prompt:
            payload["system"] = request.system_prompt
        if request.stop:
            payload["stop_sequences"] = request.stop

        try:
            async with httpx.AsyncClient(timeout=self.timeout_sec) as client:
                res = await client.post(
                    f"{self.base_url}/messages",
                    headers=self._get_headers(),
                    json=payload,
                )
                res.raise_for_status()
                data = res.json()
        except Exception as exc:
            raise self._map_http_error(exc) from exc

        content_blocks = data.get("content", [])
        text_pieces = [b.get("text", "") for b in content_blocks if b.get("type") == "text"]
        content = "".join(text_pieces)
        finish_reason = data.get("stop_reason", "end_turn")

        raw_usage = data.get("usage", {})
        prompt_tokens = raw_usage.get("input_tokens", len(request.prompt.split()))
        completion_tokens = raw_usage.get("output_tokens", len(content.split()))
        total_tokens = prompt_tokens + completion_tokens

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
            "model": model_name,
            "messages": [{"role": "user", "content": request.prompt}],
            "max_tokens": request.max_tokens or 4096,
            "temperature": request.temperature,
            "stream": True,
        }
        if request.system_prompt:
            payload["system"] = request.system_prompt

        try:
            async with (
                httpx.AsyncClient(timeout=self.timeout_sec) as client,
                client.stream(
                    "POST",
                    f"{self.base_url}/messages",
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
                        event = json.loads(data_str)
                        event_type = event.get("type")
                        if event_type == "error":
                            err_info = event.get("error", {})
                            raise ModelProviderError(
                                f"Anthropic streaming error: {err_info.get('message', err_info)}"
                            )
                        if event_type == "content_block_delta":
                            delta = event.get("delta", {})
                            if delta.get("type") == "text_delta":
                                yield delta.get("text", "")
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
            max_tokens=request.max_tokens or 4096,
        )

        resp = await self.complete(structured_req)
        clean_json = extract_json_from_text(resp.content)

        try:
            parsed_data = response_schema.model_validate_json(clean_json)
        except ValidationError as val_err:
            raise StructuredOutputValidationError(
                f"Failed to validate response against {response_schema.__name__}: {val_err}. "
                f"Raw output: {clean_json[:200]}"
            ) from val_err
        except Exception as parse_err:
            raise StructuredOutputValidationError(
                f"Invalid JSON returned: {parse_err}. Raw output: {clean_json[:200]}"
            ) from parse_err

        return parsed_data, resp.usage
