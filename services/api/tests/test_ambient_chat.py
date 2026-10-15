import pytest
from httpx import ASGITransport, AsyncClient

from services.api.nexus_api.main import app


@pytest.mark.asyncio
async def test_ambient_chat_endpoint_success():
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as client:
        response = await client.post(
            "/api/v1/ambient/chat",
            json={"message": "Hello Nexus, are you ready to assist me?"},
        )
        assert response.status_code == 200
        data = response.json()
        assert "reply" in data
        assert len(data["reply"]) > 0
        assert data["provider"] in ("gemini", "mock")


@pytest.mark.asyncio
async def test_ambient_chat_with_context():
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as client:
        response = await client.post(
            "/api/v1/ambient/chat",
            json={
                "message": "What app am I currently using?",
                "context": {"app_name": "Safari", "window_title": "Google Search"},
            },
        )
        assert response.status_code == 200
        data = response.json()
        assert "reply" in data
        assert len(data["reply"]) > 0


@pytest.mark.asyncio
async def test_ambient_voice_actions():
    """Verify that OS app control, media playback, youtube, and search commands are dispatched."""
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as client:
        # 1. Media Next
        res = await client.post("/api/v1/ambient/chat", json={"message": "next video"})
        assert res.status_code == 200
        assert res.json()["model"] in ("nexus-os-action", "gemini-ambient-processor")

        # 2. Media Previous
        res = await client.post("/api/v1/ambient/chat", json={"message": "phele wla vide"})
        assert res.status_code == 200
        assert res.json()["model"] in ("nexus-os-action", "gemini-ambient-processor")

        # 3. Media Forward
        res = await client.post("/api/v1/ambient/chat", json={"message": "aage karo"})
        assert res.status_code == 200
        assert res.json()["model"] in ("nexus-os-action", "gemini-ambient-processor")

        # 4. Media Rewind
        res = await client.post("/api/v1/ambient/chat", json={"message": "piche karo"})
        assert res.status_code == 200
        assert res.json()["model"] in ("nexus-os-action", "gemini-ambient-processor")

        # 5. YouTube Play
        res = await client.post("/api/v1/ambient/chat", json={"message": "youtube mein lofi beats play kro"})
        assert res.status_code == 200
        assert res.json()["model"] in ("nexus-os-action", "gemini-ambient-processor")

        # 6. Web Search
        res = await client.post("/api/v1/ambient/chat", json={"message": "web par jao mechanical keyboard search kro"})
        assert res.status_code == 200
        assert res.json()["model"] in ("nexus-os-action", "gemini-ambient-processor")


@pytest.mark.asyncio
async def test_ambient_interactive_and_multi_task_flows():
    """Test interactive YouTube, Spotify, Notes context save, and Multi-Task queueing."""
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as client:
        # 1. YouTube Interactive Open: "youtube kholo" -> asks what to play or opens
        res = await client.post("/api/v1/ambient/chat", json={"message": "youtube kholo"})
        assert res.status_code == 200
        assert any(w in res.json()["reply"] for w in ("Kya play karna hai", "YouTube", "khol"))

        # Follow-up: User specifies what to play
        res2 = await client.post("/api/v1/ambient/chat", json={"message": "lofi chill songs"})
        assert res2.status_code == 200
        assert any(k in res2.json()["reply"] for k in ("lofi chill songs", "Spotify", "YouTube", "play"))

        # 2. Spotify Interactive Open: "spotify kholo" -> asks which song
        res = await client.post("/api/v1/ambient/chat", json={"message": "spotify kholo"})
        assert res.status_code == 200
        assert any(
            phrase.lower() in res.json()["reply"].lower()
            for phrase in ("kaun sa song play karna hai", "spotify open", "opened spotify")
        )

        # Follow-up: User specifies song
        res2 = await client.post("/api/v1/ambient/chat", json={"message": "kesariya"})
        assert res2.status_code == 200
        assert any(
            phrase.lower() in res2.json()["reply"].lower()
            for phrase in ("spotify par 'kesariya' play kar diya", "playing kesariya on spotify")
        )

        # 3. Contextual Notes Save: "isko note mein add kar do"
        # First ask a question so assistant produces an explanation
        res_qa = await client.post("/api/v1/ambient/chat", json={"message": "What is SDLC in software?"})
        assert res_qa.status_code == 200
        # Now ask to save it to Notes
        res_save = await client.post("/api/v1/ambient/chat", json={"message": "isko note mein add kr do"})
        assert res_save.status_code == 200
        assert any(
            w.lower() in res_save.json()["reply"].lower()
            for w in ("notes app mein save kar diya", "notes mein add", "saved")
        )

        # 4. Multi-Task Queue: compound command
        res_multi = await client.post(
            "/api/v1/ambient/chat",
            json={"message": "calculator open karo aur fir spotify par arijit singh play karo"},
        )
        assert res_multi.status_code == 200
        assert "calculator" in res_multi.json()["reply"].lower()
        assert "spotify" in res_multi.json()["reply"].lower()

        # 5. WhatsApp Two-Step Draft & Confirm
        res_wa = await client.post(
            "/api/v1/ambient/chat",
            json={"message": "Rahul ko message bhejo kal subah milte hain aur send karo"},
        )
        assert res_wa.status_code == 200
        assert any(w in res_wa.json()["reply"].lower() for w in ("send kar doon", "send", "rahul"))

        # Confirmation
        res_wa_confirm = await client.post("/api/v1/ambient/chat", json={"message": "haan send kar do"})
        assert res_wa_confirm.status_code == 200
        assert any(w in res_wa_confirm.json()["reply"].lower() for w in ("message send kar diya", "send", "bhej diya"))

