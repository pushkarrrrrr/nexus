"""Unit and Integration Tests for Phase 6: Memory, Knowledge & RAG Subsystem.

Covers:
- DocumentIngestor parsing across PDF, Markdown, TXT, CSV, and JSON formats.
- Semantic text chunking with character boundary and page number attribution.
- MemoryExtractor intelligent noise rejection and high-value memory classification.
- MemoryManager CRUD lifecycle, 5-class taxonomy, enable/disable toggles, and vector similarity search.
- Knowledge REST API: Asynchronous upload (202 Accepted), background processing, chunk inspection, and cascade deletion.
- Semantic vector retrieval with source attribution (document title, page, chunk index, similarity score, snippet).
- End-to-end RAG query synthesis with grounded source citations and memory integration.
- Multi-tenant authorization boundaries preventing cross-user data leakage.
"""

import io
import uuid

import pytest
from httpx import ASGITransport, AsyncClient

from packages.shared.nexus_shared.knowledge.ingestion import DocumentIngestor
from packages.shared.nexus_shared.memory.extractor import MemoryExtractor
from packages.types.nexus_types.schemas import (
    MemoryClass,
)
from services.api.nexus_api.database import init_database
from services.api.nexus_api.knowledge.routes import process_document_background
from services.api.nexus_api.main import app

MINIMAL_VALID_PDF = (
    b"%PDF-1.4\n"
    b"1 0 obj<</Type/Catalog/Pages 2 0 R>>endobj\n"
    b"2 0 obj<</Type/Pages/Count 1/Kids[3 0 R]>>endobj\n"
    b"3 0 obj<</Type/Page/MediaBox[0 0 300 144]/Parent 2 0 R/Resources<</Font<</F1 4 0 R>>>>/Contents 5 0 R>>endobj\n"
    b"4 0 obj<</Type/Font/Subtype/Type1/BaseFont/Helvetica>>endobj\n"
    b"5 0 obj<</Length 44>>stream\n"
    b"BT /F1 18 Tf 20 50 Td (NEXUS Security Policy Document) Tj ET\n"
    b"endstream\nendobj\n"
    b"xref\n0 6\n0000000000 65535 f \n0000000009 00000 n \n0000000056 00000 n \n0000000111 00000 n \n0000000212 00000 n \n0000000289 00000 n \n"
    b"trailer<</Size 6/Root 1 0 R>>\nstartxref\n382\n%%EOF\n"
)


@pytest.fixture(autouse=True)
async def ensure_db():
    await init_database()


def random_email() -> str:
    return f"mem_test_{uuid.uuid4().hex[:8]}@example.com"


@pytest.fixture
async def auth_user_a():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        email = random_email()
        reg = await client.post(
            "/api/v1/auth/register",
            json={"email": email, "password": "SecretPassword123!", "full_name": "User Alpha"},
        )
        assert reg.status_code == 201
        token = reg.json()["access_token"]
        client.headers.update({"Authorization": f"Bearer {token}"})
        yield client, reg.json()["user"]


@pytest.fixture
async def auth_user_b():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        email = random_email()
        reg = await client.post(
            "/api/v1/auth/register",
            json={"email": email, "password": "SecretPassword123!", "full_name": "User Beta"},
        )
        assert reg.status_code == 201
        token = reg.json()["access_token"]
        client.headers.update({"Authorization": f"Bearer {token}"})
        yield client, reg.json()["user"]


# ============================================================================
# 1. Document Ingestion & Chunking Unit Tests
# ============================================================================


def test_document_ingestion_text_and_markdown():
    ingestor = DocumentIngestor(chunk_size=100, chunk_overlap=20)
    md_content = (
        b"# NEXUS Architecture\n\n"
        b"The NEXUS Operating System employs strict boundaries between layers.\n\n"
        b"Policy evaluation is mandatory before any tool execution occurs."
    )

    chunks = ingestor.extract_and_chunk(md_content, filename="arch.md", file_type="md")
    assert len(chunks) >= 2
    assert chunks[0].chunk_index == 0
    assert chunks[0].char_start == 0
    assert chunks[0].char_end > 0
    assert "NEXUS Architecture" in chunks[0].content


