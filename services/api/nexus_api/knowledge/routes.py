"""NEXUS Personal Knowledge & RAG REST API Routes.

Exposes endpoints for:
- Asynchronous multi-format document ingestion (PDF, Markdown, TXT, CSV, JSON).
- Document catalog inspection and deletion.
- Semantic vector similarity search with granular source attribution.
- End-to-end Retrieval-Augmented Generation (RAG) with verified citations.
"""

import hashlib
from typing import Any

from fastapi import (
    APIRouter,
    BackgroundTasks,
    Depends,
    File,
    HTTPException,
    Query,
    UploadFile,
    status,
)
from sqlalchemy import delete, desc, select
from sqlalchemy.ext.asyncio import AsyncSession

from packages.shared.nexus_shared.knowledge.ingestion import DocumentIngestor
from packages.shared.nexus_shared.knowledge.rag import get_rag_engine
from packages.shared.nexus_shared.knowledge.vector_store import get_vector_store
from packages.shared.nexus_shared.models import (
    DocumentChunkModel,
    DocumentModel,
    UserModel,
    utcnow,
)
from packages.types.nexus_types.schemas import (
    DocumentChunkItem,
    DocumentItem,
    DocumentStatus,
    DocumentUploadResponse,
    KnowledgeSearchRequest,
    KnowledgeSearchResponse,
    RAGQueryRequest,
    RAGQueryResponse,
)
from services.api.nexus_api.auth.dependencies import get_current_user
from services.api.nexus_api.database import get_db, get_session_factory

knowledge_router = APIRouter(prefix="/knowledge", tags=["knowledge"])


async def process_document_background(
    doc_id: str,
    file_bytes: bytes,
    filename: str,
    file_type: str,
) -> None:
    """Asynchronously chunk, embed, and index an uploaded document in the background."""
    session_factory = get_session_factory()
    async with session_factory() as session:
        try:
            doc = await session.get(DocumentModel, doc_id)
            if not doc:
                return

            ingestor = DocumentIngestor()
            chunks = ingestor.extract_and_chunk(
                file_bytes=file_bytes,
                filename=filename,
                file_type=file_type,
            )

            vector_store = get_vector_store()
            await vector_store.index_document_chunks(
                db=session,
                document=doc,
                chunks=chunks,
            )

        except Exception as exc:  # noqa: BLE001
            doc = await session.get(DocumentModel, doc_id)
            if doc:
                doc.status = "failed"
                doc.error_message = str(exc)
                doc.updated_at = utcnow()
                await session.commit()


@knowledge_router.post(
    "/upload",
    response_model=DocumentUploadResponse,
    status_code=status.HTTP_202_ACCEPTED,
)
async def upload_document(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    db: AsyncSession = Depends(get_db),
    current_user: UserModel = Depends(get_current_user),
) -> DocumentUploadResponse:
    """Upload a document for asynchronous parsing, chunking, and embedding indexing."""
    filename = file.filename or "uploaded_doc"
    file_bytes = await file.read()

    if not file_bytes:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Uploaded file is empty",
        )

    # Determine file type
    file_type = "txt"
    if "." in filename:
        file_type = filename.rsplit(".", 1)[1].lower()

    allowed_types = {"pdf", "txt", "text", "md", "markdown", "csv", "json", "log"}
    if file_type not in allowed_types:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Unsupported file type '{file_type}'. Supported: {sorted(allowed_types)}",
        )

    sha256 = hashlib.sha256(file_bytes).hexdigest()

    # Create document in processing state
    doc = DocumentModel(
        user_id=current_user.id,
        filename=filename,
        file_type=file_type,
        file_size_bytes=len(file_bytes),
        sha256=sha256,
        chunk_count=0,
        status="processing",
        doc_metadata={"original_name": filename, "content_type": file.content_type or ""},
        created_at=utcnow(),
        updated_at=utcnow(),
    )
    db.add(doc)
    await db.commit()
    await db.refresh(doc)

    # Queue async processing task
    background_tasks.add_task(
        process_document_background,
        doc_id=doc.id,
        file_bytes=file_bytes,
        filename=filename,
        file_type=file_type,
    )

    return DocumentUploadResponse(
        document=_doc_to_schema(doc),
        message="Document accepted for background indexing",
    )


@knowledge_router.get("/documents", response_model=list[DocumentItem])
async def list_documents(
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    db: AsyncSession = Depends(get_db),
    current_user: UserModel = Depends(get_current_user),
) -> list[DocumentItem]:
    """List all indexed or processing documents for current user."""
    stmt = (
        select(DocumentModel)
        .where(DocumentModel.user_id == current_user.id)
        .order_by(desc(DocumentModel.created_at))
        .limit(limit)
        .offset(offset)
    )
    result = await db.execute(stmt)
    docs = result.scalars().all()
    return [_doc_to_schema(d) for d in docs]


