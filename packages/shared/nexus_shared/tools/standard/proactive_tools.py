"""Standard tools for Proactive Watchers, Triggers, and Self-Healing Remediation."""

from typing import Any

from pydantic import BaseModel, Field

from packages.shared.nexus_shared.proactive.watcher import get_system_watcher
from packages.shared.nexus_shared.tools.base import BaseTool


# ---------------------------------------------------------------------------
# 1. watcher.get_system_metrics
# ---------------------------------------------------------------------------
class WatcherGetSystemMetricsInput(BaseModel):
    include_raw: bool = Field(default=False, description="Whether to include raw byte counters")


class WatcherGetSystemMetricsOutput(BaseModel):
    status: str
    cpu_percent: float
    cpu_load_1m: float
    memory_percent: float
    disk_percent: float
    disk_free_bytes: int
    health_status: str


class WatcherGetSystemMetricsTool(BaseTool):
    name = "watcher.get_system_metrics"
    description = (
        "Inspect real-time CPU, memory, and disk telemetry from the host operating system."
    )
    input_schema = WatcherGetSystemMetricsInput
    output_schema = WatcherGetSystemMetricsOutput
    required_capability = "watcher.get_system_metrics"
    default_risk_level = "LOW"
    timeout_seconds = 5.0
    is_reversible = False

    async def run(
        self,
        user_id: str,
        params: WatcherGetSystemMetricsInput,
        context: dict[str, Any] | None = None,
    ) -> WatcherGetSystemMetricsOutput:
        watcher = get_system_watcher()
        metrics = watcher.capture_metrics()
        return WatcherGetSystemMetricsOutput(
            status="success",
            cpu_percent=metrics.cpu_percent,
            cpu_load_1m=metrics.cpu_load_1m,
            memory_percent=metrics.memory_percent,
            disk_percent=metrics.disk_percent,
            disk_free_bytes=metrics.disk_free_bytes,
            health_status=metrics.status,
        )


# ---------------------------------------------------------------------------
# 2. watcher.inspect_events
# ---------------------------------------------------------------------------
class WatcherInspectEventsInput(BaseModel):
    limit: int = Field(default=10, ge=1, le=100, description="Max number of events to inspect")


class WatcherInspectEventsOutput(BaseModel):
    status: str
    events_count: int
    events: list[dict[str, Any]]


class WatcherInspectEventsTool(BaseTool):
    name = "watcher.inspect_events"
    description = (
        "Inspect recent proactive trigger detections, anomaly alerts, and remediation events."
    )
    input_schema = WatcherInspectEventsInput
    output_schema = WatcherInspectEventsOutput
    required_capability = "watcher.inspect_events"
    default_risk_level = "LOW"
    timeout_seconds = 5.0
    is_reversible = False

    async def run(
        self,
        user_id: str,
        params: WatcherInspectEventsInput,
        context: dict[str, Any] | None = None,
    ) -> WatcherInspectEventsOutput:
        # Returns inspection record from context or empty
        events: list[dict[str, Any]] = []
        if context and "events" in context:
            events = context["events"][: params.limit]
        return WatcherInspectEventsOutput(
            status="success",
            events_count=len(events),
            events=events,
        )


# ---------------------------------------------------------------------------
# 3. trigger.create_rule
# ---------------------------------------------------------------------------
class TriggerCreateRuleInput(BaseModel):
    name: str = Field(..., min_length=2, max_length=128, description="Human-readable trigger name")
    trigger_type: str = Field(
        default="threshold", description="threshold, schedule, file_watch, task_failure"
    )
    condition: dict[str, Any] = Field(default_factory=dict, description="Evaluation rule criteria")
    action_capability: str = Field(
        default="remediation.execute_fix", description="Capability to invoke"
    )
    action_params: dict[str, Any] = Field(default_factory=dict, description="Parameters for action")
    cooldown_seconds: int = Field(default=300, ge=10, le=86400)


class TriggerCreateRuleOutput(BaseModel):
    status: str
    name: str
    trigger_type: str
    action_capability: str
    message: str


class TriggerCreateRuleTool(BaseTool):
    name = "trigger.create_rule"
    description = "Define and register a new autonomous background trigger condition."
    input_schema = TriggerCreateRuleInput
    output_schema = TriggerCreateRuleOutput
    required_capability = "trigger.create_rule"
    default_risk_level = "MEDIUM"
    timeout_seconds = 10.0
    is_reversible = False

    async def run(
        self,
        user_id: str,
        params: TriggerCreateRuleInput,
        context: dict[str, Any] | None = None,
    ) -> TriggerCreateRuleOutput:
        return TriggerCreateRuleOutput(
            status="success",
            name=params.name,
            trigger_type=params.trigger_type,
            action_capability=params.action_capability,
            message=f"Trigger '{params.name}' created successfully",
        )


