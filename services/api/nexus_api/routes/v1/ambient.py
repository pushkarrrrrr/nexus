"""NEXUS Ambient Voice Conversation API Route.

Provides ultra-fast conversational intelligence via Google Gemini for the summonable
NEXUS Ambient Voice Orb on macOS.
"""

from typing import Any

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field

from packages.shared.nexus_shared.ai.gateway import get_model_gateway
from packages.shared.nexus_shared.intelligence.context_synthesizer import get_context_synthesizer
from packages.shared.nexus_shared.logging import get_logger
from packages.shared.nexus_shared.models import UserModel
from packages.types.nexus_types.schemas import CompletionRequest
from services.api.nexus_api.auth.dependencies import get_optional_current_user
from services.api.nexus_api.routes.v1.voice_action_dispatcher import (
    set_last_assistant_reply,
    try_dispatch_voice_action,
)

logger = get_logger("nexus.api.ambient")
ambient_router = APIRouter(prefix="/ambient", tags=["ambient"])

AMBIENT_SYSTEM_PROMPT = (
    "You are NEXUS, an intelligent, calm, fast, and friendly AI voice assistant for macOS. "
    "Respond conversationally, concisely, and naturally in 1 to 2 short sentences suitable for text-to-speech voice playback. "
    "Never use markdown formatting like asterisks, bullet points, or code blocks in your response because your output is read aloud. "
    "Support English, Hindi, and Hinglish naturally depending on how the user addresses you. "
    "Be direct, witty, and warmly helpful."
)


class AmbientChatRequest(BaseModel):
    message: str = Field(..., description="The user's spoken voice transcript or message")
    context: dict[str, Any] | None = Field(default=None, description="Active macOS app context")
    history: list[dict[str, str]] | None = Field(default=None, description="Recent conversation turns")


class AmbientChatResponse(BaseModel):
    reply: str
    model: str
    provider: str


@ambient_router.post("/chat", response_model=AmbientChatResponse)
async def ambient_chat(
    req: AmbientChatRequest,
    current_user: UserModel | None = Depends(get_optional_current_user),
) -> AmbientChatResponse:
    """Conversational and actionable endpoint for ambient voice chat."""
    user_prompt = req.message.strip()

    # 1. First, check if this is an actionable voice OS command or conversational query processed via Gemini
    try:
        action_result = await try_dispatch_voice_action(user_prompt, req.context)
        if action_result:
            logger.info("ambient_voice_action_dispatched", action=action_result.get("action"))
            reply_text = action_result["reply"]
            set_last_assistant_reply(reply_text)
            return AmbientChatResponse(
                reply=reply_text,
                model="gemini-ambient-processor",
                provider="gemini",
            )
    except Exception as exc:  # noqa: BLE001
        logger.warning(f"[ambient_chat] Voice action dispatch error: {exc}")

    # 2. General conversational queries powered by Gemini with synthesized cross-memory context
    gateway = get_model_gateway()
    session_key = str(current_user.id) if current_user else "default"
    ctx = get_context_synthesizer().synthesize(session_key)

    augmented_prompt = user_prompt
    if req.context and req.context.get("app_name"):
        context_hint = f" [Current frontmost app: {req.context.get('app_name')}]"
        augmented_prompt += context_hint

    system_prompt_full = f"{AMBIENT_SYSTEM_PROMPT}\n{ctx.system_prompt_addon}".strip()

    try:
        completion_req = CompletionRequest(
            prompt=augmented_prompt,
            system_prompt=system_prompt_full,
            model="gemini-3.5-flash-lite",
            temperature=0.7,
            max_tokens=150,
        )
        response = await gateway.complete(
            completion_req,
            provider_name="gemini",
            fallback_provider="mock",
            timeout_sec=8.0,   # Ambient is real-time voice — fail fast over slow retries
            max_retries=0,     # No retries for interactive voice; frontend has its own fallback
        )
        clean_reply = response.content.strip().replace("*", "").replace("#", "")
        final_reply = clean_reply or "I'm here! How can I help you?"
        set_last_assistant_reply(final_reply)

        # Update synthesized memory profile
        get_context_synthesizer().update_session_event(
            session_id=session_key,
            goal=user_prompt[:80],
        )

        return AmbientChatResponse(
            reply=final_reply,
            model=response.model,
            provider=response.provider,
        )
    except Exception as exc:  # noqa: BLE001
        logger.warning(f"[ambient_chat] Gemini completion failed, fallback: {exc}")
        fallback_msg = "Hello! I am NEXUS, your AI assistant. How can I help you right now?"
        set_last_assistant_reply(fallback_msg)
        return AmbientChatResponse(
            reply=fallback_msg,
            model="gemini-fallback",
            provider="gemini",
        )

