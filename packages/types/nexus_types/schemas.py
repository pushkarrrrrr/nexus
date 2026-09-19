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
    OBSERVING = "observing"
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
    started_at: datetime | None = None
    completed_at: datetime | None = None


class TaskDAG(BaseModel):
    dag_id: str
    session_id: str
    goal: str
    nodes: list[DAGNode] = Field(default_factory=list)
    status: TaskStatus = TaskStatus.PENDING
    user_id: str | None = None
    execution_metadata: dict[str, Any] = Field(default_factory=dict)
    created_at: datetime = Field(default_factory=datetime.utcnow)
    completed_at: datetime | None = None


# =====================================================================
# Identity & User Context Schemas
# =====================================================================


class ModelPreferences(BaseModel):
    default_provider: str = "openai"
    fast_model: str = "gpt-4o-mini"
    reasoning_model: str = "gpt-4o"
    temperature: float = 0.2


class PermissionPreferences(BaseModel):
    auto_grant_low_risk: bool = True
    require_hitl_high_risk: bool = True
    session_grant_ttl_minutes: int = 60


class PrivacySettings(BaseModel):
    store_audit_payloads: bool = True
    telemetry_enabled: bool = False
    allow_external_rag: bool = False


class UserPreferences(BaseModel):
    timezone: str = "UTC"
    model_preferences: ModelPreferences = Field(default_factory=ModelPreferences)
    permission_preferences: PermissionPreferences = Field(default_factory=PermissionPreferences)
    privacy_settings: PrivacySettings = Field(default_factory=PrivacySettings)


class UserProfile(BaseModel):
    id: str
    email: str
    full_name: str | None = None
    is_active: bool = True
    created_at: datetime = Field(default_factory=datetime.utcnow)
    preferences: UserPreferences | None = None


class UserRegisterRequest(BaseModel):
    email: str
    password: str
    full_name: str | None = None


class UserLoginRequest(BaseModel):
    email: str
    password: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expires_in: int = 86400
    user: UserProfile


class UpdatePreferencesRequest(BaseModel):
    timezone: str | None = None
    model_preferences: dict[str, Any] | None = None
    permission_preferences: dict[str, Any] | None = None
    privacy_settings: dict[str, Any] | None = None


# =====================================================================
# Phase 4: Core Task, Goal, Event, & Session Schemas
# =====================================================================


class GoalStatus(str, Enum):
    ACTIVE = "active"
    PAUSED = "paused"
    COMPLETED = "completed"
    ARCHIVED = "archived"


class TaskEventType(str, Enum):
    DAG_CREATED = "dag_created"
    DAG_UPDATED = "dag_updated"
    STATE_TRANSITION = "state_transition"
    NODE_STATE_TRANSITION = "node_state_transition"
    TASK_CANCELLED = "task_cancelled"
    TASK_COMPLETED = "task_completed"
    TASK_FAILED = "task_failed"


class DAGNodeCreateRequest(BaseModel):
    id: str | None = None
    name: str
    agent: str = "orchestrator"
    tool: str | None = None
    input: dict[str, Any] = Field(default_factory=dict)
    dependencies: list[str] = Field(default_factory=list)


class TaskCreateRequest(BaseModel):
    session_id: str | None = None
    goal: str
    nodes: list[DAGNodeCreateRequest] = Field(default_factory=list)
    execution_metadata: dict[str, Any] = Field(default_factory=dict)


class TaskTransitionRequest(BaseModel):
    to_state: TaskStatus
    reason: str | None = None
    execution_metadata: dict[str, Any] = Field(default_factory=dict)


class DAGNodeTransitionRequest(BaseModel):
    to_state: TaskStatus
    result: dict[str, Any] | None = None
    error: str | None = None


class TaskCancelRequest(BaseModel):
    reason: str = "User cancelled task"


class TaskEventResponse(BaseModel):
    id: str
    dag_id: str
    node_id: str | None = None
    event_type: str
    from_state: str | None = None
    to_state: str | None = None
    message: str
    payload: dict[str, Any] = Field(default_factory=dict)
    created_at: datetime


class TaskTimelineResponse(BaseModel):
    dag_id: str
    events: list[TaskEventResponse] = Field(default_factory=list)
    total_events: int = 0


class GoalMilestone(BaseModel):
    id: str
    title: str
    completed: bool = False
    completed_at: datetime | None = None


class GoalCreateRequest(BaseModel):
    title: str
    description: str | None = None
    category: str = "general"
    session_id: str | None = None
    milestones: list[GoalMilestone] = Field(default_factory=list)


class GoalUpdateRequest(BaseModel):
    title: str | None = None
    description: str | None = None
    status: GoalStatus | None = None
    category: str | None = None
    progress: float | None = None
    milestones: list[GoalMilestone] | None = None


class GoalResponse(BaseModel):
    id: str
    user_id: str
    session_id: str | None = None
    title: str
    description: str | None = None
    status: GoalStatus
    category: str
    progress: float
    milestones: list[GoalMilestone] = Field(default_factory=list)
    created_at: datetime
    updated_at: datetime


class SessionCreateRequest(BaseModel):
    title: str = "New Session"
    metadata: dict[str, Any] = Field(default_factory=dict)


class SessionResponse(BaseModel):
    session_id: str
    user_id: str
    title: str
    metadata: dict[str, Any] = Field(default_factory=dict)
    created_at: datetime
    updated_at: datetime
