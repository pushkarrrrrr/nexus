"""REST API Endpoints for Tool Registry and Controlled Tool Invocations."""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from packages.shared.nexus_shared.models import UserModel
from packages.shared.nexus_shared.tools.registry import get_tool_registry
from services.api.nexus_api.auth.dependencies import get_current_user
from services.api.nexus_api.database import get_db
from services.api.nexus_api.tools.schemas import (
    ToolExecuteRequest,
    ToolExecuteResponse,
    ToolListResponse,
    ToolManifestResponse,
)

tools_router = APIRouter(prefix="/tools", tags=["tools"])


@tools_router.get(
    "",
    response_model=ToolListResponse,
    summary="List all registered tools, schemas, required capabilities, and risk levels",
)
async def list_tools() -> ToolListResponse:
    registry = get_tool_registry()
    items: list[ToolManifestResponse] = []
    for tool in registry.list_tools():
        items.append(
            ToolManifestResponse(
                name=tool.name,
                description=tool.description,
                required_capability=tool.required_capability,
                default_risk_level=tool.default_risk_level,
                timeout_seconds=tool.timeout_seconds,
                is_reversible=tool.is_reversible,
                input_schema=tool.input_schema.model_json_schema(),
                output_schema=tool.output_schema.model_json_schema(),
            )
        )
    return ToolListResponse(items=items, total=len(items))


@tools_router.get(
    "/{name}",
    response_model=ToolManifestResponse,
    summary="Get single tool manifest and JSON schema",
)
async def get_tool(name: str) -> ToolManifestResponse:
    tool = get_tool_registry().get(name)
    if not tool:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Tool '{name}' not found in registry.",
        )
    return ToolManifestResponse(
        name=tool.name,
        description=tool.description,
        required_capability=tool.required_capability,
        default_risk_level=tool.default_risk_level,
        timeout_seconds=tool.timeout_seconds,
        is_reversible=tool.is_reversible,
        input_schema=tool.input_schema.model_json_schema(),
        output_schema=tool.output_schema.model_json_schema(),
    )


@tools_router.post(
    "/{name}/execute",
    response_model=ToolExecuteResponse,
    summary="Execute tool with PolicyEngine gating and audit logging",
)
async def execute_tool(
    name: str,
    payload: ToolExecuteRequest,
    db: AsyncSession = Depends(get_db),
    current_user: UserModel = Depends(get_current_user),
) -> ToolExecuteResponse:
    tool = get_tool_registry().get(name)
    if not tool:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Tool '{name}' not found in registry.",
        )

    result = await tool.execute(
        user_id=current_user.id,
        params=payload.parameters,
        context=payload.context,
        db=db,
    )

    output_data = (
        result.output.model_dump() if hasattr(result.output, "model_dump") else result.output
    )

    return ToolExecuteResponse(
        tool=name,
        success=result.success,
        output=output_data,
        error=result.error,
        duration_ms=result.duration_ms,
        snapshot_id=result.snapshot_id,
        approval_id=result.approval_id,
        is_awaiting_approval=result.is_awaiting_approval,
    )
