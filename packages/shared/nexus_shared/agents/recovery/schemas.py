"""Pydantic domain schemas for Autonomous Self-Correction and Error Recovery."""

from typing import Any, Literal

from pydantic import BaseModel, Field

ErrorCategory = Literal[
    "PARAM_INVALID",
    "TOOL_FAILURE",
    "ENVIRONMENT_ERROR",
    "POLICY_REJECTED",
    "TIMEOUT",
    "RESOURCE_NOT_FOUND",
    "UNKNOWN",
]

RecoveryStrategy = Literal[
    "RETRY_WITH_CORRECTED_PARAMS",
    "FALLBACK_TOOL",
    "PRUNE_AND_SPLICE_DAG",
    "ROLLBACK_AND_RETRY",
    "ESCALATE_HITL",
]


class ProposedRecoveryStep(BaseModel):
    """A synthesized recovery step generated during error reflection."""

    description: str = Field(..., description="Actionable description of the recovery step")
    assigned_agent: str = Field(
        default="orchestrator",
        description="Target specialized agent: orchestrator, research, document, computer, planning",
    )
    required_tools: list[str] = Field(default_factory=list, description="Tool IDs required")
    dependencies: list[str] = Field(
        default_factory=list, description="Explicit prerequisite step IDs or relative indices"
    )


class SelfCorrectionProposal(BaseModel):
    """Structured LLM reflection and remediation proposal."""

    error_category: ErrorCategory = Field(..., description="Classified failure category")
    diagnosis: str = Field(..., description="Root-cause critique and failure analysis")
    strategy: RecoveryStrategy = Field(..., description="Resolution strategy")
    requires_rollback: bool = Field(
        default=False, description="Whether previous file mutations must be reverted first"
    )
    requires_hitl: bool = Field(
        default=False, description="Whether human approval is required prior to recovery execution"
    )
    recovery_steps: list[ProposedRecoveryStep] = Field(
        default_factory=list, description="Synthesized recovery steps"
    )


class ReplanRecordResponse(BaseModel):
    """API response model for an error reflection & replan record."""

    id: str
    plan_id: str
    step_id: str
    task_id: str
    user_id: str
    iteration: int
    error_category: str
    error_message: str | None = None
    diagnosis: str
    strategy: str
    recovery_steps: list[dict[str, Any]] = Field(default_factory=list)
    snapshot_id: str | None = None
    rollback_performed: bool = False
    status: str
    created_at: str
