"""NEXUS AI Gateway REST API Routes.

Provides endpoints for model discovery, unified LLM completions, structured agent reasoning,
vector embeddings, prompt template inspection, and gateway telemetry.
"""

from typing import Any, Literal

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel

from packages.shared.nexus_shared.ai.gateway import get_model_gateway
from packages.shared.nexus_shared.ai.prompt_manager import get_prompt_manager
from packages.shared.nexus_shared.errors import (
    ModelProviderError,
    ModelRateLimitError,
    ModelTimeoutError,
    StructuredOutputValidationError,
)
from packages.shared.nexus_shared.models import UserModel
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
    GatewayTelemetry,
    PromptTemplate,
)
from services.api.nexus_api.auth.dependencies import get_current_user

ai_router = APIRouter(prefix="/ai", tags=["ai"])


class StructuredAIRequest(BaseModel):
    prompt: str
    schema_type: Literal["intent", "plan", "tool_call", "tool_result", "final_response"]
    model: str | None = None
    provider: str | None = None
    fallback_provider: str | None = None
    system_prompt: str | None = None
    temperature: float = 0.1
    max_tokens: int = 4096


class StructuredAIResponse(BaseModel):
    schema_type: str
    data: dict[str, Any]
    usage: dict[str, Any]


@ai_router.get("/models")
async def list_models() -> dict[str, Any]:
    """List all registered AI providers, capabilities, and active default models."""
    gateway = get_model_gateway()
    return {
        "providers": gateway.list_providers(),
        "default_provider": gateway.settings.default_ai_provider,
        "default_fallback_provider": gateway.settings.default_fallback_provider,
    }


@ai_router.post("/complete", response_model=CompletionResponse)
async def complete_text(
    request: CompletionRequest,
    provider: str | None = Query(None, description="Explicit provider override"),
    fallback: str | None = Query(None, description="Explicit fallback provider override"),
    current_user: UserModel = Depends(get_current_user),
) -> CompletionResponse:
    """Execute LLM text completion via the NEXUS Model Gateway."""
    gateway = get_model_gateway()
    target_provider = provider or (request.provider.value if request.provider else None)

    try:
        return await gateway.complete(
            request,
            provider_name=target_provider,
            fallback_provider=fallback,
            timeout_sec=request.timeout_sec,
        )
    except ModelRateLimitError as rle:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail=f"Rate limit exceeded: {rle}",
        ) from rle
    except ModelTimeoutError as mte:
        raise HTTPException(
            status_code=status.HTTP_504_GATEWAY_TIMEOUT,
            detail=f"Model execution timed out: {mte}",
        ) from mte
    except ModelProviderError as mpe:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"Provider error: {mpe}",
        ) from mpe
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Internal gateway error: {exc}",
        ) from exc


@ai_router.post("/structured", response_model=StructuredAIResponse)
async def complete_structured(
    request: StructuredAIRequest,
    current_user: UserModel = Depends(get_current_user),
) -> StructuredAIResponse:
    """Execute structured reasoning validated strictly against Pydantic schema."""
    gateway = get_model_gateway()

    schema_map: dict[str, type[Any]] = {
        "intent": AgentIntent,
        "plan": AgentPlan,
        "tool_call": AgentToolCall,
        "tool_result": AgentToolResult,
        "final_response": AgentFinalResponse,
    }

    schema_cls = schema_map.get(request.schema_type)
    if not schema_cls:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Unsupported schema type '{request.schema_type}'. Allowed: {list(schema_map.keys())}",
        )

    comp_req = CompletionRequest(
        prompt=request.prompt,
        system_prompt=request.system_prompt,
        model=request.model,
        temperature=request.temperature,
        max_tokens=request.max_tokens,
    )

    try:
        parsed_obj, usage = await gateway.complete_structured(
            comp_req,
            schema_cls,
            provider_name=request.provider,
            fallback_provider=request.fallback_provider,
        )
        return StructuredAIResponse(
            schema_type=request.schema_type,
            data=parsed_obj.model_dump(),
            usage=usage.model_dump(),
        )
    except StructuredOutputValidationError as sve:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Structured output failed validation: {sve}",
        ) from sve
    except ModelRateLimitError as rle:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail=f"Rate limit exceeded: {rle}",
        ) from rle
    except ModelTimeoutError as mte:
        raise HTTPException(
            status_code=status.HTTP_504_GATEWAY_TIMEOUT,
            detail=f"Model execution timed out: {mte}",
        ) from mte
    except ModelProviderError as mpe:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"Provider error: {mpe}",
        ) from mpe
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Structured generation error: {exc}",
        ) from exc


@ai_router.post("/embed", response_model=EmbeddingResponse)
async def generate_embeddings(
    request: EmbeddingRequest,
    provider: str | None = Query(None, description="Explicit provider override"),
    current_user: UserModel = Depends(get_current_user),
) -> EmbeddingResponse:
    """Generate high-dimensional vector embeddings via the Gateway."""
    gateway = get_model_gateway()
    target_provider = provider or (request.provider.value if request.provider else None)

    try:
        return await gateway.embed(request, provider_name=target_provider)
    except ModelProviderError as mpe:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"Embedding provider error: {mpe}",
        ) from mpe
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Embedding error: {exc}",
        ) from exc


@ai_router.get("/prompts", response_model=list[PromptTemplate])
async def list_prompt_templates(
    current_user: UserModel = Depends(get_current_user),
) -> list[PromptTemplate]:
    """List all registered versioned prompt templates in NEXUS."""
    pm = get_prompt_manager()
    return pm.list_templates()


@ai_router.get("/telemetry", response_model=GatewayTelemetry)
async def get_gateway_telemetry(
    current_user: UserModel = Depends(get_current_user),
) -> GatewayTelemetry:
    """Get aggregated Gateway token, latency, cost, and error telemetry."""
    gateway = get_model_gateway()
    return gateway.get_telemetry()
