"""Intelligence & Reasoning API Endpoints for NEXUS.

Exposes endpoints for sub-15ms fast-path matching, two-pass action validation,
multi-modal screen comprehension, and synthesized cross-memory context.
"""

from typing import Any

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field

from packages.shared.nexus_shared.intelligence.context_synthesizer import get_context_synthesizer
from packages.shared.nexus_shared.intelligence.fast_path import get_fast_path_engine
from packages.shared.nexus_shared.intelligence.grounding import get_grounding_validator
from packages.shared.nexus_shared.intelligence.screen_reasoner import get_screen_perception_reasoner
from services.api.nexus_api.auth.dependencies import get_optional_current_user

intelligence_router = APIRouter(prefix="/intelligence", tags=["intelligence"])


class FastPathRequest(BaseModel):
    query: str = Field(..., description="User voice or text prompt")


class ValidateActionRequest(BaseModel):
    tool_name: str = Field(..., description="Target tool identifier")
    parameters: dict[str, Any] = Field(default_factory=dict, description="Action arguments")


class ScreenQueryRequest(BaseModel):
    query: str = Field(default="What is on my screen?", description="Contextual question about active screen")
    target_app: str | None = Field(default=None, description="Optional target app filter")


@intelligence_router.post("/fast-path")
async def evaluate_fast_path(req: FastPathRequest):
    """Evaluate text against sub-15ms deterministic multi-lingual intent table."""
    engine = get_fast_path_engine()
    result = engine.match(req.query)
    return {
        "matched": result.matched,
        "action_type": result.action_type,
        "target": result.target,
        "args": result.args,
        "confidence": result.confidence,
        "latency_ms": result.latency_ms,
        "explanation": result.explanation,
        "reply_template": result.reply_template,
    }


@intelligence_router.post("/validate-action")
async def validate_action(req: ValidateActionRequest):
    """Perform two-pass schema verification and environmental ground-truth validation."""
    validator = get_grounding_validator()
    verdict = validator.validate_action(req.tool_name, req.parameters)
    return {
        "valid": verdict.valid,
        "tool_name": verdict.tool_name,
        "normalized_target": verdict.normalized_target,
        "sanitized_parameters": verdict.sanitized_parameters,
        "confidence_score": verdict.confidence_score,
        "risk_level": verdict.risk_level,
        "requires_disambiguation": verdict.requires_disambiguation,
        "rejection_reason": verdict.rejection_reason,
    }


@intelligence_router.post("/screen-query")
async def inspect_and_reason_screen(req: ScreenQueryRequest):
    """Analyze active window contents, accessibility nodes, and answer screen Q&A."""
    reasoner = get_screen_perception_reasoner()
    answer = await reasoner.answer_screen_query(req.query, target_app=req.target_app)
    return answer


@intelligence_router.get("/context")
async def get_synthesized_context(
    session_id: str = "default",
    current_user=Depends(get_optional_current_user),
):
    """Retrieve synthesized cross-memory profile for the given session."""
    user_session = f"user_{current_user.id}" if current_user else session_id
    synthesizer = get_context_synthesizer()
    ctx = synthesizer.synthesize(user_session)
    return {
        "session_id": ctx.session_id,
        "preferred_language": ctx.preferred_language,
        "preferred_browser": ctx.preferred_browser,
        "preferred_editor": ctx.preferred_editor,
        "recent_tools_used": ctx.recent_tools_used,
        "active_goals": ctx.active_goals,
        "recent_errors": ctx.recent_errors,
        "system_prompt_addon": ctx.system_prompt_addon,
    }