@knowledge_router.get("/documents/{doc_id}", response_model=DocumentItem)
async def get_document(
    doc_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: UserModel = Depends(get_current_user),
) -> DocumentItem:
    """Retrieve document metadata and processing status."""
    stmt = select(DocumentModel).where(
        DocumentModel.id == doc_id,
        DocumentModel.user_id == current_user.id,
    )
    result = await db.execute(stmt)
    doc = result.scalar_one_or_none()
    if not doc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Document '{doc_id}' not found",
        )
    return _doc_to_schema(doc)


@knowledge_router.get("/documents/{doc_id}/chunks", response_model=list[DocumentChunkItem])
async def list_document_chunks(
    doc_id: str,
    limit: int = Query(100, ge=1, le=500),
    offset: int = Query(0, ge=0),
    db: AsyncSession = Depends(get_db),
    current_user: UserModel = Depends(get_current_user),
) -> list[DocumentChunkItem]:
    """List indexed chunks with character/page offsets for a document."""
    # Ensure document belongs to user
    doc = await db.scalar(
        select(DocumentModel).where(
            DocumentModel.id == doc_id,
            DocumentModel.user_id == current_user.id,
        )
    )
    if not doc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Document '{doc_id}' not found",
        )

    stmt = (
        select(DocumentChunkModel)
        .where(DocumentChunkModel.document_id == doc_id)
        .order_by(DocumentChunkModel.chunk_index.asc())
        .limit(limit)
        .offset(offset)
    )
    result = await db.execute(stmt)
    chunks = result.scalars().all()

    return [
        DocumentChunkItem(
            id=c.id,
            document_id=c.document_id,
            chunk_index=c.chunk_index,
            content=c.content,
            page_number=c.page_number,
            char_start=c.char_start,
            char_end=c.char_end,
            metadata=c.chunk_metadata or {},
            created_at=c.created_at,
        )
        for c in chunks
    ]


@knowledge_router.delete("/documents/{doc_id}", status_code=status.HTTP_200_OK)
async def delete_document(
    doc_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: UserModel = Depends(get_current_user),
) -> dict[str, Any]:
    """Delete a document and cascade remove all its indexed chunks."""
    stmt = delete(DocumentModel).where(
        DocumentModel.id == doc_id,
        DocumentModel.user_id == current_user.id,
    )
    result = await db.execute(stmt)
    await db.commit()

    rowcount = getattr(result, "rowcount", 0) or 0
    if rowcount == 0:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Document '{doc_id}' not found",
        )
    return {"deleted": True, "id": doc_id}


@knowledge_router.post("/search", response_model=KnowledgeSearchResponse)
async def search_knowledge(
    request: KnowledgeSearchRequest,
    db: AsyncSession = Depends(get_db),
    current_user: UserModel = Depends(get_current_user),
) -> KnowledgeSearchResponse:
    """Semantic vector search across indexed documents with source attribution."""
    vector_store = get_vector_store()
    results = await vector_store.search(
        db=db,
        user_id=current_user.id,
        query=request.query,
        limit=request.limit,
        min_similarity=request.min_similarity,
        document_ids=request.document_ids,
    )
    return KnowledgeSearchResponse(
        query=request.query,
        total_chunks_matched=len(results),
        results=results,
    )


@knowledge_router.post("/rag", response_model=RAGQueryResponse)
async def rag_query(
    request: RAGQueryRequest,
    db: AsyncSession = Depends(get_db),
    current_user: UserModel = Depends(get_current_user),
) -> RAGQueryResponse:
    """Execute end-to-end RAG synthesis with supporting source attributions."""
    rag_engine = get_rag_engine()
    return await rag_engine.execute_rag_query(
        db=db,
        user_id=current_user.id,
        request=request,
    )


def _doc_to_schema(doc: DocumentModel) -> DocumentItem:
    return DocumentItem(
        id=doc.id,
        user_id=doc.user_id,
        filename=doc.filename,
        file_type=doc.file_type,
        file_size_bytes=doc.file_size_bytes,
        sha256=doc.sha256,
        chunk_count=doc.chunk_count,
        status=DocumentStatus(doc.status),
        error_message=doc.error_message,
        metadata=doc.doc_metadata or {},
        created_at=doc.created_at,
        updated_at=doc.updated_at,
    )
