"""DocumentAgent specializing in document analysis, section inspection, and insight extraction."""

from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from packages.shared.nexus_shared.agents.base import AgentStepResult, BaseAgent
from packages.shared.nexus_shared.models import DocumentChunkModel, DocumentModel
from packages.types.nexus_types.schemas import AgentType, PlanStep


class DocumentAgent(BaseAgent):
    """Specialized agent for analyzing and extracting structured insights from indexed documents."""

    def __init__(self) -> None:
        super().__init__(
            agent_type=AgentType.DOCUMENT,
            name="Document Agent",
            description="Analyzes uploaded documents, parses structural sections, and extracts structured metadata.",
            allowed_tools=["document_reader", "chunk_analyzer", "metadata_extractor"],
            assigned_model="gpt-4o",
        )

    async def run(
        self,
        step: PlanStep,
        context: dict[str, Any],
        user_id: str,
        db: AsyncSession,
    ) -> AgentStepResult:
        """Inspect documents matching the query context."""
        doc_id = context.get("document_id")

        if doc_id:
            query = await db.execute(
                select(DocumentModel).where(
                    DocumentModel.id == doc_id,
                    DocumentModel.user_id == user_id,
                )
            )
            doc = query.scalar_one_or_none()
            if not doc:
                return AgentStepResult(
                    success=False,
                    error_message=f"Document '{doc_id}' not found for user",
                )

            # Retrieve top chunks
            chunks_query = await db.execute(
                select(DocumentChunkModel)
                .where(DocumentChunkModel.document_id == doc.id)
                .order_by(DocumentChunkModel.chunk_index.asc())
                .limit(5)
            )
            chunks = list(chunks_query.scalars().all())

            return AgentStepResult(
                success=True,
                result_payload={
                    "document_id": doc.id,
                    "filename": doc.filename,
                    "file_type": doc.file_type,
                    "chunk_count": doc.chunk_count,
                    "preview_chunks": [
                        {"index": c.chunk_index, "content": c.content[:150]} for c in chunks
                    ],
                },
            )

        # General document inventory lookup
        all_docs_query = await db.execute(
            select(DocumentModel)
            .where(DocumentModel.user_id == user_id)
            .order_by(DocumentModel.created_at.desc())
            .limit(10)
        )
        docs = list(all_docs_query.scalars().all())

        return AgentStepResult(
            success=True,
            result_payload={
                "documents_found": len(docs),
                "documents": [
                    {
                        "id": d.id,
                        "filename": d.filename,
                        "status": d.status,
                        "chunk_count": d.chunk_count,
                    }
                    for d in docs
                ],
            },
        )
