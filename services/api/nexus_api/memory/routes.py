"""NEXUS Memory REST API Routes.

Exposes endpoints for:
- Memory creation, retrieval, and 5-class categorization.
- Provenance inspection and confidence scoring.
- Correction/editing of stored memory items.
- Lifecycle control (toggling enable/disable, permanent deletion).
- Intelligent extraction from dialogue turns with noise filtering.
"""

from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from packages.shared.nexus_shared.memory.extractor import MemoryExtractor
from packages.shared.nexus_shared.memory.manager import get_memory_manager
from packages.shared.nexus_shared.models import UserModel
from packages.types.nexus_types.schemas import (
    MemoryClass,
    MemoryCreate,
    MemoryExtractRequest,
    MemoryExtractResponse,
    MemoryItem,
    MemoryUpdate,
)
from services.api.nexus_api.auth.dependencies import get_current_user
from services.api.nexus_api.database import get_db

memory_router = APIRouter(prefix="/memory", tags=["memory"])


@memory_router.get("", response_model=list[MemoryItem])
async def list_memories(
    memory_class: MemoryClass | None = Query(None, description="Filter by memory class"),
    query: str | None = Query(None, description="Search text in memory title or content"),
    enabled_only: bool = Query(False, description="Filter for only enabled memories"),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    db: AsyncSession = Depends(get_db),
    current_user: UserModel = Depends(get_current_user),
) -> list[MemoryItem]:
    """List memories belonging to current authenticated user with filtering."""
    manager = get_memory_manager()
    return await manager.list_memories(
        db=db,
        user_id=current_user.id,
        memory_class=memory_class,
        query=query,
        enabled_only=enabled_only,
        limit=limit,
        offset=offset,
    )


@memory_router.post("", response_model=MemoryItem, status_code=status.HTTP_201_CREATED)
async def create_memory(
    data: MemoryCreate,
    db: AsyncSession = Depends(get_db),
    current_user: UserModel = Depends(get_current_user),
) -> MemoryItem:
    """Create a new memory item and compute its semantic embedding."""
    manager = get_memory_manager()
    return await manager.create_memory(
        db=db,
        user_id=current_user.id,
        data=data,
    )


@memory_router.get("/{memory_id}", response_model=MemoryItem)
async def get_memory(
    memory_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: UserModel = Depends(get_current_user),
) -> MemoryItem:
    """Retrieve a specific memory item by ID."""
    manager = get_memory_manager()
    item = await manager.get_memory(db=db, user_id=current_user.id, memory_id=memory_id)
    if not item:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Memory '{memory_id}' not found",
        )
    return item


@memory_router.patch("/{memory_id}", response_model=MemoryItem)
async def update_memory(
    memory_id: str,
    data: MemoryUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: UserModel = Depends(get_current_user),
) -> MemoryItem:
    """Correct or update memory title, content, class, or status."""
    manager = get_memory_manager()
    updated = await manager.update_memory(
        db=db,
        user_id=current_user.id,
        memory_id=memory_id,
        data=data,
    )
    if not updated:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Memory '{memory_id}' not found",
        )
    return updated


@memory_router.delete("/{memory_id}", status_code=status.HTTP_200_OK)
async def delete_memory(
    memory_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: UserModel = Depends(get_current_user),
) -> dict[str, Any]:
    """Permanently delete a memory item."""
    manager = get_memory_manager()
    success = await manager.delete_memory(db=db, user_id=current_user.id, memory_id=memory_id)
    if not success:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Memory '{memory_id}' not found",
        )
    return {"deleted": True, "id": memory_id}


@memory_router.post("/{memory_id}/toggle", response_model=MemoryItem)
async def toggle_memory(
    memory_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: UserModel = Depends(get_current_user),
) -> MemoryItem:
    """Toggle a memory item's active/enabled state."""
    manager = get_memory_manager()
    item = await manager.toggle_memory(db=db, user_id=current_user.id, memory_id=memory_id)
    if not item:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Memory '{memory_id}' not found",
        )
    return item


@memory_router.post("/extract", response_model=MemoryExtractResponse)
async def extract_memories(
    request: MemoryExtractRequest,
    db: AsyncSession = Depends(get_db),
    current_user: UserModel = Depends(get_current_user),
) -> MemoryExtractResponse:
    """Intelligently extract and persist durable memories from conversation turns."""
    extractor = MemoryExtractor()
    manager = get_memory_manager()

    candidates = extractor.extract_from_turns(
        messages=request.messages,
        session_id=request.session_id,
    )

    created_memories: list[MemoryItem] = []
    for cand in candidates:
        mem = await manager.create_memory(db=db, user_id=current_user.id, data=cand)
        created_memories.append(mem)

    return MemoryExtractResponse(
        extracted_count=len(created_memories),
        memories=created_memories,
    )
