"""Pydantic schemas for NEXUS Tools REST API."""

from typing import Any

from pydantic import BaseModel, Field


class ToolManifestResponse(BaseModel):
    name: str
    description: str
    required_capability: str
    default_risk_level: str
    timeout_seconds: float
    is_reversible: bool
    input_schema: dict[str, Any]
    output_schema: dict[str, Any]


class ToolListResponse(BaseModel):
    items: list[ToolManifestResponse]
    total: int


class ToolExecuteRequest(BaseModel):
    parameters: dict[str, Any] = Field(default_factory=dict)
    context: dict[str, Any] | None = None


class ToolExecuteResponse(BaseModel):
    tool: str
    success: bool
    output: Any = None
    error: str | None = None
    duration_ms: float = 0.0
    snapshot_id: str | None = None
    approval_id: str | None = None
    is_awaiting_approval: bool = False
