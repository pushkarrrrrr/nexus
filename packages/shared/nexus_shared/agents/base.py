"""BaseAgent abstraction and common agent contracts for NEXUS."""

import time
from abc import ABC, abstractmethod
from typing import Any

from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from packages.shared.nexus_shared.logging import get_logger
from packages.types.nexus_types.schemas import AgentType, PlanStep


class AgentStepResult(BaseModel):
    """Result of an agent step execution."""

    success: bool
    result_payload: dict[str, Any] = Field(default_factory=dict)
    error_message: str | None = None
    duration_ms: float = 0.0
    tokens_used: int = 0


class BaseAgent(ABC):
    """Abstract lifecycle interface for specialized agents."""

    def __init__(
        self,
        agent_type: AgentType | str,
        name: str,
        description: str,
        allowed_tools: list[str] | None = None,
        assigned_model: str = "gpt-4o",
    ) -> None:
        self.agent_type = str(agent_type.value if hasattr(agent_type, "value") else agent_type)
        self.name = name
        self.description = description
        self.allowed_tools = allowed_tools or []
        self.assigned_model = assigned_model
        self.logger = get_logger(f"nexus.agent.{self.agent_type}")

    def validate_input(self, step: PlanStep, context: dict[str, Any]) -> bool:
        """Validate step inputs before execution."""
        return bool(step.description or step.name)

    @abstractmethod
    async def run(
        self,
        step: PlanStep,
        context: dict[str, Any],
        user_id: str,
        db: AsyncSession,
    ) -> AgentStepResult:
        """Execute a single assigned plan step."""
        ...

    async def execute(
        self,
        step: PlanStep,
        context: dict[str, Any],
        user_id: str,
        db: AsyncSession,
    ) -> AgentStepResult:
        """Execute with lifecycle tracking and error containment."""
        start_time = time.perf_counter()
        self.logger.info(
            "agent_step_started",
            agent=self.name,
            step_id=step.id,
            description=step.description,
        )

        try:
            if not self.validate_input(step, context):
                return AgentStepResult(
                    success=False,
                    error_message=f"Step validation failed for agent {self.name}",
                    duration_ms=(time.perf_counter() - start_time) * 1000.0,
                )

            result = await self.run(step, context, user_id, db)
            result.duration_ms = (time.perf_counter() - start_time) * 1000.0

            self.logger.info(
                "agent_step_completed",
                agent=self.name,
                step_id=step.id,
                success=result.success,
                duration_ms=round(result.duration_ms, 2),
            )
            return result

        except Exception as exc:  # noqa: BLE001
            duration_ms = (time.perf_counter() - start_time) * 1000.0
            self.logger.error(
                "agent_step_failed",
                agent=self.name,
                step_id=step.id,
                error=str(exc),
                duration_ms=round(duration_ms, 2),
            )
            return AgentStepResult(
                success=False,
                error_message=str(exc),
                duration_ms=duration_ms,
            )
