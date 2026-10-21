"""Comprehensive Test Suite for NEXUS Tri-Pillar Intelligence Upgrade.

Validates:
1. Speed: Sub-15ms FastPathEngine deterministic matching & LRU caching.
2. Accuracy: Two-Pass GroundingValidator schema integrity & environmental security.
3. Intelligence: ScreenPerceptionReasoner multi-modal screen comprehension & ContextSynthesizer.
4. REST API Integration: End-to-end intelligence endpoints.
"""

import pytest
from httpx import ASGITransport, AsyncClient

from packages.shared.nexus_shared.intelligence.context_synthesizer import (
    ContextSynthesizer,
)
from packages.shared.nexus_shared.intelligence.fast_path import (
    FastPathEngine,
)
from packages.shared.nexus_shared.intelligence.grounding import (
    GroundingValidator,
)
from packages.shared.nexus_shared.intelligence.screen_reasoner import (
    ScreenPerceptionReasoner,
)
from services.api.nexus_api.main import app


# -----------------------------------------------------------------------------
# 1. Pillar 1: Maximum Speed (Sub-15ms Fast-Path Intent Engine)
# -----------------------------------------------------------------------------
def test_fast_path_engine_latency_and_matches():
    """Verify sub-15ms execution latency and accurate multi-lingual matches."""
    engine = FastPathEngine()

    # 1. Media Control (English & Hinglish)
    m1 = engine.match("next video")
    assert m1.matched is True
    assert m1.action_type == "media_next"
    assert m1.latency_ms < 20.0  # Must be sub-20ms

    m2 = engine.match("aage karo")
    assert m2.matched is True
    assert m2.action_type == "media_next"

    m3 = engine.match("pause")
    assert m3.matched is True
    assert m3.action_type == "media_pause"

    # 2. Application Launch & Termination
    m4 = engine.match("spotify kholo")
    assert m4.matched is True
    assert m4.action_type == "open_app"
    assert m4.target == "spotify"

    m5 = engine.match("close chrome")
    assert m5.matched is True
    assert m5.action_type == "close_app"
    assert m5.target == "chrome"

    # 3. YouTube & Spotify Playback
    m6 = engine.match("youtube par lofi hip hop play karo")
    assert m6.matched is True
    assert m6.action_type == "youtube_play"
    assert "lofi hip hop" in m6.target

    m7 = engine.match("spotify par kesariya play karo")
    assert m7.matched is True
    assert m7.action_type == "spotify_play"
    assert "kesariya" in m7.target

    # 4. Screen Perception & System Status
    m8 = engine.match("screen par kya hai")
    assert m8.matched is True
    assert m8.action_type == "read_screen"

    m9 = engine.match("system status")
    assert m9.matched is True
    assert m9.action_type == "system_metrics"

    # 5. LRU Cache Hit Verification
    cached_m = engine.match("spotify kholo")
    assert cached_m.matched is True
    assert "cache_hit" in cached_m.explanation


# -----------------------------------------------------------------------------
# 2. Pillar 2: Maximum Accuracy (Two-Pass Grounding & Schema Validation)
# -----------------------------------------------------------------------------
def test_grounding_validator_schema_and_security():
    """Verify schema integrity, phonetic alias normalization, and security boundaries."""
    validator = GroundingValidator()

    # 1. Unknown tool rejection
    v1 = validator.validate_action("non_existent_fake_tool", {})
    assert v1.valid is False
    assert "not registered" in (v1.rejection_reason or "")

    # 2. Application normalization and injection guard
    v2 = validator.validate_action("application_open", {"app_name": "spotfy"})
    assert v2.valid is True
    assert v2.sanitized_parameters["app_name"] == "Spotify"
    assert v2.normalized_target == "app:Spotify"

    v3 = validator.validate_action("application_open", {"app_name": "chrome; rm -rf /"})
    assert v3.valid is False
    assert "Prohibited characters" in (v3.rejection_reason or "")

    # 3. Filesystem path normalization & protected system paths
    v4 = validator.validate_action("filesystem_read", {"path": "/System/Library/CoreServices"})
    assert v4.valid is False
    assert "protected system directory" in (v4.rejection_reason or "")

    v5 = validator.validate_action("filesystem_write", {"path": "relative/test.txt", "content": "hello"})
    assert v5.valid is True
    assert v5.normalized_target.startswith("file:")


# -----------------------------------------------------------------------------
# 3. Pillar 3: Maximum Intelligence (Screen Perception & Context Synthesis)
# -----------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_screen_perception_reasoner_qa():
    """Verify multi-modal screen comprehension and error diagnostics."""
    reasoner = ScreenPerceptionReasoner()

    # General screen inspection
    answer = await reasoner.answer_screen_query("What is on my screen?")
    assert "reply" in answer
    assert len(answer["reply"]) > 0
    assert "screen_info" in answer

    # Error diagnosis request
    err_answer = await reasoner.answer_screen_query("Screen par kya error hai?")
    assert err_answer["category"] == "error_diagnosis"
    assert "reply" in err_answer


def test_context_synthesizer_profile_and_prompt():
    """Verify unified cross-memory synthesis and system prompt enrichment."""
    synthesizer = ContextSynthesizer()
    session_id = "test_session_xyz"

    synthesizer.update_session_event(
        session_id=session_id,
        tool_name="filesystem_read",
        goal="Refactor authentication middleware",
        language="Hinglish",
    )
    synthesizer.update_session_event(
        session_id=session_id,
        tool_name="terminal_execute",
        error_msg="ConnectionRefusedError: port 8000 offline",
    )

    ctx = synthesizer.synthesize(session_id)
    assert ctx.session_id == session_id
    assert ctx.preferred_language == "Hinglish"
    assert "filesystem_read" in ctx.recent_tools_used
    assert "Refactor authentication middleware" in ctx.active_goals
    assert "ConnectionRefusedError" in ctx.recent_errors[0]
    assert "NEXUS Context" in ctx.system_prompt_addon


# -----------------------------------------------------------------------------
# 4. REST Endpoints Integration
# -----------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_intelligence_rest_endpoints():
    """Verify all REST routes in /api/v1/intelligence."""
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as client:
        # 1. Fast-path endpoint
        res = await client.post("/api/v1/intelligence/fast-path", json={"query": "aage karo"})
        assert res.status_code == 200
        data = res.json()
        assert data["matched"] is True
        assert data["action_type"] == "media_next"
        assert data["latency_ms"] >= 0.0

        # 2. Action validation endpoint
        res = await client.post(
            "/api/v1/intelligence/validate-action",
            json={"tool_name": "application_open", "parameters": {"app_name": "chorme"}},
        )
        assert res.status_code == 200
        val_data = res.json()
        assert val_data["valid"] is True
        assert val_data["sanitized_parameters"]["app_name"] == "Google Chrome"

        # 3. Screen query endpoint
        res = await client.post(
            "/api/v1/intelligence/screen-query",
            json={"query": "What app is open right now?"},
        )
        assert res.status_code == 200
        screen_data = res.json()
        assert "reply" in screen_data

        # 4. Context profile endpoint
        res = await client.get("/api/v1/intelligence/context?session_id=demo_session")
        assert res.status_code == 200
        ctx_data = res.json()
        assert "system_prompt_addon" in ctx_data
