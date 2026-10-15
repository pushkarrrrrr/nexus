"""LLM-powered Error Reflection and Self-Correction Synthesizer."""

from typing import Any

from packages.shared.nexus_shared.agents.recovery.schemas import (
    ErrorCategory,
    ProposedRecoveryStep,
    RecoveryStrategy,
    SelfCorrectionProposal,
)
from packages.shared.nexus_shared.ai.gateway import get_model_gateway
from packages.shared.nexus_shared.logging import get_logger
from packages.shared.nexus_shared.models import PlanStepModel
from packages.types.nexus_types.schemas import CompletionRequest

logger = get_logger("nexus.recovery.reflector")


class SelfCorrectionReflector:
    """Reflects on execution errors and synthesizes structured self-correction proposals."""

    def __init__(self, assigned_model: str = "gpt-4o") -> None:
        self.assigned_model = assigned_model
        self.gateway = get_model_gateway()

    async def reflect(
        self,
        goal: str,
        failed_step: PlanStepModel,
        error_context: str,
        error_category: ErrorCategory,
        prior_results: dict[str, Any] | None = None,
        has_snapshot: bool = False,
    ) -> SelfCorrectionProposal:
        """Analyze failure and synthesize a SelfCorrectionProposal."""
        prompt = (
            f"You are the NEXUS Operating System Self-Correction and Error Recovery Engine.\n"
            f"An agentic step failed during plan execution. Perform a critical root-cause diagnosis "
            f"and synthesize a concrete recovery proposal.\n\n"
            f"Overall Goal: {goal}\n"
            f"Failed Step Index: {failed_step.index}\n"
            f"Failed Step Description: {failed_step.description}\n"
            f"Assigned Agent: {failed_step.assigned_agent}\n"
            f"Required Tools: {failed_step.required_tools}\n"
            f"Classified Error Category: {error_category}\n"
            f"Error Message / Trace: {error_context}\n"
            f"Pre-mutation Snapshot Available: {has_snapshot}\n"
            f"Prior Completed Step Results: {prior_results or {}}\n\n"
            f"Instructions:\n"
            f"1. Diagnose the exact technical root cause of failure.\n"
            f"2. Select the optimal recovery strategy: RETRY_WITH_CORRECTED_PARAMS, FALLBACK_TOOL, "
            f"PRUNE_AND_SPLICE_DAG, ROLLBACK_AND_RETRY, or ESCALATE_HITL.\n"
            f"3. Set requires_rollback=True if the workspace has dirty state from this step.\n"
            f"4. Set requires_hitl=True if user permission or guidance is mandatory.\n"
            f"5. Provide 1 to 2 concrete recovery steps with explicit alternative tools."
        )

        try:
            req = CompletionRequest(
                prompt=prompt,
                model=self.assigned_model,
                temperature=0.1,
            )
            proposal, _ = await self.gateway.complete_structured(req, SelfCorrectionProposal)
            logger.info(
                "self_correction_reflection_generated",
                step_id=failed_step.id,
                strategy=proposal.strategy,
                category=proposal.error_category,
            )
            return proposal
        except Exception as exc:  # noqa: BLE001
            logger.warning(
                "Structured reflection completion failed, falling back to deterministic heuristic: %s",
                exc,
            )
            return self._heuristic_fallback(
                goal=goal,
                failed_step=failed_step,
                error_context=error_context,
                error_category=error_category,
                has_snapshot=has_snapshot,
            )

    def _heuristic_fallback(
        self,
        goal: str,
        failed_step: PlanStepModel,
        error_context: str,
        error_category: ErrorCategory,
        has_snapshot: bool,
    ) -> SelfCorrectionProposal:
        """Deterministic heuristic fallback when LLM gateway is unavailable."""
        strategy: RecoveryStrategy
        requires_rollback = False
        requires_hitl = False
        recovery_steps: list[ProposedRecoveryStep] = []

        if error_category == "POLICY_REJECTED":
            strategy = "ESCALATE_HITL"
            requires_hitl = True
            diagnosis = f"Policy Engine blocked action for step {failed_step.index}. Human approval required."
            recovery_steps.append(
                ProposedRecoveryStep(
                    description=f"Request human approval and re-execute: {failed_step.description}",
                    assigned_agent="orchestrator",
                    required_tools=list(failed_step.required_tools or []),
                    dependencies=list(failed_step.dependencies or []),
                )
            )
        elif error_category == "PARAM_INVALID":
            strategy = "RETRY_WITH_CORRECTED_PARAMS"
            diagnosis = f"Parameter validation failure in step {failed_step.index}: {error_context[:100]}. Sanitizing inputs."
            recovery_steps.append(
                ProposedRecoveryStep(
                    description=f"Retry with sanitized parameters: {failed_step.description}",
                    assigned_agent=failed_step.assigned_agent,
                    required_tools=list(failed_step.required_tools or []),
                    dependencies=list(failed_step.dependencies or []),
                )
            )
        elif error_category == "TIMEOUT":
            strategy = "RETRY_WITH_CORRECTED_PARAMS"
            diagnosis = f"Step {failed_step.index} timed out. Retrying with extended deadline."
            recovery_steps.append(
                ProposedRecoveryStep(
                    description=f"Retry with extended timeout: {failed_step.description}",
                    assigned_agent=failed_step.assigned_agent,
                    required_tools=list(failed_step.required_tools or []),
                    dependencies=list(failed_step.dependencies or []),
                )
            )
        elif error_category == "RESOURCE_NOT_FOUND":
            strategy = "PRUNE_AND_SPLICE_DAG"
            diagnosis = f"Target resource missing in step {failed_step.index}. Prepending discovery search."
            discovery_step = ProposedRecoveryStep(
                description=f"Discover or locate missing resources for: {failed_step.description}",
                assigned_agent="research" if failed_step.assigned_agent != "computer" else "computer",
                required_tools=["filesystem.list_dir"] if "filesystem" in str(failed_step.required_tools) else ["rag_retriever"],
                dependencies=list(failed_step.dependencies or []),
            )
            retry_step = ProposedRecoveryStep(
                description=f"Execute original action with discovered target: {failed_step.description}",
                assigned_agent=failed_step.assigned_agent,
                required_tools=list(failed_step.required_tools or []),
                dependencies=[discovery_step.description],
            )
            recovery_steps.extend([discovery_step, retry_step])
        else:
            # TOOL_FAILURE or ENVIRONMENT_ERROR
            if has_snapshot:
                strategy = "ROLLBACK_AND_RETRY"
                requires_rollback = True
                diagnosis = f"Step {failed_step.index} failed with dirty state ({error_context[:80]}). Reverting filesystem snapshot before retry."
            else:
                strategy = "FALLBACK_TOOL"
                diagnosis = f"Step {failed_step.index} failed ({error_context[:80]}). Falling back to secondary agent."

            recovery_steps.append(
                ProposedRecoveryStep(
                    description=f"Fallback execution after failure: {failed_step.description}",
                    assigned_agent="orchestrator" if failed_step.assigned_agent == "research" else "research",
                    required_tools=["fallback_resolver"],
                    dependencies=list(failed_step.dependencies or []),
                )
            )

        return SelfCorrectionProposal(
            error_category=error_category,
            diagnosis=diagnosis,
            strategy=strategy,
            requires_rollback=requires_rollback,
            requires_hitl=requires_hitl,
            recovery_steps=recovery_steps,
        )