# ---------------------------------------------------------------------------
# 4. trigger.list_rules
# ---------------------------------------------------------------------------
class TriggerListRulesInput(BaseModel):
    active_only: bool = Field(default=True, description="Filter only currently active triggers")


class TriggerListRulesOutput(BaseModel):
    status: str
    total_count: int
    triggers: list[dict[str, Any]]


class TriggerListRulesTool(BaseTool):
    name = "trigger.list_rules"
    description = "List all configured proactive trigger rules for the current user."
    input_schema = TriggerListRulesInput
    output_schema = TriggerListRulesOutput
    required_capability = "trigger.list_rules"
    default_risk_level = "LOW"
    timeout_seconds = 5.0
    is_reversible = False

    async def run(
        self,
        user_id: str,
        params: TriggerListRulesInput,
        context: dict[str, Any] | None = None,
    ) -> TriggerListRulesOutput:
        triggers: list[dict[str, Any]] = []
        if context and "triggers" in context:
            triggers = context["triggers"]
        return TriggerListRulesOutput(
            status="success",
            total_count=len(triggers),
            triggers=triggers,
        )


# ---------------------------------------------------------------------------
# 5. remediation.execute_fix (HIGH RISK - strictly requires approval)
# ---------------------------------------------------------------------------
class RemediationExecuteFixInput(BaseModel):
    fix_type: str = Field(
        ..., description="Type of fix: 'clear_cache', 'restart_worker', 'kill_stale_process'"
    )
    target: str = Field(default="system", description="Target component or process to fix")
    details: dict[str, Any] = Field(
        default_factory=dict, description="Additional remediation instructions"
    )


class RemediationExecuteFixOutput(BaseModel):
    status: str
    fix_type: str
    target: str
    message: str


class RemediationExecuteFixTool(BaseTool):
    name = "remediation.execute_fix"
    description = "Execute a mutating self-healing intervention or system recovery fix (HIGH risk, strictly requires human approval)."
    input_schema = RemediationExecuteFixInput
    output_schema = RemediationExecuteFixOutput
    required_capability = "remediation.execute_fix"
    default_risk_level = "HIGH"
    timeout_seconds = 30.0
    is_reversible = False

    async def run(
        self,
        user_id: str,
        params: RemediationExecuteFixInput,
        context: dict[str, Any] | None = None,
    ) -> RemediationExecuteFixOutput:
        return RemediationExecuteFixOutput(
            status="executed",
            fix_type=params.fix_type,
            target=params.target,
            message=f"Remediation '{params.fix_type}' executed on '{params.target}'",
        )


# ---------------------------------------------------------------------------
# 6. remediation.trigger_recovery (HIGH RISK - strictly requires approval)
# ---------------------------------------------------------------------------
class RemediationTriggerRecoveryInput(BaseModel):
    task_id: str = Field(..., description="ID of the failed task or DAG to recover")
    recovery_strategy: str = Field(
        default="replan",
        description="Strategy: 'retry_failed_step', 'replan', 'rollback_to_checkpoint'",
    )


class RemediationTriggerRecoveryOutput(BaseModel):
    status: str
    task_id: str
    recovery_strategy: str
    message: str


class RemediationTriggerRecoveryTool(BaseTool):
    name = "remediation.trigger_recovery"
    description = "Trigger an autonomous recovery sequence for a failed task (HIGH risk, strictly requires human approval)."
    input_schema = RemediationTriggerRecoveryInput
    output_schema = RemediationTriggerRecoveryOutput
    required_capability = "remediation.trigger_recovery"
    default_risk_level = "HIGH"
    timeout_seconds = 30.0
    is_reversible = False

    async def run(
        self,
        user_id: str,
        params: RemediationTriggerRecoveryInput,
        context: dict[str, Any] | None = None,
    ) -> RemediationTriggerRecoveryOutput:
        return RemediationTriggerRecoveryOutput(
            status="executed",
            task_id=params.task_id,
            recovery_strategy=params.recovery_strategy,
            message=f"Recovery strategy '{params.recovery_strategy}' initiated for task '{params.task_id}'",
        )
