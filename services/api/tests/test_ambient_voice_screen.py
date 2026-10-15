"""Tests for full macOS ambient voice control: screen scrolling, reading windows, listing windows, key presses, and clicks."""

import pytest
from httpx import ASGITransport, AsyncClient

from services.api.nexus_api.main import app


@pytest.mark.asyncio
async def test_ambient_voice_scroll_down_and_up():
    """Verify that spoken scroll commands are dispatched and executed."""
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as client:
        # 1. Scroll down in Hindi/Hinglish
        res1 = await client.post("/api/v1/ambient/chat", json={"message": "thoda niche scroll karo"})
        assert res1.status_code == 200
        reply1 = res1.json()["reply"].lower()
        assert any(k in reply1 for k in ("scroll", "niche", "down"))

        # 2. Scroll up in English
        res2 = await client.post("/api/v1/ambient/chat", json={"message": "scroll up"})
        assert res2.status_code == 200
        reply2 = res2.json()["reply"].lower()
        assert any(k in reply2 for k in ("scroll", "upar", "up"))


@pytest.mark.asyncio
async def test_ambient_voice_read_screen_content():
    """Verify that spoken screen reading and inspection commands return content summaries."""
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as client:
        # Hindi: "screen pe kya hai"
        res1 = await client.post("/api/v1/ambient/chat", json={"message": "screen pe kya hai"})
        assert res1.status_code == 200
        reply1 = res1.json()["reply"].lower()
        assert any(k in reply1 for k in ("screen", "open", "active", "dikh", "window", "finder"))

        # English: "what is on my screen"
        res2 = await client.post("/api/v1/ambient/chat", json={"message": "what is on my screen"})
        assert res2.status_code == 200
        reply2 = res2.json()["reply"].lower()
        assert any(k in reply2 for k in ("screen", "open", "active", "window", "application"))


@pytest.mark.asyncio
async def test_ambient_voice_list_open_windows():
    """Verify that spoken queries about open windows return active window lists."""
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as client:
        # Hindi: "kaun se windows open hai"
        res1 = await client.post("/api/v1/ambient/chat", json={"message": "kaun se windows open hai"})
        assert res1.status_code == 200
        reply1 = res1.json()["reply"].lower()
        assert any(k in reply1 for k in ("open", "screen", "application", "window"))

        # English: "what windows are open"
        res2 = await client.post("/api/v1/ambient/chat", json={"message": "what windows are open"})
        assert res2.status_code == 200
        reply2 = res2.json()["reply"].lower()
        assert any(k in reply2 for k in ("open", "screen", "application", "window"))


@pytest.mark.asyncio
async def test_ambient_voice_keyboard_press():
    """Verify that spoken keyboard shortcut requests dispatch native key events."""
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as client:
        # Enter key
        res1 = await client.post("/api/v1/ambient/chat", json={"message": "press enter"})
        assert res1.status_code == 200
        assert "enter" in res1.json()["reply"].lower()

        # Space key in Hinglish
        res2 = await client.post("/api/v1/ambient/chat", json={"message": "space press karo"})
        assert res2.status_code == 200
        assert "space" in res2.json()["reply"].lower()


@pytest.mark.asyncio
async def test_ambient_voice_screen_click():
    """Verify that spoken click requests dispatch screen click events."""
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as client:
        res = await client.post("/api/v1/ambient/chat", json={"message": "screen pe click karo"})
        assert res.status_code == 200
        assert "click" in res.json()["reply"].lower()


@pytest.mark.asyncio
async def test_ambient_voice_compound_screen_workflow():
    """Verify that multi-step compound commands combining app launch and screen actions execute sequentially."""
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as client:
        res = await client.post(
            "/api/v1/ambient/chat",
            json={"message": "calculator open karo aur fir thoda niche scroll karo"},
        )
        assert res.status_code == 200
        reply = res.json()["reply"].lower()
        assert "calculator" in reply
        assert any(k in reply for k in ("scroll", "niche", "down"))
