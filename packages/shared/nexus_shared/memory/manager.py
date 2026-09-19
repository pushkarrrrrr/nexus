"""NEXUS Memory Manager & Lifecycle Controller.

Provides unified management across the 5 NEXUS memory classes:
- WORKING: Short-term scratchpad and active task goals.
- CONVERSATIONAL: Dialogue summaries and thread context.
- EPISODIC: Historical task outcomes, agent observations, and tool results.
- SEMANTIC: Factual knowledge, user preferences, and enduring concepts.
- PROCEDURAL: Step-by-step how-to operational workflows.
"""

import math
from typing import Any

from sqlalchemy import delete, desc, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from packages.shared.nexus_shared.ai.gateway import get_model_gateway
from packages.shared.nexus_shared.models import MemoryModel, utcnow
from packages.types.nexus_types.schemas import (
    EmbeddingRequest,
    MemoryClass,
    MemoryCreate,
    MemoryItem,
    MemoryUpdate,
)


def cosine_similarity(v1: list[float], v2: list[float]) -> float:
    """Compute cosine similarity between two vector lists."""
    if not v1 or not v2 or len(v1) != len(v2):
        return 0.0
    dot = sum(a * b for a, b in zip(v1, v2, strict=False))
    norm_a = math.sqrt(sum(a * a for a in v1))
    norm_b = math.sqrt(sum(b * b for b in v2))
    if norm_a == 0.0 or norm_b == 0.0:
        return 0.0
    return dot / (norm_a * norm_b)


