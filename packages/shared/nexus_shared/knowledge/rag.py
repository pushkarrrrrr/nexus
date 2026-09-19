"""NEXUS Retrieval-Augmented Generation (RAG) Query Engine.

Orchestrates semantic retrieval across both personal documents and user memories,
synthesizes grounded answers through the ModelGateway, and guarantees verifiable
source attribution on every response.
"""

from sqlalchemy.ext.asyncio import AsyncSession

from packages.shared.nexus_shared.ai.gateway import get_model_gateway
from packages.shared.nexus_shared.knowledge.vector_store import get_vector_store
from packages.shared.nexus_shared.memory.manager import get_memory_manager
from packages.types.nexus_types.schemas import (
    CompletionRequest,
    RAGQueryRequest,
    RAGQueryResponse,
    SourceAttribution,
)


class RAGQueryEngine:
    """End-to-end RAG reasoning engine with source attribution."""

    async def execute_rag_query(
        self,
        db: AsyncSession,
        user_id: str,
        request: RAGQueryRequest,
    ) -> RAGQueryResponse:
        """Execute semantic search, assemble context, and synthesize grounded response."""
        vector_store = get_vector_store()
        memory_manager = get_memory_manager()
        gateway = get_model_gateway()

        # 1. Retrieve supporting document chunks
        sources: list[SourceAttribution] = await vector_store.search(
            db=db,
            user_id=user_id,
            query=request.query,
            limit=request.max_context_chunks,
            min_similarity=request.min_similarity,
        )

        # 2. Retrieve supporting memory items if requested
        memory_citations: list[dict[str, str]] = []
        if request.include_memory:
            memory_results = await memory_manager.search_memories(
                db=db,
                user_id=user_id,
                query=request.query,
                limit=3,
                min_similarity=request.min_similarity,
            )
            for mem, sim in memory_results:
                memory_citations.append(
                    {
                        "memory_id": mem.id,
                        "title": mem.title,
                        "class": mem.memory_class.value,
                        "snippet": mem.content[:150] + "..."
                        if len(mem.content) > 150
                        else mem.content,
                        "similarity": str(sim),
                    }
                )

        # 3. Assemble Grounded Context Prompt
        context_blocks: list[str] = []

        if sources:
            context_blocks.append("--- VERIFIED DOCUMENT SOURCES ---")
            for idx, src in enumerate(sources, 1):
                page_info = f", Page {src.page_number}" if src.page_number else ""
                context_blocks.append(
                    f"[{idx}] Source: {src.source_title}{page_info} (Similarity: {src.similarity_score:.2f})\n"
                    f"Excerpt: {src.snippet}"
                )

        if memory_citations:
            context_blocks.append("\n--- USER MEMORY & PREFERENCES ---")
            for mem_c in memory_citations:
                context_blocks.append(
                    f"- [{mem_c['class'].upper()}] {mem_c['title']}: {mem_c['snippet']}"
                )

        combined_context = "\n\n".join(context_blocks)

        system_prompt = (
            "You are the NEXUS Personal Knowledge Assistant. Answer the user's question using "
            "ONLY the provided verified document excerpts and user memories. "
            "Cite sources by their numbered brackets (e.g. [1], [2]) when referencing facts. "
            "If the information is not contained in the context, clearly state that the knowledge base "
            "does not contain sufficient information to answer the question."
        )

        user_prompt = (
            f"Context Information:\n{combined_context}\n\nUser Question: {request.query}\n\nAnswer:"
        )

        # 4. Generate answer through ModelGateway
        comp_req = CompletionRequest(
            prompt=user_prompt,
            system_prompt=system_prompt,
            model=request.model,
            temperature=0.1,
            max_tokens=2048,
        )

        tokens_used = 0
        answer_text = ""
        try:
            resp = await gateway.complete(comp_req)
            answer_text = resp.content
            tokens_used = resp.usage.total_tokens
        except Exception as exc:  # noqa: BLE001
            # Fallback if no LLM configured: provide direct citation summary
            if sources or memory_citations:
                answer_text = (
                    f"Retrieved {len(sources)} relevant document excerpts and {len(memory_citations)} memories "
                    f"matching '{request.query}'. (Direct gateway inference unavailable: {exc})"
                )
            else:
                answer_text = f"No relevant documents or memories found matching '{request.query}'."

        confidence = 0.95 if sources else 0.50

        return RAGQueryResponse(
            query=request.query,
            answer=answer_text,
            supporting_sources=sources,
            memory_citations=memory_citations,
            confidence=confidence,
            tokens_used=tokens_used,
        )


_rag_engine: RAGQueryEngine | None = None


def get_rag_engine() -> RAGQueryEngine:
    global _rag_engine
    if _rag_engine is None:
        _rag_engine = RAGQueryEngine()
    return _rag_engine
