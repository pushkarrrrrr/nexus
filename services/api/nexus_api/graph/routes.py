"""REST API routes for Phase 7: Knowledge Graph and Relational Traversal."""

from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from packages.shared.nexus_shared.graph.engine import get_graph_engine
from packages.shared.nexus_shared.graph.extractor import get_relation_extractor
from packages.shared.nexus_shared.models import DocumentModel, UserModel
from packages.types.nexus_types.schemas import (
    GraphNeighborhood,
    GraphOverview,
    GraphShortestPath,
    KnowledgeEdgeCreate,
    KnowledgeEdgeItem,
    KnowledgeNodeCreate,
    KnowledgeNodeItem,
    KnowledgeNodeUpdate,
)
from services.api.nexus_api.auth.dependencies import get_current_user
from services.api.nexus_api.database import get_db

graph_router = APIRouter(prefix="/graph", tags=["graph"])


@graph_router.get("/overview", response_model=GraphOverview)
async def get_graph_overview(
    db: AsyncSession = Depends(get_db),
    current_user: UserModel = Depends(get_current_user),
) -> GraphOverview:
    """Get aggregated statistics on the user's knowledge graph."""
    engine = get_graph_engine()
    return await engine.get_overview(db, current_user.id)


@graph_router.get("/nodes", response_model=list[KnowledgeNodeItem])
async def list_nodes(
    node_type: str | None = Query(None, description="Filter by node type"),
    search: str | None = Query(None, description="Search node labels"),
    limit: int = Query(100, ge=1, le=500),
    offset: int = Query(0, ge=0),
    db: AsyncSession = Depends(get_db),
    current_user: UserModel = Depends(get_current_user),
) -> list[KnowledgeNodeItem]:
    """List entity nodes with optional type and search filtering."""
    engine = get_graph_engine()
    return await engine.list_nodes(
        db=db,
        user_id=current_user.id,
        node_type=node_type,
        search=search,
        limit=limit,
        offset=offset,
    )


@graph_router.post("/nodes", response_model=KnowledgeNodeItem, status_code=status.HTTP_201_CREATED)
async def create_node(
    request: KnowledgeNodeCreate,
    db: AsyncSession = Depends(get_db),
    current_user: UserModel = Depends(get_current_user),
) -> KnowledgeNodeItem:
    """Create a new knowledge entity node."""
    engine = get_graph_engine()
    return await engine.create_node(db=db, user_id=current_user.id, request=request)


@graph_router.get("/nodes/{node_id}")
async def get_node_detail(
    node_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: UserModel = Depends(get_current_user),
) -> dict[str, Any]:
    """Fetch node details and its immediate incident edges."""
    engine = get_graph_engine()
    node = await engine.get_node(db=db, user_id=current_user.id, node_id=node_id)
    if not node:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Node '{node_id}' not found",
        )

    edges = await engine.list_edges(
        db=db,
        user_id=current_user.id,
        source_node_id=node_id,
        limit=100,
    )
    incoming_edges = await engine.list_edges(
        db=db,
        user_id=current_user.id,
        target_node_id=node_id,
        limit=100,
    )

    return {
        "node": node,
        "outgoing_edges": edges,
        "incoming_edges": incoming_edges,
    }


@graph_router.put("/nodes/{node_id}", response_model=KnowledgeNodeItem)
async def update_node(
    node_id: str,
    update: KnowledgeNodeUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: UserModel = Depends(get_current_user),
) -> KnowledgeNodeItem:
    """Update an existing node's label, type, or properties."""
    engine = get_graph_engine()
    updated = await engine.update_node(
        db=db,
        user_id=current_user.id,
        node_id=node_id,
        update=update,
    )
    if not updated:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Node '{node_id}' not found",
        )
    return updated


@graph_router.delete("/nodes/{node_id}")
async def delete_node(
    node_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: UserModel = Depends(get_current_user),
) -> dict[str, Any]:
    """Delete a node and cascade remove its incident edges."""
    engine = get_graph_engine()
    deleted = await engine.delete_node(db=db, user_id=current_user.id, node_id=node_id)
    if not deleted:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Node '{node_id}' not found",
        )
    return {"deleted": True, "id": node_id}


