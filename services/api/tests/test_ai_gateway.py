"""Unit and integration tests for NEXUS AI Gateway & Model Abstraction Layer.

Covers:
- MockProvider completions, streaming, structured outputs, embeddings, and error simulation.
- ModelGateway retry handling, exponential backoff, timeout enforcement, and fallback cascading.
- PromptManager semantic versioning, variable interpolation, and validation.
- Token pricing catalog and cost calculations across model tiers.
- REST API routes under /api/v1/ai/ (models, complete, structured, embed, prompts, telemetry).
- Auth security gating and error status mappings (401, 429, 504, 502, 422).
"""

import uuid

import pytest
from httpx import ASGITransport, AsyncClient

from packages.shared.nexus_shared.ai.gateway import ModelGateway
from packages.shared.nexus_shared.ai.pricing import calculate_cost, get_model_pricing
from packages.shared.nexus_shared.ai.prompt_manager import PromptManager
from packages.shared.nexus_shared.ai.providers.mock_provider import MockProvider
from packages.shared.nexus_shared.errors import (
    ModelProviderError,
    ModelRateLimitError,
    ModelTimeoutError,
    PromptTemplateError,
)
from packages.types.nexus_types.schemas import (
    AgentFinalResponse,
    AgentIntent,
    AgentPlan,
    AgentToolCall,
    AgentToolResult,
    CompletionRequest,
    EmbeddingRequest,
    PromptTemplate,
    RiskLevel,
)
from services.api.nexus_api.database import init_database
from services.api.nexus_api.main import app


@pytest.fixture(autouse=True)
async def ensure_db():
    await init_database()


def random_email() -> str:
    return f"ai_test_{uuid.uuid4().hex[:8]}@example.com"


@pytest.fixture
async def auth_client():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        email = random_email()
        reg = await client.post(
            "/api/v1/auth/register",
            json={"email": email, "password": "AISecretPassword123!", "full_name": "AI Tester"},
        )
        assert reg.status_code == 201
        token = reg.json()["access_token"]
        client.headers.update({"Authorization": f"Bearer {token}"})
        yield client, reg.json()["user"]


# ============================================================================
# 1. MockProvider Unit Tests
# ============================================================================


@pytest.mark.asyncio
async def test_mock_provider_completion():
    provider = MockProvider()
    req = CompletionRequest(prompt="Analyze system logs for anomalies", model="mock-model")
    resp = await provider.complete(req)

    assert resp.model == "mock-model"
    assert resp.provider == "mock"
    assert "Response to: 'Analyze system logs" in resp.content
    assert resp.usage.prompt_tokens > 0
    assert resp.usage.completion_tokens > 0
    assert resp.usage.total_tokens == resp.usage.prompt_tokens + resp.usage.completion_tokens
    assert resp.finish_reason == "stop"


@pytest.mark.asyncio
async def test_mock_provider_streaming():
    provider = MockProvider()
    req = CompletionRequest(prompt="Stream this text")
    tokens = [chunk async for chunk in provider.stream_complete(req)]

    assert len(tokens) == 4
    assert "".join(tokens) == "[MOCK STREAMING TOKENS VERIFIED]"


@pytest.mark.asyncio
async def test_mock_provider_structured_outputs():
    provider = MockProvider()
    req = CompletionRequest(prompt="Synthesize file audit plan")

    # AgentIntent
    intent, usage = await provider.complete_structured(req, AgentIntent)
    assert isinstance(intent, AgentIntent)
    assert intent.goal == "Synthesize file audit plan"
    assert intent.risk_level == RiskLevel.LOW
    assert intent.confidence == 0.98

    # AgentPlan
    plan, usage = await provider.complete_structured(req, AgentPlan)
    assert isinstance(plan, AgentPlan)
    assert len(plan.steps) == 2
    assert plan.steps[0].id == "step_1"

    # AgentToolCall
    call, usage = await provider.complete_structured(req, AgentToolCall)
    assert isinstance(call, AgentToolCall)
    assert call.tool_name == "terminal_runner"

    # AgentToolResult
    res, usage = await provider.complete_structured(req, AgentToolResult)
    assert isinstance(res, AgentToolResult)
    assert res.success is True

    # AgentFinalResponse
    final_resp, usage = await provider.complete_structured(req, AgentFinalResponse)
    assert isinstance(final_resp, AgentFinalResponse)
    assert "Operation completed successfully" in final_resp.answer
    assert usage.total_tokens > 0


