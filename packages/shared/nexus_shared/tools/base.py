"""Base classes and execution pipeline for NEXUS Tools."""

import time
from abc import ABC, abstractmethod
from datetime import UTC, datetime
from typing import Any

from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from packages.shared.nexus_shared.computer import ComputerControlAdapter, get_computer_adapter
from packages.shared.nexus_shared.logging import get_logger
from packages.shared.nexus_shared.models import AuditLogModel
from packages.shared.nexus_shared.policy import PolicyEngine
from packages.shared.nexus_shared.policy.utils import normalize_resource_target
from packages.shared.nexus_shared.reversal import SnapshotManager

logger = get_logger("nexus.tools.base")


class ToolResult(BaseModel):
    """Structured result of a tool invocation."""

    success: bool
    output: Any = None
    error: str | None = None
    duration_ms: float = 0.0
    snapshot_id: str | None = None
    approval_id: str | None = None
    audit_id: str | None = None
    is_awaiting_approval: bool = False


class BaseTool(ABC):
    """Abstract Base Class for all NEXUS capability tools."""

    name: str
    description: str
    input_schema: type[BaseModel]
    output_schema: type[BaseModel]
    required_capability: str
    default_risk_level: str = "LOW"
    timeout_seconds: float = 30.0
    is_reversible: bool = False

    def __init__(self, adapter: ComputerControlAdapter | None = None) -> None:
        self.adapter = adapter or get_computer_adapter()
        self.policy_engine = PolicyEngine()
        self.snapshot_manager = SnapshotManager()

    def get_target_resource(self, validated_params: BaseModel) -> str:
        """Extract the primary target resource (file path, url, command binary) for policy checking."""
        data = validated_params.model_dump()
        for key in ("path", "file_path", "source_path", "target_path"):
            if data.get(key):
                return normalize_resource_target(str(data[key]))
        if data.get("url"):
            return str(data["url"])
        if data.get("app_name"):
            return str(data["app_name"])
        if data.get("command"):
            cmd = data["command"]
            if isinstance(cmd, list) and cmd:
                return str(cmd[0])
            if isinstance(cmd, str) and cmd:
                return cmd.split()[0]
        return ""

    def get_proposed_content(self, validated_params: BaseModel) -> str | None:
        """Extract proposed file content if tool modifies file."""
        data = validated_params.model_dump()
        if "content" in data and isinstance(data["content"], str):
            return data["content"]
        return None

    @abstractmethod
    async def run(
        self,
        user_id: str,
        params: Any,
        context: dict[str, Any] | None = None,
    ) -> Any:
        """Execute the concrete tool logic via the OS ComputerControlAdapter."""
        ...

    async def execute(
        self,
        user_id: str,
        params: dict[str, Any] | BaseModel,
        context: dict[str, Any] | None = None,
        db: AsyncSession | None = None,
        task_id: str | None = None,
        step_id: str | None = None,
    ) -> ToolResult:
        """Controlled execution pipeline: Validate -> Policy -> Approval/Snapshot -> Execute -> Audit."""
        start_time = time.perf_counter()
        now = datetime.now(UTC)

        # 1. Input Schema Validation
        try:
            if isinstance(params, BaseModel):
                validated_params = params
            else:
                validated_params = self.input_schema.model_validate(params)
        except Exception as exc:  # noqa: BLE001
            duration_ms = (time.perf_counter() - start_time) * 1000.0
            logger.warning("tool_parameter_validation_failed", tool=self.name, error=str(exc))
            return ToolResult(
                success=False,
                error=f"Invalid arguments for {self.name}: {exc}",
                duration_ms=duration_ms,
            )

        target_resource = self.get_target_resource(validated_params)
        proposed_content = self.get_proposed_content(validated_params)

        # 2. Policy Interception (if database session available)
        snapshot_id: str | None = None
        if db is not None:
            decision = await self.policy_engine.evaluate_action(
                db=db,
                user_id=user_id,
                capability_name=self.required_capability,
                resource_target=target_resource,
                params=validated_params.model_dump(),
                task_id=task_id,
                step_id=step_id,
                tool_name=self.name,
            )

            if decision.verdict == "BLOCKED":
                duration_ms = (time.perf_counter() - start_time) * 1000.0
                return ToolResult(
                    success=False,
                    error=f"Action blocked by policy: {decision.reason}",
                    duration_ms=duration_ms,
                )

            if decision.verdict == "REQUIRES_APPROVAL":
                duration_ms = (time.perf_counter() - start_time) * 1000.0
                logger.info(
                    "tool_execution_paused_for_approval",
                    tool=self.name,
                    approval_id=decision.approval_id,
                )
                return ToolResult(
                    success=False,
                    is_awaiting_approval=True,
                    approval_id=decision.approval_id,
                    error=f"Action requires approval: {decision.reason}",
                    duration_ms=duration_ms,
                )

            # Pre-execution snapshot if action is reversible mutation
            if self.is_reversible and target_resource:
                snapshot = await self.snapshot_manager.create_snapshot(
                    db=db,
                    user_id=user_id,
                    capability_name=self.required_capability,
                    target_path=target_resource,
                    proposed_content=proposed_content,
                    task_id=task_id,
                    step_id=step_id,
                    auto_apply=True,
                )
                snapshot_id = snapshot.id

        # 3. Controlled OS Execution
        try:
            output = await self.run(user_id=user_id, params=validated_params, context=context)
            duration_ms = (time.perf_counter() - start_time) * 1000.0

            # 4. Append-Only Audit Logging
            if db is not None:
                audit_entry = AuditLogModel(
                    user_id=user_id,
                    session_id=context.get("session_id") if context else "tool_session",
                    step_id=step_id,
                    agent_name="tool_runner",
                    tool_name=self.name,
                    action_type=self.default_risk_level,
                    risk_level=self.default_risk_level,
                    event_type="TOOL_EXECUTED",
                    capability_name=self.required_capability,
                    status="SUCCESS",
                    policy_verdict="ALLOWED",
                    details={
                        "tool": self.name,
                        "parameters": validated_params.model_dump(),
                        "target_resource": target_resource,
                        "snapshot_id": snapshot_id,
                    },
                    duration_ms=duration_ms,
                    created_at=now,
                    timestamp=now,
                )
                db.add(audit_entry)
                await db.commit()

            return ToolResult(
                success=True,
                output=output,
                duration_ms=duration_ms,
                snapshot_id=snapshot_id,
            )

        except Exception as exc:  # noqa: BLE001
            duration_ms = (time.perf_counter() - start_time) * 1000.0
            logger.error("tool_execution_failed", tool=self.name, error=str(exc))
            return ToolResult(
                success=False,
                error=str(exc),
                duration_ms=duration_ms,
                snapshot_id=snapshot_id,
            )
