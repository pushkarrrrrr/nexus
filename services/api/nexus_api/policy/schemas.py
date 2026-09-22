"""Pydantic schemas for Policy Engine REST endpoints."""

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field


class CapabilityResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    name: str
    category: str
    default_risk_level: str
    description: str
    is_active: bool


class CapabilityListResponse(BaseModel):
    items: list[CapabilityResponse]
    total: int


class UserPermissionResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    user_id: str
    capability_name: str
    scope: str
    resource_pattern: str
    expires_at: datetime | None
    created_at: datetime


class UserPermissionListResponse(BaseModel):
    items: list[UserPermissionResponse]
    total: int


class ApprovalRequestResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    user_id: str
    task_id: str | None
    step_id: str | None
    capability_name: str
    action_category: str
    risk_level: str
    reason: str
    affected_resources: list[str]
    parameters: dict[str, Any]
    status: str
    approved_scope: str | None
    expires_at: datetime | None
    created_at: datetime
    resolved_at: datetime | None


class ApprovalRequestListResponse(BaseModel):
    items: list[ApprovalRequestResponse]
    total: int


class ApprovalResolutionRequest(BaseModel):
    decision: Literal["APPROVED", "DENIED"]
    chosen_scope: Literal["ONE_TIME", "SESSION", "STANDING"] | None = None
    session_ttl_minutes: int = Field(default=60, ge=1, le=1440)


class ApprovalResolutionResponse(BaseModel):
    approval: ApprovalRequestResponse
    message: str


class PolicyEvaluateRequest(BaseModel):
    capability_name: str
    resource_target: str
    params: dict[str, Any] = Field(default_factory=dict)
    session_id: str | None = None
    task_id: str | None = None
    step_id: str | None = None


class PolicyEvaluateResponse(BaseModel):
    verdict: str
    capability_name: str
    risk_level: str
    reason: str
    approval_id: str | None = None
    matching_permission_id: str | None = None
    affected_resource: str
    timestamp: datetime


class AuditLogResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    user_id: str | None
    session_id: str | None
    step_id: str | None
    agent_name: str
    tool_name: str
    action_type: str
    risk_level: str
    event_type: str
    capability_name: str | None
    status: str
    policy_verdict: str
    details: dict[str, Any]
    ip_address: str | None
    created_at: datetime
    timestamp: datetime | None


class AuditLogListResponse(BaseModel):
    items: list[AuditLogResponse]
    total: int
