"""Unit and Integration Tests for Phase 7: Knowledge Graph and Relational Traversal.

Covers:
- Node & Edge CRUD lifecycle with strict tenant isolation.
- Multi-hop recursive CTE neighborhood traversal with cycle prevention.
- Bidirectional neighborhood traversal (all, outgoing, incoming).
- Shortest path graph algorithm via recursive CTE.
- Automated relation extraction for documents and memories.
- Hybrid Graph-RAG query execution with structured relational triples.
- Multi-tenant security boundaries preventing cross-tenant graph access.
"""

import uuid

import pytest
from httpx import ASGITransport, AsyncClient

from packages.shared.nexus_shared.graph.extractor import get_relation_extractor
from services.api.nexus_api.database import init_database
from services.api.nexus_api.main import app


@pytest.fixture(autouse=True)
async def ensure_db():
    await init_database()


def random_email() -> str:
    return f"graph_test_{uuid.uuid4().hex[:8]}@example.com"


@pytest.fixture
async def auth_user_a():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        email = random_email()
        reg = await client.post(
            "/api/v1/auth/register",
            json={
                "email": email,
                "password": "SecretPassword123!",
                "full_name": "Graph User Alpha",
            },
        )
        assert reg.status_code == 201, reg.text
        login = await client.post(
            "/api/v1/auth/login",
            json={"email": email, "password": "SecretPassword123!"},
        )
        assert login.status_code == 200
        token = login.json()["access_token"]
        user_id = reg.json()["user"]["id"]
        yield {
            "client": client,
            "token": token,
            "user_id": user_id,
            "headers": {"Authorization": f"Bearer {token}"},
        }


@pytest.fixture
async def auth_user_b():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        email = random_email()
        reg = await client.post(
            "/api/v1/auth/register",
            json={"email": email, "password": "SecretPassword123!", "full_name": "Graph User Beta"},
        )
        assert reg.status_code == 201
        login = await client.post(
            "/api/v1/auth/login",
            json={"email": email, "password": "SecretPassword123!"},
        )
        assert login.status_code == 200
        token = login.json()["access_token"]
        user_id = reg.json()["user"]["id"]
        yield {
            "client": client,
            "token": token,
            "user_id": user_id,
            "headers": {"Authorization": f"Bearer {token}"},
        }


@pytest.mark.asyncio
async def test_node_and_edge_crud(auth_user_a):
    client: AsyncClient = auth_user_a["client"]
    headers = auth_user_a["headers"]

    # 1. Create nodes
    create_a = await client.post(
        "/api/v1/graph/nodes",
        headers=headers,
        json={"label": "PostgreSQL", "node_type": "technology", "properties": {"version": "16"}},
    )
    assert create_a.status_code == 201
    node_a = create_a.json()
    assert node_a["label"] == "PostgreSQL"
    assert node_a["node_type"] == "technology"

    create_b = await client.post(
        "/api/v1/graph/nodes",
        headers=headers,
        json={"label": "Database Storage", "node_type": "concept"},
    )
    assert create_b.status_code == 201
    node_b = create_b.json()

    # 2. List nodes with filter
    list_res = await client.get("/api/v1/graph/nodes?node_type=technology", headers=headers)
    assert list_res.status_code == 200
    tech_nodes = list_res.json()
    assert any(n["id"] == node_a["id"] for n in tech_nodes)
    assert not any(n["id"] == node_b["id"] for n in tech_nodes)

    # 3. Create directed edge
    edge_res = await client.post(
        "/api/v1/graph/edges",
        headers=headers,
        json={
            "source_node_id": node_a["id"],
            "target_node_id": node_b["id"],
            "relation_type": "uses",
            "weight": 1.5,
        },
    )
    assert edge_res.status_code == 201
    edge = edge_res.json()
    assert edge["source_node_id"] == node_a["id"]
    assert edge["target_node_id"] == node_b["id"]
    assert edge["relation_type"] == "uses"
    assert edge["weight"] == 1.5

    # 4. Get node detail with incident edges
    detail_res = await client.get(f"/api/v1/graph/nodes/{node_a['id']}", headers=headers)
    assert detail_res.status_code == 200
    detail = detail_res.json()
    assert detail["node"]["id"] == node_a["id"]
    assert len(detail["outgoing_edges"]) == 1
    assert detail["outgoing_edges"][0]["id"] == edge["id"]

    # 5. Delete edge
    del_edge = await client.delete(f"/api/v1/graph/edges/{edge['id']}", headers=headers)
    assert del_edge.status_code == 200

    # 6. Delete node
    del_node = await client.delete(f"/api/v1/graph/nodes/{node_a['id']}", headers=headers)
    assert del_node.status_code == 200