class MemoryManager:
    """Manages CRUD, vector indexing, relevance ranking, and lifecycle of memories."""

    async def _compute_embedding(self, text: str) -> list[float] | None:
        """Generate embedding vector using the AI ModelGateway."""
        try:
            gateway = get_model_gateway()
            req = EmbeddingRequest(texts=[text])
            resp = await gateway.embed(req)
            if resp.embeddings and len(resp.embeddings) > 0:
                return resp.embeddings[0]
        except Exception:  # noqa: BLE001, S110
            pass
        return None

    async def create_memory(
        self,
        db: AsyncSession,
        user_id: str,
        data: MemoryCreate,
        embedding: list[float] | None = None,
    ) -> MemoryItem:
        """Create a new memory item and compute its embedding vector."""
        if embedding is None:
            embedding = await self._compute_embedding(f"{data.title}: {data.content}")

        mem = MemoryModel(
            user_id=user_id,
            memory_class=data.memory_class.value,
            title=data.title,
            content=data.content,
            source_session_id=data.source_session_id,
            confidence=data.confidence,
            enabled=data.enabled,
            tags=data.tags,
            embedding=embedding,
            created_at=utcnow(),
            updated_at=utcnow(),
        )
        db.add(mem)
        await db.commit()
        await db.refresh(mem)
        return self._to_schema(mem)

    async def get_memory(
        self,
        db: AsyncSession,
        user_id: str,
        memory_id: str,
    ) -> MemoryItem | None:
        """Retrieve a specific memory belonging to user."""
        stmt = select(MemoryModel).where(
            MemoryModel.id == memory_id,
            MemoryModel.user_id == user_id,
        )
        result = await db.execute(stmt)
        mem = result.scalar_one_or_none()
        return self._to_schema(mem) if mem else None

    async def list_memories(
        self,
        db: AsyncSession,
        user_id: str,
        memory_class: MemoryClass | None = None,
        query: str | None = None,
        enabled_only: bool = False,
        limit: int = 100,
        offset: int = 0,
    ) -> list[MemoryItem]:
        """List user memories with filtering and pagination."""
        stmt = select(MemoryModel).where(MemoryModel.user_id == user_id)

        if memory_class is not None:
            stmt = stmt.where(MemoryModel.memory_class == memory_class.value)
        if enabled_only:
            stmt = stmt.where(MemoryModel.enabled.is_(True))
        if query:
            q_pattern = f"%{query.strip()}%"
            stmt = stmt.where(
                MemoryModel.title.ilike(q_pattern) | MemoryModel.content.ilike(q_pattern)
            )

        stmt = stmt.order_by(desc(MemoryModel.updated_at)).limit(limit).offset(offset)
        result = await db.execute(stmt)
        memories = result.scalars().all()
        return [self._to_schema(m) for m in memories]

    async def update_memory(
        self,
        db: AsyncSession,
        user_id: str,
        memory_id: str,
        data: MemoryUpdate,
    ) -> MemoryItem | None:
        """Update/correct memory item attributes."""
        mem = await db.scalar(
            select(MemoryModel).where(
                MemoryModel.id == memory_id,
                MemoryModel.user_id == user_id,
            )
        )
        if not mem:
            return None

        update_values: dict[str, Any] = {"updated_at": utcnow()}
        recompute_embedding = False

        if data.title is not None:
            update_values["title"] = data.title
            recompute_embedding = True
        if data.content is not None:
            update_values["content"] = data.content
            recompute_embedding = True
        if data.memory_class is not None:
            update_values["memory_class"] = data.memory_class.value
        if data.confidence is not None:
            update_values["confidence"] = data.confidence
        if data.tags is not None:
            update_values["tags"] = data.tags
        if data.enabled is not None:
            update_values["enabled"] = data.enabled

        if recompute_embedding:
            new_title = data.title if data.title is not None else mem.title
            new_content = data.content if data.content is not None else mem.content
            emb = await self._compute_embedding(f"{new_title}: {new_content}")
            if emb is not None:
                update_values["embedding"] = emb

        stmt = (
            update(MemoryModel)
            .where(MemoryModel.id == memory_id, MemoryModel.user_id == user_id)
            .values(**update_values)
        )
        await db.execute(stmt)
        await db.commit()
        await db.refresh(mem)
        return self._to_schema(mem)

    async def delete_memory(
        self,
        db: AsyncSession,
        user_id: str,
        memory_id: str,
    ) -> bool:
        """Permanently delete a memory item."""
        stmt = delete(MemoryModel).where(
            MemoryModel.id == memory_id,
            MemoryModel.user_id == user_id,
        )
        result = await db.execute(stmt)
        await db.commit()
        rowcount = getattr(result, "rowcount", 0) or 0
        return rowcount > 0

    async def toggle_memory(
        self,
        db: AsyncSession,
        user_id: str,
        memory_id: str,
    ) -> MemoryItem | None:
        """Toggle the enabled status of a memory."""
        mem = await db.scalar(
            select(MemoryModel).where(
                MemoryModel.id == memory_id,
                MemoryModel.user_id == user_id,
            )
        )
        if not mem:
            return None

        new_status = not mem.enabled
        mem.enabled = new_status
        mem.updated_at = utcnow()
        await db.commit()
        await db.refresh(mem)
        return self._to_schema(mem)

    async def search_memories(
        self,
        db: AsyncSession,
        user_id: str,
        query: str,
        memory_class: MemoryClass | None = None,
        limit: int = 5,
        min_similarity: float = 0.4,
    ) -> list[tuple[MemoryItem, float]]:
        """Search enabled memories via vector similarity and keyword ranking."""
        query_embedding = await self._compute_embedding(query)

        # Retrieve enabled candidate memories
        stmt = select(MemoryModel).where(
            MemoryModel.user_id == user_id,
            MemoryModel.enabled.is_(True),
        )
        if memory_class is not None:
            stmt = stmt.where(MemoryModel.memory_class == memory_class.value)

        result = await db.execute(stmt)
        candidates = result.scalars().all()

        scored: list[tuple[MemoryItem, float]] = []
        for mem in candidates:
            score = 0.0
            if query_embedding and mem.embedding:
                score = cosine_similarity(query_embedding, mem.embedding)
            else:
                # Lexical heuristic fallback if no vector
                q_words = set(query.lower().split())
                content_words = set((mem.title + " " + mem.content).lower().split())
                overlap = len(q_words.intersection(content_words))
                score = min(1.0, overlap / max(1, len(q_words)))

            if score >= min_similarity:
                scored.append((self._to_schema(mem), round(score, 4)))

        scored.sort(key=lambda x: x[1], reverse=True)
        return scored[:limit]

    def _to_schema(self, mem: MemoryModel) -> MemoryItem:
        return MemoryItem(
            id=mem.id,
            user_id=mem.user_id,
            memory_class=MemoryClass(mem.memory_class),
            title=mem.title,
            content=mem.content,
            source_session_id=mem.source_session_id,
            confidence=mem.confidence,
            enabled=mem.enabled,
            tags=mem.tags or [],
            created_at=mem.created_at,
            updated_at=mem.updated_at,
        )


_memory_manager: MemoryManager | None = None


def get_memory_manager() -> MemoryManager:
    global _memory_manager
    if _memory_manager is None:
        _memory_manager = MemoryManager()
    return _memory_manager
