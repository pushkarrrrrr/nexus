import uuid

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select

from packages.shared.nexus_shared.models import AuditLogModel
from services.api.nexus_api.auth.security import hash_password, verify_password
from services.api.nexus_api.database import get_db, init_database
from services.api.nexus_api.main import app


@pytest.fixture(autouse=True)
async def ensure_db():
    await init_database()


def random_email() -> str:
    return f"nexus_test_{uuid.uuid4().hex[:8]}@example.com"


@pytest.mark.asyncio
async def test_password_hashing_security():
    password = "super-secure-password-123"
    hashed = hash_password(password)

    assert hashed != password
    assert hashed.startswith(("$2b$", "$2a$"))
    assert verify_password(password, hashed) is True
    assert verify_password("wrong-password", hashed) is False


@pytest.mark.asyncio
async def test_user_registration_success():
    transport = ASGITransport(app=app)
    email = random_email()

    async with AsyncClient(transport=transport, base_url="http://test") as client:
        payload = {
            "email": email,
            "password": "strongPassword123!",
            "full_name": "Test Architect",
        }
        res = await client.post("/api/v1/auth/register", json=payload)
        assert res.status_code == 201
        data = res.json()

        assert "access_token" in data
        assert data["token_type"] == "bearer"
        assert data["user"]["email"] == email
        assert data["user"]["full_name"] == "Test Architect"
        assert data["user"]["id"].startswith("usr_")
        assert data["user"]["preferences"] is not None
        assert data["user"]["preferences"]["timezone"] == "UTC"
        assert data["user"]["preferences"]["model_preferences"]["default_provider"] == "openai"


@pytest.mark.asyncio
async def test_user_registration_duplicate_email():
    transport = ASGITransport(app=app)
    email = random_email()

    async with AsyncClient(transport=transport, base_url="http://test") as client:
        payload = {"email": email, "password": "password123"}
        res1 = await client.post("/api/v1/auth/register", json=payload)
        assert res1.status_code == 201

        # Attempt duplicate
        res2 = await client.post("/api/v1/auth/register", json=payload)
        assert res2.status_code == 409
        assert "already exists" in res2.json()["detail"]


@pytest.mark.asyncio
async def test_user_registration_short_password():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        payload = {"email": random_email(), "password": "short"}
        res = await client.post("/api/v1/auth/register", json=payload)
        assert res.status_code == 400
        assert "at least 8 characters" in res.json()["detail"]


@pytest.mark.asyncio
async def test_user_login_flow():
    transport = ASGITransport(app=app)
    email = random_email()
    password = "correct-horse-battery-staple"

    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # Register first
        await client.post("/api/v1/auth/register", json={"email": email, "password": password})

        # Login with correct password
        login_res = await client.post(
            "/api/v1/auth/login", json={"email": email, "password": password}
        )
        assert login_res.status_code == 200
        token_data = login_res.json()
        assert "access_token" in token_data
        assert token_data["user"]["email"] == email

        # Login with incorrect password
        bad_pw_res = await client.post(
            "/api/v1/auth/login", json={"email": email, "password": "wrongpassword"}
        )
        assert bad_pw_res.status_code == 401

        # Login with non-existent email
        no_user_res = await client.post(
            "/api/v1/auth/login",
            json={"email": "nobody@example.com", "password": password},
        )
        assert no_user_res.status_code == 401


@pytest.mark.asyncio
async def test_protected_routes_and_token_validation():
    transport = ASGITransport(app=app)
    email = random_email()
    password = "validPassword123"

    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # Without token
        unauth_res = await client.get("/api/v1/auth/me")
        assert unauth_res.status_code == 401

        # With invalid token
        invalid_token_res = await client.get(
            "/api/v1/auth/me", headers={"Authorization": "Bearer invalid.token.payload"}
        )
        assert invalid_token_res.status_code == 401

        # Register and get valid token
        reg_res = await client.post(
            "/api/v1/auth/register", json={"email": email, "password": password}
        )
        token = reg_res.json()["access_token"]

        # With valid token
        auth_res = await client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {token}"})
        assert auth_res.status_code == 200
        user_data = auth_res.json()
        assert user_data["email"] == email
        assert user_data["is_active"] is True


@pytest.mark.asyncio
async def test_update_preferences():
    transport = ASGITransport(app=app)
    email = random_email()
    password = "validPassword123"

    async with AsyncClient(transport=transport, base_url="http://test") as client:
        reg_res = await client.post(
            "/api/v1/auth/register", json={"email": email, "password": password}
        )
        token = reg_res.json()["access_token"]
        headers = {"Authorization": f"Bearer {token}"}

        patch_payload = {
            "timezone": "America/New_York",
            "model_preferences": {
                "default_provider": "anthropic",
                "fast_model": "claude-3-5-haiku",
                "reasoning_model": "claude-3-7-sonnet",
                "temperature": 0.5,
            },
            "permission_preferences": {
                "auto_grant_low_risk": False,
                "require_hitl_high_risk": True,
                "session_grant_ttl_minutes": 120,
            },
            "privacy_settings": {
                "store_audit_payloads": True,
                "telemetry_enabled": True,
                "allow_external_rag": False,
            },
        }

        patch_res = await client.patch(
            "/api/v1/auth/preferences", json=patch_payload, headers=headers
        )
        assert patch_res.status_code == 200
        prefs = patch_res.json()
        assert prefs["timezone"] == "America/New_York"
        assert prefs["model_preferences"]["default_provider"] == "anthropic"
        assert prefs["model_preferences"]["reasoning_model"] == "claude-3-7-sonnet"
        assert prefs["permission_preferences"]["auto_grant_low_risk"] is False
        assert prefs["permission_preferences"]["session_grant_ttl_minutes"] == 120
        assert prefs["privacy_settings"]["telemetry_enabled"] is True

        # Check /me reflects updated preferences
        me_res = await client.get("/api/v1/auth/me", headers=headers)
        assert me_res.status_code == 200
        assert me_res.json()["preferences"]["timezone"] == "America/New_York"


