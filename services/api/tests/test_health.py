import pytest
from httpx import ASGITransport, AsyncClient

from services.api.nexus_api.main import app


@pytest.mark.asyncio
async def test_health_endpoint():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/health")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] in ("ok", "degraded")
        assert data["version"] == "0.1.0"
        assert "environment" in data
        assert "database" in data
        assert "timestamp" in data
        assert "database_healthy" in data


@pytest.mark.asyncio
async def test_system_status_v1():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/api/v1/system/status")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "ready"
        assert "dashboard" in data["supported_surfaces"]
        assert "ambient" in data["supported_surfaces"]
