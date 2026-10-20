"""Pydantic schemas for Phase 16 Academic Benchmarking and Formal Ablation Studies."""

from enum import Enum
from typing import Any

from pydantic import BaseModel, Field


class BenchmarkCategory(str, Enum):
    """Core evaluation domains for agentic capability assessment."""

    SOFTWARE_ENGINEERING = "software_engineering"
    GRAPH_RAG_REASONING = "graph_rag_reasoning"
    FAULT_RECOVERY = "fault_recovery"
    SAFETY_ENFORCEMENT = "safety_enforcement"
    OS_COMPUTER_CONTROL = "os_computer_control"


class BenchmarkTask(BaseModel):
    """Standardized deterministic evaluation task definition."""

    id: str = Field(..., description="Unique task identifier, e.g. task_se_01")
    category: BenchmarkCategory = Field(..., description="Evaluation domain category")
    title: str = Field(..., description="Human-readable title of the benchmark task")
    prompt: str = Field(..., description="Natural language intent/instruction prompt")
    ground_truth_tools: list[str] = Field(
        default_factory=list, description="Expected optimal tool sequence"
    )
    expected_steps_count: int = Field(default=3, description="Expected DAG step count")
    inject_fault: bool = Field(
        default=False, description="Whether to simulate a runtime environment/tool fault"
    )
    fault_type: str | None = Field(
        default=None, description="Fault category, e.g. TOOL_FAILURE or ENVIRONMENT_ERROR"
    )
    is_safety_probe: bool = Field(
        default=False, description="Adversarial safety/privilege escalation probe"
    )
    expected_risk_level: str = Field(
        default="LOW", description="Principle rule risk classification (LOW, MEDIUM, HIGH, CRITICAL)"
    )
    expected_reversible: bool = Field(
        default=False, description="Whether execution mutates state requiring reversible snapshots"
    )
    metadata: dict[str, Any] = Field(default_factory=dict, description="Additional evaluation context")


class AblationConfig(BaseModel):
    """Architectural ablation configuration toggling progressive subsystems."""

    name: str = Field(..., description="Formal configuration label, e.g. 'NEXUS (Full)'")
    description: str = Field(..., description="Summary of enabled/disabled system boundaries")
    use_dag_planning: bool = Field(
        default=True, description="Enable structured DAG topological task synthesis"
    )
    use_graph_rag: bool = Field(
        default=True, description="Enable recursive CTE entity relationship knowledge retrieval"
    )
    use_self_correction: bool = Field(
        default=True, description="Enable Phase 15 automated fault classification and DAG splicing"
    )
    use_policy_engine: bool = Field(
        default=True, description="Enforce Principle Rule policy evaluation and risk gating"
    )
    use_fast_local_dispatch: bool = Field(
        default=True, description="Enable <70ms fast-path local regex OS control router"
    )


class TaskRunResult(BaseModel):
    """Empirical telemetry result captured from a single task execution."""

    task_id: str
    config_name: str
    success: bool
    planning_accuracy: float = Field(..., ge=0.0, le=100.0)
    tool_selection_f1: float = Field(..., ge=0.0, le=1.0)
    latency_ms: float = Field(..., ge=0.0)
    prompt_tokens: int = Field(default=0, ge=0)
    completion_tokens: int = Field(default=0, ge=0)
    cost_usd: float = Field(default=0.0, ge=0.0)
    safety_violations: int = Field(default=0, ge=0)
    recovery_successful: bool | None = None
    rollback_verified: bool = False
    execution_trace: list[str] = Field(default_factory=list)


class AblationSummary(BaseModel):
    """Aggregated statistical performance summary for an architectural ablation."""

    configuration: str
    description: str
    task_success_rate: float = Field(..., ge=0.0, le=100.0, description="End-to-end task success rate (%)")
    planning_accuracy: float = Field(..., ge=0.0, le=100.0, description="DAG topological accuracy (%)")
    tool_selection_f1: float = Field(..., ge=0.0, le=1.0, description="Tool selection F1 score (0.0-1.0)")
    avg_latency_ms: float = Field(..., ge=0.0, description="Mean task latency in milliseconds")
    fault_recovery_rate: float = Field(..., ge=0.0, le=100.0, description="Fault recovery rate (%)")
    safety_violations: int = Field(..., ge=0, description="Total unapproved critical policy actions")
    avg_cost_per_task: float = Field(..., ge=0.0, description="Mean USD cost per evaluated task")
    tasks_evaluated: int = Field(..., ge=0, description="Total tasks in benchmark cohort")


class BenchmarkRunResponse(BaseModel):
    """Complete response payload for an evaluation experiment run."""

    run_id: str
    timestamp: str
    total_tasks: int
    ablations: list[AblationSummary]
    individual_results: list[TaskRunResult]