@pytest.mark.asyncio
async def test_tenant_isolation(auth_user_a, auth_user_b):
    client_a: AsyncClient = auth_user_a["client"]
    client_b: AsyncClient = auth_user_b["client"]
    headers_a = auth_user_a["headers"]
    headers_b = auth_user_b["headers"]

    # User A creates a node
    create_res = await client_a.post(
        "/api/v1/graph/nodes",
        headers=headers_a,
        json={"label": "Secret Architecture", "node_type": "concept"},
    )
    assert create_res.status_code == 201
    node_a_id = create_res.json()["id"]

    # User B attempts to read node A -> 404
    get_res = await client_b.get(f"/api/v1/graph/nodes/{node_a_id}", headers=headers_b)
    assert get_res.status_code == 404

    # User B attempts to delete node A -> 404
    del_res = await client_b.delete(f"/api/v1/graph/nodes/{node_a_id}", headers=headers_b)
    assert del_res.status_code == 404

    # User B attempts to connect edge to node A -> 400
    create_b_node = await client_b.post(
        "/api/v1/graph/nodes",
        headers=headers_b,
        json={"label": "User B Concept", "node_type": "concept"},
    )
    node_b_id = create_b_node.json()["id"]

    cross_edge = await client_b.post(
        "/api/v1/graph/edges",
        headers=headers_b,
        json={
            "source_node_id": node_b_id,
            "target_node_id": node_a_id,
            "relation_type": "references",
        },
    )
    assert cross_edge.status_code == 400


@pytest.mark.asyncio
async def test_recursive_cte_neighborhood_with_cycles(auth_user_a):
    client: AsyncClient = auth_user_a["client"]
    headers = auth_user_a["headers"]

    # Build cyclic graph: N1 -> N2 -> N3 -> N1 (cycle!) plus N3 -> N4
    n1_res = await client.post(
        "/api/v1/graph/nodes", headers=headers, json={"label": "Node 1", "node_type": "concept"}
    )
    n2_res = await client.post(
        "/api/v1/graph/nodes", headers=headers, json={"label": "Node 2", "node_type": "concept"}
    )
    n3_res = await client.post(
        "/api/v1/graph/nodes", headers=headers, json={"label": "Node 3", "node_type": "concept"}
    )
    n4_res = await client.post(
        "/api/v1/graph/nodes", headers=headers, json={"label": "Node 4", "node_type": "concept"}
    )

    n1 = n1_res.json()["id"]
    n2 = n2_res.json()["id"]
    n3 = n3_res.json()["id"]
    n4 = n4_res.json()["id"]

    # Edges
    await client.post(
        "/api/v1/graph/edges",
        headers=headers,
        json={"source_node_id": n1, "target_node_id": n2, "relation_type": "uses"},
    )
    await client.post(
        "/api/v1/graph/edges",
        headers=headers,
        json={"source_node_id": n2, "target_node_id": n3, "relation_type": "depends_on"},
    )
    await client.post(
        "/api/v1/graph/edges",
        headers=headers,
        json={"source_node_id": n3, "target_node_id": n1, "relation_type": "references"},  # cycle
    )
    await client.post(
        "/api/v1/graph/edges",
        headers=headers,
        json={"source_node_id": n3, "target_node_id": n4, "relation_type": "contains"},
    )

    # Neighborhood traversal up to 3 hops (must terminate cleanly without infinite recursion)
    neigh_res = await client.get(
        f"/api/v1/graph/neighborhood/{n1}?depth=3&direction=all", headers=headers
    )
    assert neigh_res.status_code == 200
    neighborhood = neigh_res.json()
    assert neighborhood["center_node_id"] == n1
    assert neighborhood["depth"] == 3

    discovered_node_ids = {n["id"] for n in neighborhood["nodes"]}
    assert n1 in discovered_node_ids
    assert n2 in discovered_node_ids
    assert n3 in discovered_node_ids
    assert n4 in discovered_node_ids
    assert len(neighborhood["edges"]) >= 3


