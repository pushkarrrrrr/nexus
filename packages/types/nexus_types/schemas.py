from datetime import datetime
from enum import Enum
from typing import Any

from pydantic import BaseModel, Field


class ActionType(str, Enum):
    READ = "READ"
    WRITE = "WRITE"
    MODIFY = "MODIFY"
    DELETE = "DELETE"
    EXECUTE = "EXECUTE"
    EXTERNAL_ACTION = "EXTERNAL_ACTION"


class RiskLevel(str, Enum):
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"
    CRITICAL = "CRITICAL"


class TaskStatus(str, Enum):
    PENDING = "pending"
    PLANNING = "planning"
    AWAITING_APPROVAL = "awaiting_approval"
    EXECUTING = "executing"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class ApprovalDecisionType(str, Enum):
    APPROVE_ONCE = "approve_once"
    APPROVE_SESSION = "approve_session"
    ALWAYS_ALLOW_READ = "always_allow_read"
    DENY = "deny"


class MemoryClass(str, Enum):
    WORKING = "working"
    CONVERSATIONAL = "conversational"
    EPISODIC = "episodic"
    SEMANTIC = "semantic"
    PROCEDURAL = "procedural"


class ToolManifest(BaseModel):
    name: str
    description: str
    action_type: ActionType
    risk_level: RiskLevel
    input_schema: dict[str, Any] = Field(default_factory=dict)
    output_schema: dict[str, Any] = Field(default_factory=dict)
    reversibility: bool = False
    audit_required: bool = True


class FileDiffPreview(BaseModel):
    file_path: str
    original_content_hash: str | None = None
    new_content_hash: str | None = None
    unified_diff: str
    lines_added: int = 0
    lines_removed: int = 0


class ApprovalRequest(BaseModel):
    approval_id: str
    session_id: str
    step_id: str
    agent_name: str
    tool_name: str
    action_type: ActionType
    risk_level: RiskLevel
    reason: str
    command_args: dict[str, Any] | None = None
    diff_preview: FileDiffPreview | None = None
    created_at: datetime = Field(default_factory=datetime.utcnow)
    expires_at: datetime | None = None


class ApprovalResponse(BaseModel):
    approval_id: str
    decision: ApprovalDecisionType
    decided_at: datetime = Field(default_factory=datetime.utcnow)
    feedback_notes: str | None = None


class AuditEvent(BaseModel):
    event_id: str
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    session_id: str
    step_id: str | None = None
    agent_name: str
    tool_name: str
    action_type: ActionType
    risk_level: RiskLevel
    inputs: dict[str, Any] = Field(default_factory=dict)
    outputs: dict[str, Any] | None = None
    error: str | None = None
    policy_decision: str  # auto_approved, approved_by_user, denied_by_user, blocked_by_policy
    approval_id: str | None = None
    snapshot_id: str | None = None
    execution_duration_ms: float = 0.0
    undo_registered: bool = False
    undone_at: datetime | None = None


class SnapshotRecord(BaseModel):
    snapshot_id: str
    action_id: str
    file_path: str
    sha256_before: str
    sha256_after: str | None = None
    snapshot_file_path: str
    created_at: datetime = Field(default_factory=datetime.utcnow)
    restored_at: datetime | None = None


class MemoryItem(BaseModel):
    id: str
    memory_class: MemoryClass
    title: str
    content: str
    source_turn_id: str | None = None
    confidence: float = 1.0
    enabled: bool = True
    tags: list[str] = Field(default_factory=list)
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)


class DAGNode(BaseModel):
    id: str
    name: str
    agent: str
    tool: str | None = None
    input: dict[str, Any] | None = None
    dependencies: list[str] = Field(default_factory=list)
    status: TaskStatus = TaskStatus.PENDING
    result: dict[str, Any] | None = None
    error: str | None = None


class TaskDAG(BaseModel):
    dag_id: str
    session_id: str
    goal: str
    nodes: list[DAGNode] = Field(default_factory=list)
    status: TaskStatus = TaskStatus.PENDING
    created_at: datetime = Field(default_factory=datetime.utcnow)
    completed_at: datetime | None = None