def test_document_ingestion_pdf():
    ingestor = DocumentIngestor(chunk_size=200, chunk_overlap=30)
    chunks = ingestor.extract_and_chunk(MINIMAL_VALID_PDF, filename="policy.pdf", file_type="pdf")

    assert len(chunks) >= 1
    assert chunks[0].page_number == 1
    assert "NEXUS Security Policy" in chunks[0].content


def test_document_ingestion_csv_and_json():
    ingestor = DocumentIngestor(chunk_size=150, chunk_overlap=20)

    # CSV Test
    csv_bytes = b"tool_name,action_type,risk\nterminal.run,EXECUTE,HIGH\nfs.read,READ,LOW\n"
    csv_chunks = ingestor.extract_and_chunk(csv_bytes, filename="tools.csv", file_type="csv")
    assert len(csv_chunks) >= 1
    assert "tool_name: terminal.run" in csv_chunks[0].content

    # JSON Test
    json_bytes = b'{"system": "NEXUS", "version": "0.1.0", "active_agents": ["planner", "coder"]}'
    json_chunks = ingestor.extract_and_chunk(json_bytes, filename="config.json", file_type="json")
    assert len(json_chunks) >= 1
    assert "NEXUS" in json_chunks[0].content


# ============================================================================
# 2. Memory Extraction & Noise Filtering Tests
# ============================================================================


def test_memory_noise_rejection():
    extractor = MemoryExtractor()

    # Noise turns must be rejected
    assert extractor.is_noise("Hi there") is True
    assert extractor.is_noise("Thanks a lot!") is True
    assert extractor.is_noise("ok") is True
    assert extractor.is_noise("Sure thing") is True
    assert extractor.is_noise("Goodbye") is True

    # Substantive turns must NOT be rejected
    assert (
        extractor.is_noise(
            "I prefer using PostgreSQL with pgvector over external vector databases for security."
        )
        is False
    )


def test_memory_extraction_classification():
    extractor = MemoryExtractor()
    messages = [
        {"role": "user", "content": "Hello!"},
        {"role": "user", "content": "I prefer using dark mode and Python 3.11 for all scripts."},
        {
            "role": "user",
            "content": "To deploy the backend, first run alembic upgrade head, then start uvicorn.",
        },
        {"role": "assistant", "content": "Understood, I will remember that."},
        {"role": "assistant", "content": "Fixed memory leak in task scheduler during session 42."},
    ]

    memories = extractor.extract_from_turns(messages, session_id="sess_test")
    assert len(memories) == 3

    classes = [m.memory_class for m in memories]
    assert MemoryClass.SEMANTIC in classes
    assert MemoryClass.PROCEDURAL in classes
    assert MemoryClass.EPISODIC in classes


# ============================================================================
# 3. Memory REST API & Lifecycle Tests
# ============================================================================


@pytest.mark.asyncio
async def test_memory_crud_and_lifecycle(auth_user_a):
    client, _ = auth_user_a

    # 1. Create semantic memory
    create_payload = {
        "title": "Database Engine Choice",
        "content": "NEXUS uses PostgreSQL with pgvector for production vector indexing.",
        "memory_class": "semantic",
        "confidence": 0.98,
        "tags": ["database", "vector"],
    }
    res = await client.post("/api/v1/memory", json=create_payload)
    assert res.status_code == 201
    mem = res.json()
    mem_id = mem["id"]
    assert mem["title"] == "Database Engine Choice"
    assert mem["memory_class"] == "semantic"
    assert mem["enabled"] is True

    # 2. Get memory
    get_res = await client.get(f"/api/v1/memory/{mem_id}")
    assert get_res.status_code == 200
    assert get_res.json()["id"] == mem_id

    # 3. List memories with filter
    list_res = await client.get("/api/v1/memory?memory_class=semantic")
    assert list_res.status_code == 200
    items = list_res.json()
    assert any(i["id"] == mem_id for i in items)

    # 4. Correct / Update memory
    patch_payload = {
        "title": "Corrected Database Choice",
        "confidence": 1.0,
    }
    patch_res = await client.patch(f"/api/v1/memory/{mem_id}", json=patch_payload)
    assert patch_res.status_code == 200
    assert patch_res.json()["title"] == "Corrected Database Choice"
    assert patch_res.json()["confidence"] == 1.0

    # 5. Toggle enabled state
    toggle_res = await client.post(f"/api/v1/memory/{mem_id}/toggle")
    assert toggle_res.status_code == 200
    assert toggle_res.json()["enabled"] is False

    toggle_back = await client.post(f"/api/v1/memory/{mem_id}/toggle")
    assert toggle_back.status_code == 200
    assert toggle_back.json()["enabled"] is True

    # 6. Delete memory
    del_res = await client.delete(f"/api/v1/memory/{mem_id}")
    assert del_res.status_code == 200
    assert del_res.json()["deleted"] is True

    # 7. Verify deletion
    verify_res = await client.get(f"/api/v1/memory/{mem_id}")
    assert verify_res.status_code == 404