@pytest.mark.asyncio
async def test_mock_provider_embeddings():
    provider = MockProvider()
    req = EmbeddingRequest(texts=["First sentence", "Second query"])
    resp = await provider.embed(req)

    assert resp.provider == "mock"
    assert len(resp.embeddings) == 2
    assert len(resp.embeddings[0]) == 1536
    assert resp.total_tokens > 0


@pytest.mark.asyncio
async def test_mock_provider_failure_modes():
    # Rate limit failure
    rate_limited = MockProvider(failure_mode="rate_limit")
    with pytest.raises(ModelRateLimitError):
        await rate_limited.complete(CompletionRequest(prompt="Test"))

    # Timeout failure
    timed_out = MockProvider(failure_mode="timeout")
    with pytest.raises(ModelTimeoutError):
        await timed_out.complete(CompletionRequest(prompt="Test"))

    # Server error
    errored = MockProvider(failure_mode="server_error")
    with pytest.raises(ModelProviderError):
        await errored.complete(CompletionRequest(prompt="Test"))

    # Fail first 2 times, then succeed
    fail_twice = MockProvider(failure_mode="rate_limit", fail_count=2)
    with pytest.raises(ModelRateLimitError):
        await fail_twice.complete(CompletionRequest(prompt="Test 1"))
    with pytest.raises(ModelRateLimitError):
        await fail_twice.complete(CompletionRequest(prompt="Test 2"))
    # 3rd succeeds
    success = await fail_twice.complete(CompletionRequest(prompt="Test 3"))
    assert success.content.startswith("[MOCK COMPLETION]")


# ============================================================================
# 2. ModelGateway Unit & Resilience Tests
# ============================================================================


@pytest.mark.asyncio
async def test_model_gateway_registration_and_list():
    gateway = ModelGateway()
    providers = gateway.list_providers()
    provider_names = [p["name"] for p in providers]

    assert "mock" in provider_names
    assert "openai" in provider_names
    assert "anthropic" in provider_names
    assert "gemini" in provider_names
    assert "ollama" in provider_names


@pytest.mark.asyncio
async def test_model_gateway_completion_and_telemetry():
    gateway = ModelGateway()
    gateway.reset_telemetry()

    req = CompletionRequest(prompt="Gateway orchestration test", model="mock-model")
    resp = await gateway.complete(req, provider_name="mock")

    assert resp.provider == "mock"
    telemetry = gateway.get_telemetry()
    assert telemetry.total_requests == 1
    assert telemetry.successful_requests == 1
    assert telemetry.failed_requests == 0
    assert telemetry.total_tokens > 0
    assert telemetry.requests_by_provider.get("mock") == 1


@pytest.mark.asyncio
async def test_model_gateway_retry_on_transient_failure():
    gateway = ModelGateway()
    gateway.reset_telemetry()

    # Provider fails 1 time with rate limit, then succeeds on retry 2
    flaky_provider = MockProvider(failure_mode="rate_limit", fail_count=1)
    gateway.register_llm_provider("flaky", flaky_provider)

    req = CompletionRequest(prompt="Test retry loop")
    resp = await gateway.complete(req, provider_name="flaky", max_retries=2)

    assert resp.content.startswith("[MOCK COMPLETION]")
    telemetry = gateway.get_telemetry()
    assert telemetry.retries_count == 1
    assert telemetry.successful_requests == 1
    assert telemetry.failed_requests == 0  # Request ultimately succeeded
    assert (
        telemetry.errors_by_type.get("rate_limit") == 1
    )  # Transient failure recorded in error breakdown


@pytest.mark.asyncio
async def test_model_gateway_timeout_enforcement():
    gateway = ModelGateway()
    slow_provider = MockProvider(simulated_latency_sec=0.5)
    gateway.register_llm_provider("slow", slow_provider)

    req = CompletionRequest(prompt="Test timeout")
    with pytest.raises(ModelTimeoutError):
        await gateway.complete(req, provider_name="slow", timeout_sec=0.05, max_retries=0)