@graph_router.get("/edges", response_model=list[KnowledgeEdgeItem])
async def list_edges(
    source_node_id: str | None = Query(None),
    target_node_id: str | None = Query(None),
    relation_type: str | None = Query(None),
    limit: int = Query(200, ge=1, le=1000),
    offset: int = Query(0, ge=0),
    db: AsyncSession = Depends(get_db),
    current_user: UserModel = Depends(get_current_user),
) -> list[KnowledgeEdgeItem]:
    """List edges matching query filters."""
    engine = get_graph_engine()
    return await engine.list_edges(
        db=db,
        user_id=current_user.id,
        source_node_id=source_node_id,
        target_node_id=target_node_id,
        relation_type=relation_type,
        limit=limit,
        offset=offset,
    )


@graph_router.post("/edges", response_model=KnowledgeEdgeItem, status_code=status.HTTP_201_CREATED)
async def create_edge(
    request: KnowledgeEdgeCreate,
    db: AsyncSession = Depends(get_db),
    current_user: UserModel = Depends(get_current_user),
) -> KnowledgeEdgeItem:
    """Create a typed directed edge between two entity nodes."""
    engine = get_graph_engine()
    try:
        return await engine.create_edge(db=db, user_id=current_user.id, request=request)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        ) from exc


@graph_router.delete("/edges/{edge_id}")
async def delete_edge(
    edge_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: UserModel = Depends(get_current_user),
) -> dict[str, Any]:
    """Remove a directed edge."""
    engine = get_graph_engine()
    deleted = await engine.delete_edge(db=db, user_id=current_user.id, edge_id=edge_id)
    if not deleted:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Edge '{edge_id}' not found",
        )
    return {"deleted": True, "id": edge_id}


@graph_router.get("/neighborhood/{node_id}", response_model=GraphNeighborhood)
async def get_neighborhood(
    node_id: str,
    depth: int = Query(2, ge=1, le=3, description="Neighborhood depth (1-3 hops)"),
    direction: str = Query("all", pattern="^(all|outgoing|incoming)$"),
    db: AsyncSession = Depends(get_db),
    current_user: UserModel = Depends(get_current_user),
) -> GraphNeighborhood:
    """Traverse and extract the k-hop neighborhood subgraph using cycle-safe recursive CTE."""
    engine = get_graph_engine()
    try:
        return await engine.get_neighborhood(
            db=db,
            user_id=current_user.id,
            node_id=node_id,
            depth=depth,
            direction=direction,
        )
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        ) from exc


@graph_router.get("/shortest-path", response_model=GraphShortestPath)
async def get_shortest_path(
    source_node_id: str = Query(..., description="Source node ID"),
    target_node_id: str = Query(..., description="Target node ID"),
    max_depth: int = Query(5, ge=1, le=6),
    db: AsyncSession = Depends(get_db),
    current_user: UserModel = Depends(get_current_user),
) -> GraphShortestPath:
    """Compute the shortest directed path between two entities."""
    engine = get_graph_engine()
    return await engine.find_shortest_path(
        db=db,
        user_id=current_user.id,
        source_node_id=source_node_id,
        target_node_id=target_node_id,
        max_depth=max_depth,
    )


@graph_router.post("/extract/document/{doc_id}")
async def extract_document_relations(
    doc_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: UserModel = Depends(get_current_user),
) -> dict[str, Any]:
    """Trigger automated relation extraction for an ingested document."""
    extractor = get_relation_extractor()
    doc = await db.get(DocumentModel, doc_id)
    if not doc or doc.user_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Document '{doc_id}' not found",
        )

    # Combine chunk contents
    content = doc.doc_metadata.get("text_preview", "")
    if not content:
        # fetch from chunks
        from sqlalchemy import select

        from packages.shared.nexus_shared.models import DocumentChunkModel

        chunks = (
            await db.scalars(
                select(DocumentChunkModel).where(DocumentChunkModel.document_id == doc_id)
            )
        ).all()
        content = "\n".join(c.content for c in chunks)

    edge_ids = await extractor.extract_from_document(
        db=db,
        user_id=current_user.id,
        document_id=doc.id,
        filename=doc.filename,
        content=content,
    )
    return {
        "status": "extracted",
        "document_id": doc_id,
        "relations_created_count": len(edge_ids),
        "edge_ids": edge_ids,
    }
