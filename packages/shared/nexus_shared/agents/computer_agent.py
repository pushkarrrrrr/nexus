"""Computer Agent for controlled host automation and tool execution."""

from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from packages.shared.nexus_shared.agents.base import AgentStepResult, BaseAgent
from packages.shared.nexus_shared.logging import get_logger
from packages.shared.nexus_shared.tools.registry import get_tool_registry
from packages.types.nexus_types.schemas import AgentType, PlanStep

logger = get_logger("nexus.agent.computer")


class ComputerAgent(BaseAgent):
    """Specialized agent executing filesystem, terminal, and application tools."""

    def __init__(self, assigned_model: str = "gpt-4o") -> None:
        super().__init__(
            agent_type=AgentType.COMPUTER,
            name="Computer Agent",
            description="Executes controlled computer actions, filesystem operations, and terminal tasks using approved capability tools.",
            allowed_tools=[
                "filesystem.read",
                "filesystem.write",
                "filesystem.move",
                "filesystem.delete",
                "filesystem.list_dir",
                "terminal.execute",
                "applications.open",
                "browser.open_url",
            ],
            assigned_model=assigned_model,
        )
        self.tool_registry = get_tool_registry()

    def _resolve_tool_name(self, step: PlanStep) -> str | None:
        """Identify which tool should execute the step."""
        if hasattr(step, "tool") and step.tool:
            return str(step.tool)
        if step.required_tools and len(step.required_tools) > 0:
            return step.required_tools[0]

        # Infer tool from description/name
        text = f"{step.description or ''} {step.name or ''}".lower()
        if "read" in text and ("file" in text or "content" in text):
            return "filesystem.read"
        if ("write" in text or "create" in text or "save" in text) and "file" in text:
            return "filesystem.write"
        if "delete" in text or "remove" in text:
            return "filesystem.delete"
        if "list" in text and ("dir" in text or "folder" in text or "files" in text):
            return "filesystem.list_dir"
        if "move" in text or "rename" in text:
            return "filesystem.move"
        if "open" in text and ("app" in text or "application" in text):
            return "applications.open"
        if "url" in text or "browser" in text:
            return "browser.open_url"
        if "run" in text or "execute" in text or "command" in text:
            return "terminal.execute"

        return None

    async def run(
        self,
        step: PlanStep,
        context: dict[str, Any],
        user_id: str,
        db: AsyncSession,
    ) -> AgentStepResult:
        """Execute a plan step using the requested capability tool."""
        tool_name = self._resolve_tool_name(step)
        if not tool_name:
            return AgentStepResult(
                success=False,
                error_message=f"No matching tool found for computer step: '{step.description}'",
            )

        tool = self.tool_registry.get(tool_name)
        if not tool:
            return AgentStepResult(
                success=False,
                error_message=f"Tool '{tool_name}' is not registered in ToolRegistry.",
            )

        # Build parameters
        params = step.input if hasattr(step, "input") and step.input else {}
        task_id = context.get("task_id") if context else None

        # Controlled Tool Execution
        result = await tool.execute(
            user_id=user_id,
            params=params,
            context=context,
            db=db,
            task_id=task_id,
            step_id=step.id,
        )

        # Safeguard 3: Resumable Step Metadata for Approvals
        if result.is_awaiting_approval:
            return AgentStepResult(
                success=False,
                result_payload={
                    "is_awaiting_approval": True,
                    "approval_id": result.approval_id,
                    "target_tool": tool_name,
                    "parameters": params,
                    "error": result.error,
                },
                error_message=result.error,
            )

        if not result.success:
            return AgentStepResult(
                success=False,
                result_payload={"error": result.error, "tool": tool_name},
                error_message=result.error or f"Tool '{tool_name}' failed execution.",
            )

        # Successful tool run
        output_payload = (
            result.output.model_dump() if hasattr(result.output, "model_dump") else result.output
        )
        return AgentStepResult(
            success=True,
            result_payload={
                "tool": tool_name,
                "output": output_payload,
                "snapshot_id": result.snapshot_id,
            },
        )