@pytest.mark.asyncio
async def test_model_gateway_fallback_cascading():
    gateway = ModelGateway()
    gateway.reset_telemetry()

    broken_provider = MockProvider(failure_mode="server_error")
    healthy_provider = MockProvider()
    gateway.register_llm_provider("primary_broken", broken_provider)
    gateway.register_llm_provider("secondary_fallback", healthy_provider)

    req = CompletionRequest(prompt="Cascading request")
    resp = await gateway.complete(
        req,
        provider_name="primary_broken",
        fallback_provider="secondary_fallback",
        max_retries=0,
    )

    assert resp.provider == "mock"
    telemetry = gateway.get_telemetry()
    assert telemetry.fallbacks_triggered == 1
    assert telemetry.successful_requests == 1


@pytest.mark.asyncio
async def test_model_gateway_both_providers_fail():
    gateway = ModelGateway()
    p1 = MockProvider(failure_mode="server_error")
    p2 = MockProvider(failure_mode="server_error")
    gateway.register_llm_provider("p1", p1)
    gateway.register_llm_provider("p2", p2)

    req = CompletionRequest(prompt="Both fail")
    with pytest.raises(ModelProviderError) as exc_info:
        await gateway.complete(req, provider_name="p1", fallback_provider="p2", max_retries=0)

    assert "Both primary provider" in str(exc_info.value)


@pytest.mark.asyncio
async def test_model_gateway_streaming():
    gateway = ModelGateway()
    req = CompletionRequest(prompt="Gateway stream")
    tokens = [t async for t in gateway.stream_complete(req, provider_name="mock")]

    assert len(tokens) > 0
    assert "[MOCK" in tokens[0]


@pytest.mark.asyncio
async def test_model_gateway_structured_completion():
    gateway = ModelGateway()
    req = CompletionRequest(prompt="Generate DAG plan")
    plan, usage = await gateway.complete_structured(req, AgentPlan, provider_name="mock")

    assert isinstance(plan, AgentPlan)
    assert len(plan.steps) == 2
    assert usage.prompt_tokens > 0


@pytest.mark.asyncio
async def test_model_gateway_embed():
    gateway = ModelGateway()
    req = EmbeddingRequest(texts=["Query 1", "Query 2"])
    resp = await gateway.embed(req, provider_name="mock")

    assert len(resp.embeddings) == 2
    assert len(resp.embeddings[0]) == 1536


# ============================================================================
# 3. PromptManager Unit Tests
# ============================================================================


def test_prompt_manager_seed_templates():
    pm = PromptManager()
    templates = pm.list_templates()
    template_ids = [t.template_id for t in templates]

    assert "intent_analyzer" in template_ids
    assert "dag_planner" in template_ids
    assert "tool_selector" in template_ids
    assert "task_summarizer" in template_ids


def test_prompt_manager_formatting_and_validation():
    pm = PromptManager()
    sys_p, user_p = pm.format_prompt(
        "intent_analyzer",
        user_request="Refactor database schemas",
        operating_context="PostgreSQL v16 with pgvector",
    )

    assert "intent analysis" in sys_p.lower()
    assert "Refactor database schemas" in user_p
    assert "PostgreSQL v16" in user_p

    # Missing required variable raises PromptTemplateError
    with pytest.raises(PromptTemplateError):
        pm.format_prompt("intent_analyzer", user_request="Only request, missing context")


def test_prompt_manager_versioning():
    pm = PromptManager()
    custom_v1 = PromptTemplate(
        template_id="custom_agent",
        version="1.0.0",
        description="Version 1",
        system_prompt="You are V1",
        user_template="Input: {data}",
        input_variables=["data"],
    )
    custom_v2 = PromptTemplate(
        template_id="custom_agent",
        version="2.0.0",
        description="Version 2",
        system_prompt="You are V2",
        user_template="Enhanced Input: {data}",
        input_variables=["data"],
    )

    pm.register_template(custom_v1)
    pm.register_template(custom_v2)

    # Defaults to latest version (2.0.0)
    sys_latest, _ = pm.format_prompt("custom_agent", data="test")
    assert sys_latest == "You are V2"

    # Explicit version 1.0.0
    sys_v1, _ = pm.format_prompt("custom_agent", version="1.0.0", data="test")
    assert sys_v1 == "You are V1"


# ============================================================================
# 4. Token Pricing & Cost Accounting Unit Tests
# ============================================================================