@pytest.mark.asyncio
async def test_bidirectional_traversal(auth_user_a):
    client: AsyncClient = auth_user_a["client"]
    headers = auth_user_a["headers"]

    # Incoming edge: Target <- Source
    center_res = await client.post(
        "/api/v1/graph/nodes",
        headers=headers,
        json={"label": "Target Center", "node_type": "concept"},
    )
    source_res = await client.post(
        "/api/v1/graph/nodes",
        headers=headers,
        json={"label": "Incoming Source", "node_type": "document"},
    )
    center_id = center_res.json()["id"]
    source_id = source_res.json()["id"]

    await client.post(
        "/api/v1/graph/edges",
        headers=headers,
        json={
            "source_node_id": source_id,
            "target_node_id": center_id,
            "relation_type": "contains",
        },
    )

    # 1. Outgoing only: should not find source_id
    out_res = await client.get(
        f"/api/v1/graph/neighborhood/{center_id}?depth=1&direction=outgoing", headers=headers
    )
    assert out_res.status_code == 200
    out_nodes = {n["id"] for n in out_res.json()["nodes"]}
    assert source_id not in out_nodes

    # 2. Bidirectional "all": should find source_id via incoming edge
    all_res = await client.get(
        f"/api/v1/graph/neighborhood/{center_id}?depth=1&direction=all", headers=headers
    )
    assert all_res.status_code == 200
    all_nodes = {n["id"] for n in all_res.json()["nodes"]}
    assert source_id in all_nodes


@pytest.mark.asyncio
async def test_shortest_path(auth_user_a):
    client: AsyncClient = auth_user_a["client"]
    headers = auth_user_a["headers"]

    # Line graph: A -> B -> C
    a_id = (
        await client.post("/api/v1/graph/nodes", headers=headers, json={"label": "Start A"})
    ).json()["id"]
    b_id = (
        await client.post("/api/v1/graph/nodes", headers=headers, json={"label": "Hop B"})
    ).json()["id"]
    c_id = (
        await client.post("/api/v1/graph/nodes", headers=headers, json={"label": "End C"})
    ).json()["id"]

    await client.post(
        "/api/v1/graph/edges",
        headers=headers,
        json={
            "source_node_id": a_id,
            "target_node_id": b_id,
            "relation_type": "uses",
            "weight": 2.0,
        },
    )
    await client.post(
        "/api/v1/graph/edges",
        headers=headers,
        json={
            "source_node_id": b_id,
            "target_node_id": c_id,
            "relation_type": "uses",
            "weight": 3.0,
        },
    )

    # Find path A -> C
    path_res = await client.get(
        f"/api/v1/graph/shortest-path?source_node_id={a_id}&target_node_id={c_id}", headers=headers
    )
    assert path_res.status_code == 200
    data = path_res.json()
    assert data["found"] is True
    assert data["length"] == 2
    assert data["total_weight"] == 5.0
    assert len(data["nodes"]) == 3
    assert data["nodes"][0]["id"] == a_id
    assert data["nodes"][1]["id"] == b_id
    assert data["nodes"][2]["id"] == c_id


@pytest.mark.asyncio
async def test_relation_extractor(auth_user_a):
    user_id = auth_user_a["user_id"]
    from services.api.nexus_api.database import get_session_factory

    extractor = get_relation_extractor()
    session_factory = get_session_factory()
    async with session_factory() as db:
        # Document extraction with technologies and headers
        doc_content = """# Architecture Overview
NEXUS uses FastAPI and PostgreSQL with pgvector for semantic retrieval.
# Authentication
Secured with Docker and JWT tokens.
"""
        edge_ids = await extractor.extract_from_document(
            db=db,
            user_id=user_id,
            document_id="doc_sample_1",
            filename="architecture.md",
            content=doc_content,
        )
        assert len(edge_ids) >= 2


@pytest.mark.asyncio
async def test_hybrid_rag_with_graph_triples(auth_user_a):
    client: AsyncClient = auth_user_a["client"]
    headers = auth_user_a["headers"]

    # 1. Create a node and relation for NEXUS Engine
    engine_node = (
        await client.post(
            "/api/v1/graph/nodes",
            headers=headers,
            json={"label": "NexusEngine", "node_type": "technology"},
        )
    ).json()

    policy_node = (
        await client.post(
            "/api/v1/graph/nodes",
            headers=headers,
            json={"label": "PolicyEngine", "node_type": "concept"},
        )
    ).json()

    await client.post(
        "/api/v1/graph/edges",
        headers=headers,
        json={
            "source_node_id": engine_node["id"],
            "target_node_id": policy_node["id"],
            "relation_type": "enforces",
        },
    )

    # 2. Run RAG query referencing NexusEngine
    rag_res = await client.post(
        "/api/v1/knowledge/rag",
        headers=headers,
        json={
            "query": "How does NexusEngine connect with PolicyEngine?",
            "include_graph": True,
            "include_memory": False,
        },
    )
    assert rag_res.status_code == 200
    rag_data = rag_res.json()
    assert "graph_triples" in rag_data
    # Verify graph triples enriched context
    triples = rag_data["graph_triples"]
    assert any(t["subject"] == "NexusEngine" and t["object"] == "PolicyEngine" for t in triples)