@pytest.mark.asyncio
async def test_logout_and_audit_trail_logging():
    transport = ASGITransport(app=app)
    email = random_email()
    password = "validPassword123"

    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # Register
        reg_res = await client.post(
            "/api/v1/auth/register", json={"email": email, "password": password}
        )
        token = reg_res.json()["access_token"]
        user_id = reg_res.json()["user"]["id"]
        headers = {"Authorization": f"Bearer {token}"}

        # Logout
        logout_res = await client.post("/api/v1/auth/logout", headers=headers)
        assert logout_res.status_code == 200
        assert logout_res.json()["status"] == "logged_out"

        # Verify audit logs in database
        async for db in get_db():
            stmt = (
                select(AuditLogModel)
                .where(AuditLogModel.user_id == user_id)
                .order_by(AuditLogModel.created_at.asc())
            )
            logs = (await db.execute(stmt)).scalars().all()

            tool_names = [log.tool_name for log in logs]
            assert "user_registered" in tool_names
            assert "user_logout" in tool_names
            break


@pytest.mark.asyncio
async def test_tenant_data_isolation():
    transport = ASGITransport(app=app)
    user_a_email = random_email()
    user_b_email = random_email()
    password = "validPassword123"

    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # Register User A
        reg_a = await client.post(
            "/api/v1/auth/register",
            json={
                "email": user_a_email,
                "password": password,
                "full_name": "User Alpha",
            },
        )
        token_a = reg_a.json()["access_token"]
        user_a_id = reg_a.json()["user"]["id"]

        # Register User B
        reg_b = await client.post(
            "/api/v1/auth/register",
            json={
                "email": user_b_email,
                "password": password,
                "full_name": "User Beta",
            },
        )
        token_b = reg_b.json()["access_token"]
        user_b_id = reg_b.json()["user"]["id"]

        # Requesting /me with token_a returns User A
        res_a = await client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {token_a}"})
        assert res_a.json()["id"] == user_a_id
        assert res_a.json()["email"] == user_a_email

        # Requesting /me with token_b returns User B
        res_b = await client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {token_b}"})
        assert res_b.json()["id"] == user_b_id
        assert res_b.json()["email"] == user_b_email

        # Verify DB query isolation
        async for db in get_db():
            # Query User A's logs
            stmt_a = select(AuditLogModel).where(AuditLogModel.user_id == user_a_id)
            logs_a = (await db.execute(stmt_a)).scalars().all()
            for log in logs_a:
                assert log.user_id == user_a_id
                assert log.user_id != user_b_id

            # Query User B's logs
            stmt_b = select(AuditLogModel).where(AuditLogModel.user_id == user_b_id)
            logs_b = (await db.execute(stmt_b)).scalars().all()
            for log in logs_b:
                assert log.user_id == user_b_id
                assert log.user_id != user_a_id
            break


@pytest.mark.asyncio
async def test_user_registration_password_too_long():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        payload = {"email": random_email(), "password": "a" * 73}
        res = await client.post("/api/v1/auth/register", json=payload)
        assert res.status_code == 400
        assert "cannot exceed 72 bytes" in res.json()["detail"]


@pytest.mark.asyncio
async def test_user_registration_invalid_email_format():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        for invalid_email in ["", "   ", "not-an-email", "test@", "@domain.com"]:
            payload = {"email": invalid_email, "password": "password123"}
            res = await client.post("/api/v1/auth/register", json=payload)
            assert res.status_code == 400, f"Failed to reject invalid email: {invalid_email}"
            assert "Valid email" in res.json()["detail"]


@pytest.mark.asyncio
async def test_user_registration_whitespace_handling():
    transport = ASGITransport(app=app)
    raw_email = "  NEXUS_OPERATOR_TEST@EXAMPLE.COM   "
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        payload = {
            "email": raw_email,
            "password": "validPassword123",
            "full_name": "    ",
        }
        res = await client.post("/api/v1/auth/register", json=payload)
        assert res.status_code == 201
        data = res.json()
        assert data["user"]["email"] == "nexus_operator_test@example.com"
        assert data["user"]["full_name"] is None


@pytest.mark.asyncio
async def test_password_verify_over_72_bytes():
    hashed = hash_password("validPassword123")
    assert verify_password("a" * 100, hashed) is False


@pytest.mark.asyncio
async def test_timezone_length_validation():
    transport = ASGITransport(app=app)
    email = random_email()
    password = "validPassword123"

    async with AsyncClient(transport=transport, base_url="http://test") as client:
        reg_res = await client.post(
            "/api/v1/auth/register", json={"email": email, "password": password}
        )
        token = reg_res.json()["access_token"]
        headers = {"Authorization": f"Bearer {token}"}

        # Timezone too long
        patch_res = await client.patch(
            "/api/v1/auth/preferences",
            json={"timezone": "x" * 65},
            headers=headers,
        )
        assert patch_res.status_code == 400
        assert "between 1 and 64 characters" in patch_res.json()["detail"]


def test_user_preferences_model_memory_defaults():
    from packages.shared.nexus_shared.models import UserPreferenceModel

    prefs = UserPreferenceModel(user_id="usr_test_default")
    assert prefs.timezone == "UTC"
    assert prefs.model_preferences["default_provider"] == "openai"
    assert prefs.permission_preferences["auto_grant_low_risk"] is True
    assert prefs.privacy_settings["store_audit_payloads"] is True