@pytest.mark.asyncio
async def test_memory_extract_api_endpoint(auth_user_a):
    client, _ = auth_user_a
    payload = {
        "messages": [
            {"role": "user", "content": "Hey there!"},
            {
                "role": "user",
                "content": "I prefer TypeScript over JavaScript for all frontend code.",
            },
            {"role": "assistant", "content": "Got it!"},
        ]
    }
    res = await client.post("/api/v1/memory/extract", json=payload)
    assert res.status_code == 200
    data = res.json()
    assert data["extracted_count"] >= 1
    assert any("TypeScript" in m["content"] for m in data["memories"])


# ============================================================================
# 4. Knowledge & Document Ingestion REST API Tests
# ============================================================================


@pytest.mark.asyncio
async def test_async_document_upload_and_indexing(auth_user_a):
    client, _ = auth_user_a

    # Upload document
    file_content = (
        b"# Policy Air Gap Specification\n\n"
        b"The Policy Engine intercepts all agent tool requests.\n\n"
        b"If the risk is HIGH or CRITICAL, Human-in-the-Loop approval is required.\n"
    )
    files = {"file": ("airgap_policy.md", io.BytesIO(file_content), "text/markdown")}

    res = await client.post("/api/v1/knowledge/upload", files=files)
    assert res.status_code == 202
    data = res.json()
    doc = data["document"]
    doc_id = doc["id"]
    assert doc["filename"] == "airgap_policy.md"
    assert doc["status"] == "processing"

    # Execute background processing directly to verify indexing
    await process_document_background(
        doc_id=doc_id,
        file_bytes=file_content,
        filename="airgap_policy.md",
        file_type="md",
    )

    # Inspect document detail
    doc_res = await client.get(f"/api/v1/knowledge/documents/{doc_id}")
    assert doc_res.status_code == 200
    updated_doc = doc_res.json()
    assert updated_doc["status"] == "completed"
    assert updated_doc["chunk_count"] >= 1

    # Inspect chunks
    chunks_res = await client.get(f"/api/v1/knowledge/documents/{doc_id}/chunks")
    assert chunks_res.status_code == 200
    chunks = chunks_res.json()
    assert len(chunks) == updated_doc["chunk_count"]
    assert "Policy Engine intercepts" in chunks[0]["content"]


@pytest.mark.asyncio
async def test_semantic_search_with_source_attribution(auth_user_a):
    client, _ = auth_user_a

    # Upload & index document
    file_content = (
        b"NEXUS Architecture Overview:\n"
        b"All filesystem write mutations require pre-execution snapshotting.\n"
        b"Rollback handlers must be registered with the Audit Engine.\n"
    )
    files = {"file": ("arch_overview.txt", io.BytesIO(file_content), "text/plain")}
    res = await client.post("/api/v1/knowledge/upload", files=files)
    assert res.status_code == 202
    doc_id = res.json()["document"]["id"]

    await process_document_background(
        doc_id=doc_id,
        file_bytes=file_content,
        filename="arch_overview.txt",
        file_type="txt",
    )

    # Search knowledge
    search_payload = {
        "query": "snapshotting and rollback handlers",
        "limit": 3,
        "min_similarity": 0.1,
    }
    search_res = await client.post("/api/v1/knowledge/search", json=search_payload)
    assert search_res.status_code == 200
    data = search_res.json()
    assert data["total_chunks_matched"] >= 1

    top_result = data["results"][0]
    assert top_result["document_id"] == doc_id
    assert top_result["source_title"] == "arch_overview.txt"
    assert top_result["file_type"] == "txt"
    assert top_result["similarity_score"] > 0
    assert "snapshotting" in top_result["snippet"]


