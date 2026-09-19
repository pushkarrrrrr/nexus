"""NEXUS Prompt & Version Management Engine.

Maintains versioned system and user prompt templates with strict
variable validation and parameter substitution.
"""

from typing import Any

from packages.shared.nexus_shared.errors import PromptTemplateError
from packages.types.nexus_types.schemas import PromptTemplate


class PromptManager:
    """Manages versioned prompt templates for NEXUS autonomous agents."""

    def __init__(self) -> None:
        self._templates: dict[str, dict[str, PromptTemplate]] = {}
        self._load_seed_templates()

    def _load_seed_templates(self) -> None:
        """Seed default prompt templates for core orchestrator roles."""
        seed_templates = [
            PromptTemplate(
                template_id="intent_analyzer",
                version="v1.0.0",
                description="Classifies user goals into structured intentions, domains, and risk levels.",
                system_prompt=(
                    "You are the NEXUS Intent Analysis Subsystem. "
                    "Analyze the user's request and classify its intent, domain, entities, and risk level. "
                    "You must output valid JSON conforming strictly to the requested AgentIntent schema."
                ),
                user_template="User Request: {user_request}\nOperating Context: {operating_context}",
                input_variables=["user_request", "operating_context"],
            ),
            PromptTemplate(
                template_id="dag_planner",
                version="v1.0.0",
                description="Synthesizes multi-step topological execution plans (DAGs) for complex tasks.",
                system_prompt=(
                    "You are the NEXUS Topological Task DAG Planner. "
                    "Decompose the user's objective into a deterministic Directed Acyclic Graph. "
                    "Assign specialized agents, designate tools, and declare explicit step dependencies. "
                    "Output valid JSON conforming strictly to the requested AgentPlan schema."
                ),
                user_template=(
                    "Goal: {goal}\n"
                    "Available Agents: {available_agents}\n"
                    "Available Tools: {available_tools}\n"
                    "Constraints: {constraints}"
                ),
                input_variables=["goal", "available_agents", "available_tools", "constraints"],
            ),
            PromptTemplate(
                template_id="tool_selector",
                version="v1.0.0",
                description="Selects the optimal tool and formats exact input parameters for an agent action.",
                system_prompt=(
                    "You are the NEXUS Tool Selection & Parameter Engine. "
                    "Given the active step and available tool manifest, select the appropriate tool "
                    "and formulate exact input arguments. Output valid JSON matching AgentToolCall."
                ),
                user_template=(
                    "Step Description: {step_name}\n"
                    "Step Input: {step_input}\n"
                    "Tool Manifests: {manifests}"
                ),
                input_variables=["step_name", "step_input", "manifests"],
            ),
            PromptTemplate(
                template_id="task_summarizer",
                version="v1.0.0",
                description="Generates executive summaries and artifact catalogs upon task completion.",
                system_prompt=(
                    "You are the NEXUS Executive Response Formulator. "
                    "Synthesize the outputs and observations of all completed subtasks into a clear, "
                    "technical response with next steps. Output valid JSON matching AgentFinalResponse."
                ),
                user_template=(
                    "Original Goal: {goal}\n"
                    "Execution Observations: {observations}\n"
                    "Artifacts Produced: {artifacts}"
                ),
                input_variables=["goal", "observations", "artifacts"],
            ),
        ]

        for tmpl in seed_templates:
            self.register_template(tmpl)

    def register_template(self, template: PromptTemplate) -> None:
        """Register a versioned prompt template."""
        if template.template_id not in self._templates:
            self._templates[template.template_id] = {}
        self._templates[template.template_id][template.version] = template

    def get_template(self, template_id: str, version: str | None = None) -> PromptTemplate:
        """Retrieve a template by ID and optional version.

        If version is omitted, returns the latest registered version.
        """
        versions = self._templates.get(template_id)
        if not versions:
            raise PromptTemplateError(f"Prompt template '{template_id}' not found")

        if version:
            if version not in versions:
                raise PromptTemplateError(
                    f"Version '{version}' for template '{template_id}' not found. "
                    f"Available versions: {list(versions.keys())}"
                )
            return versions[version]

        # Latest version by alphabetical/semantic sort
        latest_key = max(versions.keys())
        return versions[latest_key]

    def format_prompt(
        self,
        template_id: str,
        variables: dict[str, Any] | None = None,
        version: str | None = None,
        **kwargs: Any,
    ) -> tuple[str, str]:
        """Format a prompt template into system and user prompt strings.

        Args:
            template_id: Identifier of the prompt template.
            variables: Keyword arguments dictionary for template interpolation.
            version: Optional version tag.
            **kwargs: Direct keyword arguments for template interpolation.

        Raises:
            PromptTemplateError: If required template variables are missing.

        Returns:
            Tuple of (rendered_system_prompt, rendered_user_prompt).
        """
        template = self.get_template(template_id, version)

        # Merge variables dict with kwargs
        merged_vars: dict[str, Any] = {}
        if variables:
            merged_vars.update(variables)
        merged_vars.update(kwargs)

        # Validate required variables
        missing_vars = [v for v in template.input_variables if v not in merged_vars]
        if missing_vars:
            raise PromptTemplateError(
                f"Missing required template variables for '{template_id}': {missing_vars}"
            )

        try:
            rendered_user = template.user_template.format(**merged_vars)
            rendered_system = (
                template.system_prompt.format(**merged_vars)
                if "{" in template.system_prompt
                else template.system_prompt
            )
        except KeyError as ke:
            raise PromptTemplateError(
                f"Formatting failed for '{template_id}': missing key {ke}"
            ) from ke

        return rendered_system, rendered_user

    def list_templates(self) -> list[PromptTemplate]:
        """List all registered prompt templates and versions."""
        result: list[PromptTemplate] = []
        for version_map in self._templates.values():
            result.extend(version_map.values())
        return result


# Cached singleton
_prompt_manager: PromptManager | None = None


def get_prompt_manager() -> PromptManager:
    """Get the singleton PromptManager instance."""
    global _prompt_manager
    if _prompt_manager is None:
        _prompt_manager = PromptManager()
    return _prompt_manager
