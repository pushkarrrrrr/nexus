"""Deterministic Mock Model Provider Adapter.

Provides testable, reproducible, and controllable completions, streaming tokens,
structured outputs, and embeddings without requiring external API keys.
"""

import asyncio
import time
from collections.abc import AsyncIterator
from typing import Any, TypeVar

from pydantic import BaseModel

from packages.shared.nexus_shared.ai.base import EmbeddingProvider, LLMProvider
from packages.shared.nexus_shared.ai.pricing import calculate_cost
from packages.shared.nexus_shared.errors import (
    ModelProviderError,
    ModelRateLimitError,
    ModelTimeoutError,
)
from packages.types.nexus_types.schemas import (
    AgentFinalResponse,
    AgentIntent,
    AgentPlan,
    AgentToolCall,
    AgentToolResult,
    CompletionRequest,
    CompletionResponse,
    EmbeddingRequest,
    EmbeddingResponse,
    ModelUsage,
    PlanStep,
    RiskLevel,
)

T = TypeVar("T", bound=BaseModel)


class MockProvider(LLMProvider, EmbeddingProvider):
    """Mock Provider for deterministic unit and integration tests."""

    def __init__(
        self,
        provider_name: str = "mock",
        default_model: str = "mock-model",
        failure_mode: str | None = None,
        fail_count: int = 0,
        simulated_latency_sec: float = 0.0,
    ) -> None:
        self._provider_name = provider_name
        self.default_model = default_model
        self.failure_mode = failure_mode  # 'rate_limit', 'timeout', 'server_error'
        self.fail_count = fail_count  # Fail first N times, then succeed
        self.call_count = 0
        self.simulated_latency_sec = simulated_latency_sec

    @property
    def provider_name(self) -> str:
        return self._provider_name

    def _check_simulated_failures(self) -> None:
        """Evaluate if request should fail based on failure_mode."""
        self.call_count += 1
        if self.fail_count > 0:
            if self.call_count <= self.fail_count:
                if self.failure_mode == "rate_limit":
                    raise ModelRateLimitError("Mock provider simulated rate limit (HTTP 429)")
                if self.failure_mode == "timeout":
                    raise ModelTimeoutError("Mock provider simulated read timeout")
                raise ModelProviderError("Mock provider simulated transient 500 error")
            return

        if self.failure_mode == "rate_limit":
            raise ModelRateLimitError("Mock provider simulated rate limit (HTTP 429)")
        if self.failure_mode == "timeout":
            raise ModelTimeoutError("Mock provider simulated read timeout")
        if self.failure_mode == "server_error":
            raise ModelProviderError("Mock provider simulated 500 internal server error")

    async def complete(self, request: CompletionRequest) -> CompletionResponse:
        start_time = time.perf_counter()
        if self.simulated_latency_sec > 0:
            await asyncio.sleep(self.simulated_latency_sec)

        self._check_simulated_failures()

        model_name = request.model or self.default_model
        prompt_tokens = len(request.prompt.split()) + 10
        content = f"[MOCK COMPLETION] Response to: '{request.prompt[:50]}...'"
        completion_tokens = len(content.split())
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
            finish_reason="stop",
        )

    async def stream_complete(self, request: CompletionRequest) -> AsyncIterator[str]:
        self._check_simulated_failures()
        chunks = ["[MOCK", " STREAMING", " TOKENS", " VERIFIED]"]
        for chunk in chunks:
            if self.simulated_latency_sec > 0:
                await asyncio.sleep(self.simulated_latency_sec / len(chunks))
            yield chunk

    async def complete_structured(
        self, request: CompletionRequest, response_schema: type[T]
    ) -> tuple[T, ModelUsage]:
        start_time = time.perf_counter()
        if self.simulated_latency_sec > 0:
            await asyncio.sleep(self.simulated_latency_sec)

        self._check_simulated_failures()

        model_name = request.model or self.default_model
        prompt_tokens = len(request.prompt.split()) + 20

        # Synthesize schema-compliant mock objects
        mock_instance: Any
        if response_schema == AgentIntent:
            mock_instance = AgentIntent(
                goal=request.prompt,
                primary_intent="execute_task",
                domain="system",
                entities=["workspace", "terminal"],
                risk_level=RiskLevel.LOW,
                confidence=0.98,
                requires_tools=True,
            )
        elif response_schema == AgentPlan:
            mock_instance = AgentPlan(
                goal=request.prompt,
                rationale="Decomposed into 2 sequential execution steps",
                estimated_complexity="low",
                steps=[
                    PlanStep(
                        id="step_1",
                        name="Inspect environment configuration",
                        agent="planner",
                        tool="file_reader",
                        input={"target": "config"},
                        dependencies=[],
                        risk_level=RiskLevel.LOW,
                    ),
                    PlanStep(
                        id="step_2",
                        name="Execute target operation",
                        agent="executor",
                        tool="terminal_runner",
                        input={"command": "echo test"},
                        dependencies=["step_1"],
                        risk_level=RiskLevel.LOW,
                    ),
                ],
            )
        elif response_schema == AgentToolCall:
            mock_instance = AgentToolCall(
                tool_name="terminal_runner",
                arguments={"command": "pytest"},
                rationale="Run validation test suite",
                expected_output="Test execution summary",
                reversibility=False,
                risk_level=RiskLevel.LOW,
            )
        elif response_schema == AgentToolResult:
            mock_instance = AgentToolResult(
                tool_name="terminal_runner",
                success=True,
                data={"exit_code": 0, "output": "All tests passed"},
                error=None,
                duration_ms=45.2,
            )
        elif response_schema == AgentFinalResponse:
            mock_instance = AgentFinalResponse(
                answer="Operation completed successfully with deterministic verification.",
                summary=f"Processed goal: {request.prompt[:60]}",
                artifacts=["output.log"],
                follow_up_suggestions=["View audit timeline", "Inspect system metrics"],
            )
        else:
            # Fallback reflection for arbitrary Pydantic schema
            mock_instance = response_schema.model_validate({})

        completion_tokens = 50
        total_tokens = prompt_tokens + completion_tokens
        latency_ms = (time.perf_counter() - start_time) * 1000.0
        cost = calculate_cost(model_name, prompt_tokens, completion_tokens)

        usage = ModelUsage(
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
            total_tokens=total_tokens,
            estimated_cost_usd=cost,
            latency_ms=round(latency_ms, 2),
        )

        return mock_instance, usage

    async def embed(self, request: EmbeddingRequest) -> EmbeddingResponse:
        self._check_simulated_failures()
        model_name = request.model or "nomic-embed-text"
        dim = 1536
        # Generate deterministic synthetic vectors
        embeddings = [[0.01 * (i + 1)] * dim for i in range(len(request.texts))]
        total_tokens = sum(len(t.split()) for t in request.texts) * 2

        return EmbeddingResponse(
            embeddings=embeddings,
            model=model_name,
            provider=self.provider_name,
            total_tokens=total_tokens,
        )