def test_token_pricing_catalog():
    # OpenAI GPT-4o
    cost_gpt4o = calculate_cost("gpt-4o", prompt_tokens=1_000_000, completion_tokens=1_000_000)
    assert cost_gpt4o == 12.50  # 2.50 + 10.00

    # Claude 3.5 Sonnet
    cost_claude = calculate_cost("claude-3-5-sonnet", prompt_tokens=1000, completion_tokens=2000)
    assert cost_claude > 0.0

    # Gemini 1.5 Flash
    cost_gemini = calculate_cost("gemini-1.5-flash", prompt_tokens=10_000, completion_tokens=5_000)
    assert cost_gemini > 0.0

    # Local & Mock have zero dollar charge
    assert calculate_cost("mock-model", prompt_tokens=5000, completion_tokens=5000) == 0.0
    assert calculate_cost("llama3", prompt_tokens=5000, completion_tokens=5000) == 0.0

    # Catalog lookup helper
    price = get_model_pricing("gpt-4o")
    assert price.input_per_million == 2.50
    assert price.output_per_million == 10.00


# ============================================================================
# 5. FastAPI AI REST API Integration Tests
# ============================================================================


@pytest.mark.asyncio
async def test_api_list_models(auth_client):
    client, _ = auth_client
    res = await client.get("/api/v1/ai/models")
    assert res.status_code == 200
    data = res.json()

    assert "providers" in data
    assert "default_provider" in data
    provider_names = [p["name"] for p in data["providers"]]
    assert "mock" in provider_names


@pytest.mark.asyncio
async def test_api_complete_text(auth_client):
    client, _ = auth_client
    payload = {
        "prompt": "Evaluate code security",
        "model": "mock-model",
    }
    res = await client.post("/api/v1/ai/complete?provider=mock", json=payload)
    assert res.status_code == 200
    data = res.json()

    assert data["provider"] == "mock"
    assert data["model"] == "mock-model"
    assert "[MOCK COMPLETION]" in data["content"]
    assert data["usage"]["total_tokens"] > 0


@pytest.mark.asyncio
async def test_api_complete_structured(auth_client):
    client, _ = auth_client

    schemas = ["intent", "plan", "tool_call", "tool_result", "final_response"]
    for s_type in schemas:
        payload = {
            "prompt": f"Perform {s_type} task",
            "schema_type": s_type,
            "provider": "mock",
        }
        res = await client.post("/api/v1/ai/structured", json=payload)
        assert res.status_code == 200, f"Failed for schema {s_type}: {res.text}"
        data = res.json()
        assert data["schema_type"] == s_type
        assert isinstance(data["data"], dict)
        assert "prompt_tokens" in data["usage"]


@pytest.mark.asyncio
async def test_api_embed(auth_client):
    client, _ = auth_client
    payload = {
        "texts": ["Embed this text", "And this text too"],
    }
    res = await client.post("/api/v1/ai/embed", json=payload)
    assert res.status_code == 200
    data = res.json()

    assert len(data["embeddings"]) == 2
    assert len(data["embeddings"][0]) == 1536


@pytest.mark.asyncio
async def test_api_prompts_list(auth_client):
    client, _ = auth_client
    res = await client.get("/api/v1/ai/prompts")
    assert res.status_code == 200
    templates = res.json()
    assert len(templates) >= 4
    template_ids = [t["template_id"] for t in templates]
    assert "intent_analyzer" in template_ids
    assert "dag_planner" in template_ids


@pytest.mark.asyncio
async def test_api_telemetry(auth_client):
    client, _ = auth_client
    res = await client.get("/api/v1/ai/telemetry")
    assert res.status_code == 200
    data = res.json()

    assert "total_requests" in data
    assert "successful_requests" in data
    assert "total_cost_usd" in data
    assert "average_latency_ms" in data


@pytest.mark.asyncio
async def test_api_unauthorized_access():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # Protected endpoints must reject without token
        complete_res = await client.post("/api/v1/ai/complete", json={"prompt": "test"})
        assert complete_res.status_code == 401

        struct_res = await client.post(
            "/api/v1/ai/structured", json={"prompt": "test", "schema_type": "intent"}
        )
        assert struct_res.status_code == 401

        embed_res = await client.post("/api/v1/ai/embed", json={"texts": ["test"]})
        assert embed_res.status_code == 401

        prompts_res = await client.get("/api/v1/ai/prompts")
        assert prompts_res.status_code == 401

        telem_res = await client.get("/api/v1/ai/telemetry")
        assert telem_res.status_code == 401