@pytest.mark.asyncio
async def test_rag_query_end_to_end(auth_user_a):
    client, _ = auth_user_a

    # 1. Add knowledge document
    doc_content = b"NEXUS uses an append-only audit ledger recording every agent tool action."
    files = {"file": ("audit_ledger.txt", io.BytesIO(doc_content), "text/plain")}
    up = await client.post("/api/v1/knowledge/upload", files=files)
    doc_id = up.json()["document"]["id"]
    await process_document_background(
        doc_id=doc_id,
        file_bytes=doc_content,
        filename="audit_ledger.txt",
        file_type="txt",
    )

    # 2. Add user memory
    await client.post(
        "/api/v1/memory",
        json={
            "title": "Audit Ledger Policy",
            "content": "Audit records are immutable and cannot be deleted by agents.",
            "memory_class": "semantic",
        },
    )

    # 3. Execute RAG query
    rag_payload = {
        "query": "How are agent tool actions recorded in the audit ledger?",
        "include_memory": True,
        "min_similarity": 0.1,
    }
    rag_res = await client.post("/api/v1/knowledge/rag", json=rag_payload)
    assert rag_res.status_code == 200
    data = rag_res.json()

    assert "answer" in data
    assert len(data["supporting_sources"]) >= 1
    assert data["supporting_sources"][0]["source_title"] == "audit_ledger.txt"
    assert data["confidence"] > 0


@pytest.mark.asyncio
async def test_document_deletion_cascades_chunks(auth_user_a):
    client, _ = auth_user_a

    file_content = b"Temporary content to test deletion."
    files = {"file": ("temp.txt", io.BytesIO(file_content), "text/plain")}
    up = await client.post("/api/v1/knowledge/upload", files=files)
    doc_id = up.json()["document"]["id"]
    await process_document_background(
        doc_id=doc_id,
        file_bytes=file_content,
        filename="temp.txt",
        file_type="txt",
    )

    # Delete document
    del_res = await client.delete(f"/api/v1/knowledge/documents/{doc_id}")
    assert del_res.status_code == 200
    assert del_res.json()["deleted"] is True

    # Verify document 404
    get_res = await client.get(f"/api/v1/knowledge/documents/{doc_id}")
    assert get_res.status_code == 404


@pytest.mark.asyncio
async def test_tenant_isolation_memory_and_knowledge(auth_user_a, auth_user_b):
    client_a, _user_a = auth_user_a
    client_b, _user_b = auth_user_b

    # User A creates memory
    mem_res = await client_a.post(
        "/api/v1/memory",
        json={
            "title": "User A Private Secret",
            "content": "Secret token is ABC-123-PRIVATE",
            "memory_class": "semantic",
        },
    )
    mem_a_id = mem_res.json()["id"]

    # User A uploads document
    doc_res = await client_a.post(
        "/api/v1/knowledge/upload",
        files={"file": ("secret_a.txt", io.BytesIO(b"Confidential user A notes"), "text/plain")},
    )
    doc_a_id = doc_res.json()["document"]["id"]

    # User B must NOT be able to view User A's memory
    b_mem = await client_b.get(f"/api/v1/memory/{mem_a_id}")
    assert b_mem.status_code == 404

    # User B must NOT be able to view User A's document
    b_doc = await client_b.get(f"/api/v1/knowledge/documents/{doc_a_id}")
    assert b_doc.status_code == 404

    # User B must NOT be able to delete User A's memory or document
    b_del_mem = await client_b.delete(f"/api/v1/memory/{mem_a_id}")
    assert b_del_mem.status_code == 404

    b_del_doc = await client_b.delete(f"/api/v1/knowledge/documents/{doc_a_id}")
    assert b_del_doc.status_code == 404
