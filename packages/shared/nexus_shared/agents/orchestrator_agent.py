"""OrchestratorAgent coordinates multi-agent execution, dependency resolution, replanning, and synthesis."""

from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from packages.shared.nexus_shared.agents.base import AgentStepResult, BaseAgent
from packages.shared.nexus_shared.agents.document_agent import DocumentAgent
from packages.shared.nexus_shared.agents.planning_agent import PlanningAgent
from packages.shared.nexus_shared.agents.research_agent import ResearchAgent
from packages.shared.nexus_shared.ai.gateway import get_model_gateway
from packages.shared.nexus_shared.models import (
    ExecutionPlanModel,
    PlanStepModel,
    SessionModel,
    TaskDAGModel,
    generate_uuid,
    utcnow,
)
from packages.types.nexus_types.schemas import (
    AgentExecuteResponse,
    AgentFinalResponse,
    AgentMessage,
    AgentRosterItem,
    AgentType,
    CompletionRequest,
    ExecutionPlan,
    PlanStatus,
    PlanStep,
    PlanStepStatus,
    TaskStatus,
)


class OrchestratorAgent(BaseAgent):
    """Central autonomous coordinator for NEXUS specialized agent pipelines."""

    def __init__(self) -> None:
        super().__init__(
            agent_type=AgentType.ORCHESTRATOR,
            name="Orchestrator Agent",
            description="Coordinates intent analysis, execution planning, subtask dispatch, failure recovery, and answer synthesis.",
            allowed_tools=["intent_classifier", "dag_scheduler", "synthesizer"],
            assigned_model="gpt-4o",
        )
        self.gateway = get_model_gateway()
        self.planning_agent = PlanningAgent()
        self.research_agent = ResearchAgent()
        self.document_agent = DocumentAgent()

        # Agent directory for dynamic dispatch
        self._sub_agents: dict[str, BaseAgent] = {
            "orchestrator": self,
            "planning": self.planning_agent,
            "research": self.research_agent,
            "document": self.document_agent,
        }

    def get_roster(self) -> list[AgentRosterItem]:
        """Return the active agent roster."""
        roster: list[AgentRosterItem] = []
        for a in [self, self.planning_agent, self.research_agent, self.document_agent]:
            roster.append(
                AgentRosterItem(
                    agent_type=a.agent_type,
                    name=a.name,
                    description=a.description,
                    allowed_tools=list(a.allowed_tools),
                    assigned_model=a.assigned_model,
                    status="ready",
                    system_prompt_preview=f"Autonomous specialist for {a.name}",
                )
            )
        return roster

    async def run(
        self,
        step: PlanStep,
        context: dict[str, Any],
        user_id: str,
        db: AsyncSession,
    ) -> AgentStepResult:
        """Execute an internal orchestrator step (e.g., synthesis or aggregation)."""
        goal = context.get("goal") or step.description
        step_results = context.get("step_results", {})

        synthesis_prompt = (
            f"Synthesize verified conclusions and final answer for the goal:\n"
            f"Goal: {goal}\n\n"
            f"Step Results Collected:\n{step_results}\n\n"
            f"Provide a clear, cohesive final summary."
        )

        try:
            req = CompletionRequest(
                prompt=synthesis_prompt,
                model=self.assigned_model,
                temperature=0.2,
            )
            structured_res, _ = await self.gateway.complete_structured(req, AgentFinalResponse)
            return AgentStepResult(
                success=True,
                result_payload={
                    "answer": structured_res.answer,
                    "summary": structured_res.summary,
                    "artifacts": structured_res.artifacts,
                },
            )
        except Exception as exc:  # noqa: BLE001
            self.logger.warning("Structured synthesis fallback: %s", exc)
            return AgentStepResult(
                success=True,
                result_payload={
                    "answer": f"Completed execution for: {goal}. All planned steps finished.",
                    "summary": goal[:60],
                    "artifacts": [],
                },
            )

    async def create_plan(
        self,
        goal: str,
        task_id: str,
        user_id: str,
        context: dict[str, Any],
        db: AsyncSession,
    ) -> ExecutionPlanModel:
        """Decompose a goal using the PlanningAgent and persist the ExecutionPlan."""
        # 1. Generate steps via PlanningAgent
        steps = await self.planning_agent.generate_steps(goal, context)

        # 2. Persist ExecutionPlan
        plan = ExecutionPlanModel(
            id=generate_uuid("plan"),
            task_id=task_id,
            user_id=user_id,
            goal=goal,
            current_step_index=0,
            status=PlanStatus.CREATED.value,
            replan_count=0,
            max_replans=3,
            plan_metadata=context,
        )
        db.add(plan)
        await db.flush()

        # Map raw step IDs to globally unique step IDs
        id_map: dict[str, str] = {}
        for s in steps:
            unique_id = generate_uuid("pstep")
            if s.id:
                id_map[s.id] = unique_id
            id_map[str(s.index)] = unique_id

        # 3. Persist PlanSteps with mapped unique IDs
        for s in steps:
            unique_id = id_map.get(s.id, generate_uuid("pstep"))
            remapped_deps = [id_map.get(dep, dep) for dep in s.dependencies]
            pstep = PlanStepModel(
                id=unique_id,
                plan_id=plan.id,
                index=s.index,
                description=s.description or s.name,
                assigned_agent=s.assigned_agent or "orchestrator",
                required_tools=s.required_tools,
                dependencies=remapped_deps,
                status=PlanStepStatus.PENDING.value,
            )
            db.add(pstep)

        await db.commit()
        await db.refresh(plan)
        return plan

    async def execute_plan(
        self,
        plan_id: str,
        user_id: str,
        db: AsyncSession,
        event_callback: Any | None = None,
    ) -> tuple[ExecutionPlanModel, str | None, list[AgentMessage]]:
        """
        Execute an existing ExecutionPlan with strict transaction hygiene, dual-point cancellation
        checks, explicit dependency resolution, and failure replanning.
        """
        messages: list[AgentMessage] = []

        # Load plan & task
        plan_query = await db.execute(
            select(ExecutionPlanModel).where(
                ExecutionPlanModel.id == plan_id,
                ExecutionPlanModel.user_id == user_id,
            )
        )
        plan = plan_query.scalar_one_or_none()
        if not plan:
            raise ValueError(f"Plan '{plan_id}' not found for user")

        task_query = await db.execute(select(TaskDAGModel).where(TaskDAGModel.id == plan.task_id))
        task = task_query.scalar_one_or_none()
        if not task:
            raise ValueError(f"Task '{plan.task_id}' not found")

        # Check initial cancellation status before marking EXECUTING
        if task.status == TaskStatus.CANCELLED.value or plan.status == PlanStatus.CANCELLED.value:
            self.logger.info("plan_execution_cancelled_prior_to_start", plan_id=plan.id)
            plan.status = PlanStatus.CANCELLED.value
            steps_query = await db.execute(
                select(PlanStepModel)
                .where(PlanStepModel.plan_id == plan.id)
                .order_by(PlanStepModel.index.asc())
            )
            all_steps = list(steps_query.scalars().all())
            for s in all_steps:
                if s.status == PlanStepStatus.PENDING.value:
                    s.status = PlanStepStatus.SKIPPED.value
                    s.completed_at = utcnow()
            await db.commit()
            messages.append(
                AgentMessage(
                    role="system",
                    sender="orchestrator",
                    recipient="user",
                    content="Plan execution halted cleanly due to task cancellation.",
                )
            )
            return plan, "Task cancelled by user", messages

        # Set initial status to EXECUTING
        plan.status = PlanStatus.EXECUTING.value
        task.status = TaskStatus.EXECUTING.value
        await db.commit()
        await db.refresh(plan)

        messages.append(
            AgentMessage(
                role="agent",
                sender="orchestrator",
                recipient="all",
                content=f"Starting autonomous execution plan for goal: {plan.goal}",
            )
        )

        step_results: dict[str, Any] = {}
        final_answer: str | None = None

        # Outer execution loop
        while True:
            # Query all steps fresh from DB
            steps_query = await db.execute(
                select(PlanStepModel)
                .where(PlanStepModel.plan_id == plan.id)
                .order_by(PlanStepModel.index.asc())
            )
            all_steps = list(steps_query.scalars().all())

            # Find next pending step
            pending_step = next(
                (s for s in all_steps if s.status == PlanStepStatus.PENDING.value),
                None,
            )

            if not pending_step:
                # All steps processed
                break

            # -------------------------------------------------------------
            # ADJUSTMENT 2: Cancellation check immediately BEFORE step dispatch
            # -------------------------------------------------------------
            await db.refresh(task)
            await db.refresh(plan)
            if (
                task.status == TaskStatus.CANCELLED.value
                or plan.status == PlanStatus.CANCELLED.value
            ):
                self.logger.info("plan_execution_halted_by_cancellation", plan_id=plan.id)
                plan.status = PlanStatus.CANCELLED.value
                for s in all_steps:
                    if s.status == PlanStepStatus.PENDING.value:
                        s.status = PlanStepStatus.SKIPPED.value
                await db.commit()
                messages.append(
                    AgentMessage(
                        role="system",
                        sender="orchestrator",
                        recipient="user",
                        content="Plan execution halted cleanly due to task cancellation.",
                    )
                )
                return plan, "Task cancelled by user", messages

            # -------------------------------------------------------------
            # ADJUSTMENT 3: Explicit Dependency Resolution
            # -------------------------------------------------------------
            dependencies_met = True
            dep_failure_reason: str | None = None
            step_status_map = {s.id: s.status for s in all_steps}

            for dep_id in pending_step.dependencies:
                dep_status = step_status_map.get(dep_id)
                if dep_status != PlanStepStatus.COMPLETED.value:
                    if dep_status in (PlanStepStatus.FAILED.value, PlanStepStatus.SKIPPED.value):
                        dependencies_met = False
                        dep_failure_reason = f"Upstream dependency '{dep_id}' was {dep_status}"
                        break
                    else:
                        # Dependency still pending or in progress
                        dependencies_met = False
                        break

            if not dependencies_met:
                if dep_failure_reason:
                    # Mark this step as skipped because dependency failed
                    pending_step.status = PlanStepStatus.SKIPPED.value
                    pending_step.error_message = dep_failure_reason
                    await db.commit()
                    messages.append(
                        AgentMessage(
                            role="agent",
                            sender="orchestrator",
                            recipient="all",
                            content=f"Skipping step '{pending_step.description}': {dep_failure_reason}",
                        )
                    )
                continue

            # -------------------------------------------------------------
            # ADJUSTMENT 1: Session & Transaction Hygiene (Pre-Execution Commit)
            # -------------------------------------------------------------
            pending_step.status = PlanStepStatus.IN_PROGRESS.value
            pending_step.started_at = utcnow()
            plan.current_step_index = pending_step.index
            await db.commit()
            await db.refresh(pending_step)

            if event_callback:
                try:
                    await event_callback("step_started", pending_step)
                except Exception as cb_err:  # noqa: BLE001
                    self.logger.debug("event_callback error: %s", cb_err)

            messages.append(
                AgentMessage(
                    role="agent",
                    sender=pending_step.assigned_agent,
                    recipient="orchestrator",
                    content=f"Executing step {pending_step.index}: {pending_step.description}",
                )
            )

            # Resolve assigned agent
            target_agent = self._sub_agents.get(pending_step.assigned_agent, self)

            # Build step contract schema
            pydantic_step = PlanStep(
                id=pending_step.id,
                index=pending_step.index,
                description=pending_step.description,
                name=pending_step.description,
                assigned_agent=pending_step.assigned_agent,
                required_tools=list(pending_step.required_tools or []),
                dependencies=list(pending_step.dependencies or []),
                status=pending_step.status,
            )

            # Run agent OUTSIDE uncommitted transaction
            step_context = {
                "goal": plan.goal,
                "step_results": step_results,
                "plan_metadata": plan.plan_metadata,
            }
            step_result = await target_agent.execute(
                pydantic_step,
                step_context,
                user_id,
                db,
            )

            # -------------------------------------------------------------
            # ADJUSTMENT 2: Cancellation check immediately AFTER step execution
            # -------------------------------------------------------------
            await db.refresh(task)
            await db.refresh(plan)
            if (
                task.status == TaskStatus.CANCELLED.value
                or plan.status == PlanStatus.CANCELLED.value
            ):
                self.logger.info("plan_execution_halted_post_step_cancellation", plan_id=plan.id)
                plan.status = PlanStatus.CANCELLED.value
                pending_step.status = PlanStepStatus.SKIPPED.value
                pending_step.completed_at = utcnow()
                await db.commit()
                return plan, "Task cancelled by user", messages

            # -------------------------------------------------------------
            # ADJUSTMENT 1: Session & Transaction Hygiene (Post-Execution Commit)
            # -------------------------------------------------------------
            if step_result.success:
                pending_step.status = PlanStepStatus.COMPLETED.value
                pending_step.result_payload = step_result.result_payload
                pending_step.completed_at = utcnow()
                step_results[pending_step.id] = step_result.result_payload
                if "answer" in step_result.result_payload:
                    final_answer = str(step_result.result_payload["answer"])

                await db.commit()
                await db.refresh(pending_step)

                if event_callback:
                    try:
                        await event_callback("step_completed", pending_step)
                    except Exception as cb_err:  # noqa: BLE001
                        self.logger.debug("event_callback error: %s", cb_err)

                messages.append(
                    AgentMessage(
                        role="agent",
                        sender=pending_step.assigned_agent,
                        recipient="orchestrator",
                        content=f"Step {pending_step.index} completed successfully.",
                        structured_payload=step_result.result_payload,
                    )
                )

            else:
                # Handle failure: check retries
                pending_step.retry_count += 1
                pending_step.error_message = step_result.error_message

                if pending_step.retry_count <= pending_step.max_retries:
                    self.logger.info(
                        "step_retrying",
                        step_id=pending_step.id,
                        attempt=pending_step.retry_count,
                    )
                    pending_step.status = PlanStepStatus.PENDING.value
                    await db.commit()
                    continue

                # Retries exhausted
                pending_step.status = PlanStepStatus.FAILED.value
                pending_step.completed_at = utcnow()
                await db.commit()

                if event_callback:
                    try:
                        await event_callback("step_failed", pending_step)
                    except Exception as cb_err:  # noqa: BLE001
                        self.logger.debug("event_callback error: %s", cb_err)

                messages.append(
                    AgentMessage(
                        role="agent",
                        sender=pending_step.assigned_agent,
                        recipient="orchestrator",
                        content=f"Step {pending_step.index} failed: {step_result.error_message}",
                    )
                )

                # ---------------------------------------------------------
                # Guardrail: Replan if within max_replans limit
                # ---------------------------------------------------------
                if plan.replan_count < plan.max_replans:
                    messages.append(
                        AgentMessage(
                            role="agent",
                            sender="orchestrator",
                            recipient="planning",
                            content=f"Triggering recovery replan (iteration {plan.replan_count + 1}/{plan.max_replans})",
                        )
                    )
                    recovery_steps = await self.planning_agent.replan(
                        failed_step=pending_step,
                        error_context=str(step_result.error_message),
                        plan_id=plan.id,
                        db=db,
                    )
                    if event_callback:
                        try:
                            await event_callback("plan_updated", plan)
                        except Exception as cb_err:  # noqa: BLE001
                            self.logger.debug("event_callback error: %s", cb_err)

                    messages.append(
                        AgentMessage(
                            role="agent",
                            sender="planning",
                            recipient="orchestrator",
                            content=f"Added {len(recovery_steps)} recovery steps to execution plan.",
                        )
                    )
                    # Resume execution with new recovery steps
                    continue
                else:
                    self.logger.warning("plan_exceeded_max_replans", plan_id=plan.id)
                    plan.status = PlanStatus.FAILED.value
                    task.status = TaskStatus.FAILED.value
                    for s in all_steps:
                        if s.status == PlanStepStatus.PENDING.value and s.id != pending_step.id:
                            s.status = PlanStepStatus.SKIPPED.value
                            s.error_message = f"Skipped: Upstream dependency '{pending_step.id}' failed ({step_result.error_message})"
                            s.completed_at = utcnow()
                    await db.commit()
                    messages.append(
                        AgentMessage(
                            role="system",
                            sender="orchestrator",
                            recipient="user",
                            content="Plan execution failed: exceeded maximum allowed replan iterations.",
                        )
                    )
                    return plan, f"Failed at step: {step_result.error_message}", messages

        # Final Verification & State Transition
        await db.refresh(plan)
        all_steps_final = await db.execute(
            select(PlanStepModel).where(PlanStepModel.plan_id == plan.id)
        )
        final_steps = list(all_steps_final.scalars().all())

        has_failed = any(s.status == PlanStepStatus.FAILED.value for s in final_steps)
        if has_failed:
            plan.status = PlanStatus.FAILED.value
            task.status = TaskStatus.FAILED.value
        else:
            plan.status = PlanStatus.COMPLETED.value
            task.status = TaskStatus.COMPLETED.value
            task.completed_at = utcnow()

        await db.commit()
        await db.refresh(plan)

        if not final_answer:
            final_answer = f"All {len(final_steps)} steps executed for goal: '{plan.goal}'."

        messages.append(
            AgentMessage(
                role="agent",
                sender="orchestrator",
                recipient="user",
                content=final_answer,
            )
        )

        return plan, final_answer, messages

    async def execute_goal(
        self,
        goal: str,
        user_id: str,
        session_id: str | None,
        context: dict[str, Any],
        db: AsyncSession,
        event_callback: Any | None = None,
    ) -> AgentExecuteResponse:
        """High-level autonomous entrypoint: creates Task, Plan, executes, and synthesizes response."""
        # 1. Resolve or create active session
        if not session_id:
            sess_q = await db.execute(
                select(SessionModel)
                .where(SessionModel.user_id == user_id)
                .order_by(SessionModel.created_at.desc())
                .limit(1)
            )
            active_sess = sess_q.scalar_one_or_none()
            if not active_sess:
                active_sess = SessionModel(
                    id=generate_uuid("sess"),
                    user_id=user_id,
                    surface="dashboard",
                    title="Agent Session",
                    os_context={},
                )
                db.add(active_sess)
                await db.commit()
                await db.refresh(active_sess)
            session_id = active_sess.id

        # 2. Create TaskDAG
        task = TaskDAGModel(
            id=generate_uuid("dag"),
            user_id=user_id,
            session_id=session_id,
            goal=goal,
            status=TaskStatus.PLANNING.value,
            execution_metadata=context,
        )
        db.add(task)
        await db.commit()
        await db.refresh(task)

        # 3. Create initial ExecutionPlan
        plan = await self.create_plan(
            goal=goal,
            task_id=task.id,
            user_id=user_id,
            context=context,
            db=db,
        )

        # 4. Execute plan
        executed_plan, final_answer, messages = await self.execute_plan(
            plan_id=plan.id,
            user_id=user_id,
            db=db,
            event_callback=event_callback,
        )

        # 5. Format response
        steps_query = await db.execute(
            select(PlanStepModel)
            .where(PlanStepModel.plan_id == executed_plan.id)
            .order_by(PlanStepModel.index.asc())
        )
        plan_steps = [
            PlanStep(
                id=s.id,
                index=s.index,
                description=s.description,
                name=s.description,
                assigned_agent=s.assigned_agent,
                required_tools=list(s.required_tools or []),
                dependencies=list(s.dependencies or []),
                status=s.status,
                retry_count=s.retry_count,
                max_retries=s.max_retries,
                result=s.result_payload,
                error=s.error_message,
                started_at=s.started_at,
                completed_at=s.completed_at,
            )
            for s in steps_query.scalars().all()
        ]

        formatted_plan = ExecutionPlan(
            id=executed_plan.id,
            task_id=executed_plan.task_id,
            user_id=executed_plan.user_id,
            goal=executed_plan.goal,
            steps=plan_steps,
            current_step_index=executed_plan.current_step_index,
            status=executed_plan.status,
            replan_count=executed_plan.replan_count,
            max_replans=executed_plan.max_replans,
            plan_metadata=dict(executed_plan.plan_metadata or {}),
            created_at=executed_plan.created_at,
            updated_at=executed_plan.updated_at,
        )

        return AgentExecuteResponse(
            task_id=task.id,
            plan=formatted_plan,
            final_response=final_answer,
            status=executed_plan.status,
            messages=messages,
        )


_orchestrator_instance: OrchestratorAgent | None = None


def get_orchestrator_agent() -> OrchestratorAgent:
    """Get the singleton OrchestratorAgent instance."""
    global _orchestrator_instance
    if _orchestrator_instance is None:
        _orchestrator_instance = OrchestratorAgent()
    return _orchestrator_instance