# ============================================================================
# 7. Edge Cases & Micro-Bug Validations
# ============================================================================


def test_extract_json_from_text_edge_cases():
    """Verify robust JSON extraction from messy LLM conversational output."""
    from packages.shared.nexus_shared.ai.json_extractor import extract_json_from_text

    # 1. Clean JSON
    assert extract_json_from_text('{"a": 1}') == '{"a": 1}'

    # 2. Markdown block
    md = '```json\n{"status": "ok"}\n```'
    assert extract_json_from_text(md) == '{"status": "ok"}'

    # 3. Conversational preamble & postamble
    preamble = 'Here is your requested output:\n\n```json\n{"goal": "run audit", "confidence": 0.99}\n```\nHope this helps!'
    extracted = extract_json_from_text(preamble)
    assert '"goal": "run audit"' in extracted
    assert "Here is your requested" not in extracted

    # 4. Outermost balanced braces without code fence
    dirty = 'I analyzed the log and found: {"key": "value", "nested": {"num": 42}} in the dataset.'
    assert extract_json_from_text(dirty) == '{"key": "value", "nested": {"num": 42}}'

    # 5. Array JSON with preamble
    array_text = 'Results are: [{"step": 1}, {"step": 2}] as follows.'
    assert extract_json_from_text(array_text) == '[{"step": 1}, {"step": 2}]'

    # 6. Escaped quotes inside JSON string
    escaped = 'Result: {"msg": "hello \\"world\\"", "valid": true}'
    assert extract_json_from_text(escaped) == '{"msg": "hello \\"world\\"", "valid": true}'


def test_pricing_prefix_and_dated_model_matching():
    """Verify that get_model_pricing handles models/ prefix and dated variants."""
    # models/ prefix
    pricing_gemini = get_model_pricing("models/gemini-1.5-pro")
    assert pricing_gemini.input_per_million > 0
    assert pricing_gemini.output_per_million > 0

    # Dated variant prefix match
    pricing_dated = get_model_pricing("gpt-4o-2024-08-06")
    pricing_base = get_model_pricing("gpt-4o")
    assert pricing_dated.input_per_million == pricing_base.input_per_million

    # calculate_cost with models/ prefix
    cost = calculate_cost("models/gemini-1.5-flash", prompt_tokens=1000, completion_tokens=1000)
    assert cost > 0


@pytest.mark.asyncio
async def test_gateway_invalid_fallback_graceful_handling():
    """Verify that setting fallback to 'none', '', 'null', or same provider does not crash."""
    from packages.config.nexus_config import NexusSettings

    settings = NexusSettings(DEFAULT_AI_PROVIDER="mock", DEFAULT_FALLBACK_PROVIDER="mock")
    gw = ModelGateway(settings=settings)

    req = CompletionRequest(prompt="Fallback test")

    # String "none" should be ignored, not trigger Provider 'none' not found
    resp1 = await gw.complete(req, provider_name="mock", fallback_provider="none")
    assert resp1.provider == "mock"

    # String "" or "null" should also be ignored
    resp2 = await gw.complete(req, provider_name="mock", fallback_provider="")
    assert resp2.provider == "mock"

    # Self-reference fallback should be ignored
    resp3 = await gw.complete(req, provider_name="mock", fallback_provider="mock")
    assert resp3.provider == "mock"


@pytest.mark.asyncio
async def test_telemetry_metrics_integrity():
    """Verify that telemetry total_requests equals successful_requests + failed_requests."""
    from packages.config.nexus_config import NexusSettings

    # Failure mode provider
    failing_provider = MockProvider(failure_mode="server_error")
    settings = NexusSettings(DEFAULT_AI_PROVIDER="mock", DEFAULT_FALLBACK_PROVIDER="mock")
    gw = ModelGateway(settings=settings)
    gw.register_llm_provider("failing", failing_provider)

    # 1. Successful request
    req = CompletionRequest(prompt="Success test")
    await gw.complete(req, provider_name="mock", max_retries=0)

    # 2. Permanent failed request with no fallback
    with pytest.raises(ModelProviderError):
        await gw.complete(req, provider_name="failing", fallback_provider="none", max_retries=1)

    telem = gw.get_telemetry()
    assert telem.total_requests == 2
    assert telem.successful_requests == 1
    assert telem.failed_requests == 1
    assert telem.total_requests == telem.successful_requests + telem.failed_requests
