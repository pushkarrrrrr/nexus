"""Unified Context Synthesizer & Cross-Memory Personalization for NEXUS.

Bridges Working Memory (scratchpad/session), Episodic Memory (recent executions/outcomes),
and Semantic Memory (user habits/preferences) to produce intelligent, personalized context prompts.
"""

from dataclasses import dataclass, field
from typing import Any

from packages.shared.nexus_shared.logging import get_logger

logger = get_logger("nexus.intelligence.context_synthesizer")


@dataclass
class SynthesizedContext:
    """Consolidated context payload for agent planning and prompt enhancement."""

    session_id: str
    preferred_language: str = "Hinglish/English"
    preferred_browser: str = "Google Chrome"
    preferred_editor: str = "Visual Studio Code"
    recent_tools_used: list[str] = field(default_factory=list)
    active_goals: list[str] = field(default_factory=list)
    recent_errors: list[str] = field(default_factory=list)
    system_prompt_addon: str = ""


class ContextSynthesizer:
    """Manages cross-memory synthesis and builds high-density contextual prompts."""

    def __init__(self) -> None:
        # In-memory session context registry
        self._session_profiles: dict[str, dict[str, Any]] = {}

    def update_session_event(
        self,
        session_id: str,
        tool_name: str | None = None,
        error_msg: str | None = None,
        goal: str | None = None,
        language: str | None = None,
    ) -> None:
        """Record an interaction event into the session's working profile."""
        if session_id not in self._session_profiles:
            self._session_profiles[session_id] = {
                "tools": [],
                "errors": [],
                "goals": [],
                "language": language or "Hinglish/English",
                "browser": "Google Chrome",
                "editor": "Visual Studio Code",
            }

        profile = self._session_profiles[session_id]
        if tool_name and tool_name not in profile["tools"]:
            profile["tools"].append(tool_name)
            if len(profile["tools"]) > 10:
                profile["tools"].pop(0)

        if error_msg and error_msg not in profile["errors"]:
            profile["errors"].append(error_msg[:120])
            if len(profile["errors"]) > 5:
                profile["errors"].pop(0)

        if goal and goal not in profile["goals"]:
            profile["goals"].append(goal)
            if len(profile["goals"]) > 5:
                profile["goals"].pop(0)

        if language:
            profile["language"] = language

    def synthesize(self, session_id: str = "default") -> SynthesizedContext:
        """Generate a structured, token-efficient context bundle for the agent."""
        profile = self._session_profiles.get(session_id, {
            "tools": [],
            "errors": [],
            "goals": [],
            "language": "Hinglish/English",
            "browser": "Google Chrome",
            "editor": "Visual Studio Code",
        })

        goals_snippet = f"Active Goals: {', '.join(profile['goals'])}; " if profile["goals"] else ""
        tools_snippet = f"Recent Tools: {', '.join(profile['tools'][-4:])}; " if profile["tools"] else ""
        errors_snippet = f"Recent Faults to Avoid: {', '.join(profile['errors'][-2:])}; " if profile["errors"] else ""

        addon = (
            f"[NEXUS Context: Preferred Language: {profile['language']}; "
            f"Preferred Editor: {profile['editor']}; {goals_snippet}{tools_snippet}{errors_snippet}]"
        ).strip()

        return SynthesizedContext(
            session_id=session_id,
            preferred_language=profile["language"],
            preferred_browser=profile["browser"],
            preferred_editor=profile["editor"],
            recent_tools_used=list(profile["tools"]),
            active_goals=list(profile["goals"]),
            recent_errors=list(profile["errors"]),
            system_prompt_addon=addon,
        )


# Global singleton synthesizer
_context_synthesizer_singleton: ContextSynthesizer | None = None


def get_context_synthesizer() -> ContextSynthesizer:
    """Retrieve or initialize the global ContextSynthesizer singleton."""
    global _context_synthesizer_singleton
    if _context_synthesizer_singleton is None:
        _context_synthesizer_singleton = ContextSynthesizer()
    return _context_synthesizer_singleton
