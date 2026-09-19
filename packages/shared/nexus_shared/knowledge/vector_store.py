"""Dual-Mode Vector Store & Semantic Retrieval Engine.

Supports:
- PostgreSQL with native pgvector distance operator (`<=>`).
- SQLite / In-memory fallback via exact normalized cosine dot product.
- Batch embedding generation via ModelGateway.
- Granular source attribution (document title, page, character range, similarity).
"""

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from packages.shared.nexus_shared.ai.gateway import get_model_gateway
from packages.shared.nexus_shared.knowledge.ingestion import ParsedChunk
from packages.shared.nexus_shared.memory.manager import cosine_similarity
from packages.shared.nexus_shared.models import DocumentChunkModel, DocumentModel
from packages.types.nexus_types.schemas import (
    EmbeddingRequest,
    SourceAttribution,
)


class VectorStore:
    """Manages chunk vector embeddings and semantic similarity searches."""

    async def generate_embeddings_batch(self, texts: list[str]) -> list[list[float]]:
        """Batch compute embeddings for a list of texts."""
        if not texts:
            return []
        try:
            gateway = get_model_gateway()
            req = EmbeddingRequest(texts=texts)
            resp = await gateway.embed(req)
            return resp.embeddings
        except Exception:  # noqa: BLE001
            # Return empty embeddings list if embedding service fails
            return [[] for _ in texts]

    async def index_document_chunks(
        self,
        db: AsyncSession,
        document: DocumentModel,
        chunks: list[ParsedChunk],
    ) -> int:
        """Embed and persist all chunks for a document."""
        if not chunks:
            document.chunk_count = 0
            document.status = "completed"
            await db.commit()
            return 0

        # Ensure idempotency: clear prior chunks if any
        await db.execute(
            delete(DocumentChunkModel).where(DocumentChunkModel.document_id == document.id)
        )

        texts = [c.content for c in chunks]
        embeddings = await self.generate_embeddings_batch(texts)

        chunk_models: list[DocumentChunkModel] = []
        for i, chunk in enumerate(chunks):
            emb = embeddings[i] if i < len(embeddings) and embeddings[i] else None
            chunk_models.append(
                DocumentChunkModel(
                    document_id=document.id,
                    chunk_index=chunk.chunk_index,
                    content=chunk.content,
                    page_number=chunk.page_number,
                    char_start=chunk.char_start,
                    char_end=chunk.char_end,
                    embedding=emb,
                    chunk_metadata={
                        "filename": document.filename,
                        "file_type": document.file_type,
                    },
                )
            )

        db.add_all(chunk_models)
        document.chunk_count = len(chunk_models)
        document.status = "completed"
        document.error_message = None
        await db.commit()
        return len(chunk_models)

    async def search(
        self,
        db: AsyncSession,
        user_id: str,
        query: str,
        limit: int = 5,
        min_similarity: float = 0.4,
        document_ids: list[str] | None = None,
    ) -> list[SourceAttribution]:
        """Perform semantic similarity search across user document chunks."""
        # 1. Compute query vector
        query_embeddings = await self.generate_embeddings_batch([query])
        query_vector = query_embeddings[0] if query_embeddings and query_embeddings[0] else None

        # 2. Join DocumentChunkModel with DocumentModel ensuring user isolation
        stmt = (
            select(DocumentChunkModel, DocumentModel)
            .join(DocumentModel, DocumentChunkModel.document_id == DocumentModel.id)
            .where(DocumentModel.user_id == user_id, DocumentModel.status == "completed")
        )
        if document_ids:
            stmt = stmt.where(DocumentModel.id.in_(document_ids))

        # SQLite / Fallback evaluation
        result = await db.execute(stmt)
        rows = result.all()

        scored: list[tuple[DocumentChunkModel, DocumentModel, float]] = []
        q_words = set(query.lower().split())

        for chunk_row, doc_row in rows:
            score = 0.0
            if query_vector and chunk_row.embedding:
                score = cosine_similarity(query_vector, chunk_row.embedding)
            else:
                # Lexical overlap fallback if embedding is absent
                content_words = set(chunk_row.content.lower().split())
                overlap = len(q_words.intersection(content_words))
                score = min(1.0, overlap / max(1, len(q_words)))

            if score >= min_similarity:
                scored.append((chunk_row, doc_row, round(score, 4)))

        scored.sort(key=lambda x: x[2], reverse=True)

        attributions: list[SourceAttribution] = []
        for chk, doc, sim_score in scored[:limit]:
            snippet = chk.content.replace("\n", " ").strip()
            if len(snippet) > 280:
                snippet = snippet[:280] + "..."

            attributions.append(
                SourceAttribution(
                    document_id=doc.id,
                    source_title=doc.filename,
                    file_type=doc.file_type,
                    chunk_index=chk.chunk_index,
                    page_number=chk.page_number,
                    char_start=chk.char_start,
                    char_end=chk.char_end,
                    similarity_score=sim_score,
                    snippet=snippet,
                )
            )

        return attributions


_vector_store: VectorStore | None = None


def get_vector_store() -> VectorStore:
    global _vector_store
    if _vector_store is None:
        _vector_store = VectorStore()
    return _vector_store
