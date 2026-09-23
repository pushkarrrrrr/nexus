"""Pydantic schemas and domain models for Proactive Watchers and Triggers."""

from datetime import UTC, datetime
from typing import Any, Literal

from pydantic import BaseModel, Field

TriggerType = Literal["threshold", "schedule", "task_failure", "system_event", "file_watch"]
TriggerEventStatus = Literal[
    "detected", "awaiting_approval", "approved", "executed", "rejected", "failed"
]


class SystemMetricsSnapshot(BaseModel):
    """Snapshot of host and kernel runtime metrics."""

    timestamp: datetime = Field(default_factory=lambda: datetime.now(UTC))
    cpu_percent: float = Field(
        default=0.0, description="Estimated CPU utilization percentage (0-100)"
    )
    cpu_load_1m: float = Field(default=0.0, description="1-minute load average")
    cpu_load_5m: float = Field(default=0.0, description="5-minute load average")
    cpu_load_15m: float = Field(default=0.0, description="15-minute load average")
    memory_total_bytes: int = Field(default=0)
    memory_used_bytes: int = Field(default=0)
    memory_percent: float = Field(default=0.0, description="Memory utilization percentage (0-100)")
    disk_total_bytes: int = Field(default=0)
    disk_used_bytes: int = Field(default=0)
    disk_free_bytes: int = Field(default=0)
    disk_percent: float = Field(default=0.0, description="Disk utilization percentage (0-100)")
    active_watchers: int = Field(default=1)
    status: str = Field(default="healthy")


class TriggerCondition(BaseModel):
    """Declarative specification of trigger rules and conditions."""

    metric_name: str | None = Field(
        default=None, description="e.g. cpu_percent, memory_percent, disk_percent"
    )
    operator: Literal[">", ">=", "<", "<=", "==", "!="] = Field(default=">")
    threshold_value: float = Field(default=80.0)
    target_path: str | None = Field(default=None, description="For file_watch conditions")
    schedule_interval_sec: int | None = Field(default=None, description="For recurring schedules")
    metadata: dict[str, Any] = Field(default_factory=dict)


class TriggerCreateRequest(BaseModel):
    name: str = Field(..., min_length=2, max_length=128)
    trigger_type: TriggerType = Field(default="threshold")
    condition: TriggerCondition
    action_capability: str = Field(default="remediation.execute_fix")
    action_params: dict[str, Any] = Field(default_factory=dict)
    cooldown_seconds: int = Field(default=300, ge=10, le=86400)
    is_active: bool = Field(default=True)


class TriggerResponse(BaseModel):
    id: str
    user_id: str
    name: str
    trigger_type: TriggerType
    condition: dict[str, Any]
    action_capability: str
    action_params: dict[str, Any]
    is_active: bool
    cooldown_seconds: int
    last_triggered_at: datetime | None = None
    trigger_count: int
    created_at: datetime
    updated_at: datetime


class TriggerEventResponse(BaseModel):
    id: str
    trigger_id: str
    user_id: str
    event_type: str
    observed_data: dict[str, Any]
    action_proposed: str
    approval_id: str | None = None
    status: TriggerEventStatus
    result_payload: dict[str, Any] | None = None
    error_message: str | None = None
    created_at: datetime


class TriggerEvaluationResult(BaseModel):
    triggered: bool
    trigger_id: str
    trigger_name: str
    reason: str
    observed_data: dict[str, Any] = Field(default_factory=dict)
    action_capability: str
    action_params: dict[str, Any] = Field(default_factory=dict)
    requires_approval: bool = False
    approval_id: str | None = None
    status: TriggerEventStatus = "detected"
