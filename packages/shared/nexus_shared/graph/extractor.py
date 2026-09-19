"""NEXUS Relation Extractor Subsystem.

Automatically extracts structured entity nodes and semantic relations from
documents, tasks, and memory entries to build the knowledge graph without
requiring manual triple entry.
"""

import re
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from packages.shared.nexus_shared.graph.engine import get_graph_engine
from packages.shared.nexus_shared.models import KnowledgeEdgeModel, KnowledgeNodeModel
from packages.types.nexus_types.schemas import (
    KnowledgeEdgeCreate,
    KnowledgeNodeCreate,
    NodeType,
    RelationType,
)

# Common technology keywords to detect automatically
TECH_KEYWORDS = {
    "python",
    "typescript",
    "javascript",
    "react",
    "nextjs",
    "next.js",
    "fastapi",
    "postgresql",
    "postgres",
    "sqlite",
    "pgvector",
    "docker",
    "kubernetes",
    "redis",
    "celery",
    "graphql",
    "rest",
    "tailwind",
    "css",
    "html",
    "git",
    "github",
    "openai",
    "anthropic",
    "gemini",
    "ollama",
    "rag",
    "pytorch",
    "tensorflow",
}


class RelationExtractor:
    """Heuristic and rule-based relation extractor linking knowledge entities."""

    async def extract_from_document(
        self,
        db: AsyncSession,
        user_id: str,
        document_id: str,
        filename: str,
        content: str,
        chunks: list[dict[str, Any]] | None = None,
    ) -> list[str]:
        """Extract concepts, technologies, and relations from an ingested document."""
        engine = get_graph_engine()
        created_edge_ids: list[str] = []

        # 1. Ensure a node for the document itself exists
        doc_node_label = filename
        existing_doc_stmt = select(KnowledgeNodeModel).where(
            KnowledgeNodeModel.user_id == user_id,
            KnowledgeNodeModel.document_id == document_id,
        )
        doc_node = await db.scalar(existing_doc_stmt)
        if not doc_node:
            doc_node_item = await engine.create_node(
                db=db,
                user_id=user_id,
                request=KnowledgeNodeCreate(
                    label=doc_node_label,
                    node_type=NodeType.DOCUMENT,
                    document_id=document_id,
                    properties={"filename": filename, "source": "ingestion"},
                ),
            )
            doc_node_id = doc_node_item.id
        else:
            doc_node_id = doc_node.id

        # 2. Extract technology entities
        lower_content = content.lower()
        extracted_techs = {
            tech for tech in TECH_KEYWORDS if re.search(rf"\b{re.escape(tech)}\b", lower_content)
        }

        for tech in extracted_techs:
            tech_label = tech.capitalize() if tech != "next.js" else "Next.js"
            node_stmt = select(KnowledgeNodeModel).where(
                KnowledgeNodeModel.user_id == user_id,
                KnowledgeNodeModel.label.ilike(tech_label),
            )
            node = await db.scalar(node_stmt)
            if not node:
                node_item = await engine.create_node(
                    db=db,
                    user_id=user_id,
                    request=KnowledgeNodeCreate(
                        label=tech_label,
                        node_type=NodeType.TECHNOLOGY,
                        properties={"auto_extracted": True},
                    ),
                )
                target_node_id = node_item.id
            else:
                target_node_id = node.id

            # Create edge: Document -> references -> Technology
            edge_exists = await db.scalar(
                select(KnowledgeEdgeModel).where(
                    KnowledgeEdgeModel.user_id == user_id,
                    KnowledgeEdgeModel.source_node_id == doc_node_id,
                    KnowledgeEdgeModel.target_node_id == target_node_id,
                    KnowledgeEdgeModel.relation_type == RelationType.REFERENCES.value,
                )
            )
            if not edge_exists:
                edge_item = await engine.create_edge(
                    db=db,
                    user_id=user_id,
                    request=KnowledgeEdgeCreate(
                        source_node_id=doc_node_id,
                        target_node_id=target_node_id,
                        relation_type=RelationType.REFERENCES,
                        weight=1.0,
                    ),
                )
                created_edge_ids.append(edge_item.id)

        # 3. Extract Markdown / section headers as Concepts
        header_matches = re.findall(r"^#+\s+(.+)$", content, flags=re.MULTILINE)
        for header in header_matches[:5]:  # limit to top 5 main concepts
            clean_concept = header.strip()
            if len(clean_concept) < 3 or len(clean_concept) > 60:
                continue

            concept_node = await db.scalar(
                select(KnowledgeNodeModel).where(
                    KnowledgeNodeModel.user_id == user_id,
                    KnowledgeNodeModel.label.ilike(clean_concept),
                )
            )
            if not concept_node:
                concept_item = await engine.create_node(
                    db=db,
                    user_id=user_id,
                    request=KnowledgeNodeCreate(
                        label=clean_concept,
                        node_type=NodeType.CONCEPT,
                        properties={"source_document": filename},
                    ),
                )
                concept_id = concept_item.id
            else:
                concept_id = concept_node.id

            # Create edge: Document -> contains -> Concept
            edge_exists = await db.scalar(
                select(KnowledgeEdgeModel).where(
                    KnowledgeEdgeModel.user_id == user_id,
                    KnowledgeEdgeModel.source_node_id == doc_node_id,
                    KnowledgeEdgeModel.target_node_id == concept_id,
                    KnowledgeEdgeModel.relation_type == RelationType.CONTAINS.value,
                )
            )
            if not edge_exists:
                edge_item = await engine.create_edge(
                    db=db,
                    user_id=user_id,
                    request=KnowledgeEdgeCreate(
                        source_node_id=doc_node_id,
                        target_node_id=concept_id,
                        relation_type=RelationType.CONTAINS,
                        weight=1.0,
                    ),
                )
                created_edge_ids.append(edge_item.id)

        return created_edge_ids

    async def extract_from_memory(
        self,
        db: AsyncSession,
        user_id: str,
        memory_id: str,
        title: str,
        content: str,
        memory_class: str,
    ) -> list[str]:
        """Link a personal memory to concept or technology nodes."""
        engine = get_graph_engine()
        created_edge_ids: list[str] = []

        # 1. Create or get node for the memory
        mem_node = await db.scalar(
            select(KnowledgeNodeModel).where(
                KnowledgeNodeModel.user_id == user_id,
                KnowledgeNodeModel.memory_id == memory_id,
            )
        )
        if not mem_node:
            node_type = (
                NodeType.CONCEPT if memory_class in ("semantic", "procedural") else NodeType.TASK
            )
            mem_node_item = await engine.create_node(
                db=db,
                user_id=user_id,
                request=KnowledgeNodeCreate(
                    label=title,
                    node_type=node_type,
                    memory_id=memory_id,
                    properties={"memory_class": memory_class},
                ),
            )
            mem_node_id = mem_node_item.id
        else:
            mem_node_id = mem_node.id

        # 2. Extract technologies mentioned in memory
        lower_content = (title + " " + content).lower()
        extracted_techs = {
            tech for tech in TECH_KEYWORDS if re.search(rf"\b{re.escape(tech)}\b", lower_content)
        }

        for tech in extracted_techs:
            tech_label = tech.capitalize() if tech != "next.js" else "Next.js"
            tech_node = await db.scalar(
                select(KnowledgeNodeModel).where(
                    KnowledgeNodeModel.user_id == user_id,
                    KnowledgeNodeModel.label.ilike(tech_label),
                )
            )
            if not tech_node:
                tech_item = await engine.create_node(
                    db=db,
                    user_id=user_id,
                    request=KnowledgeNodeCreate(
                        label=tech_label,
                        node_type=NodeType.TECHNOLOGY,
                        properties={"auto_extracted": True},
                    ),
                )
                target_id = tech_item.id
            else:
                target_id = tech_node.id

            edge_exists = await db.scalar(
                select(KnowledgeEdgeModel).where(
                    KnowledgeEdgeModel.user_id == user_id,
                    KnowledgeEdgeModel.source_node_id == mem_node_id,
                    KnowledgeEdgeModel.target_node_id == target_id,
                )
            )
            if not edge_exists:
                edge_item = await engine.create_edge(
                    db=db,
                    user_id=user_id,
                    request=KnowledgeEdgeCreate(
                        source_node_id=mem_node_id,
                        target_node_id=target_id,
                        relation_type=RelationType.USES
                        if memory_class == "procedural"
                        else RelationType.REFERENCES,
                        weight=1.0,
                    ),
                )
                created_edge_ids.append(edge_item.id)

        return created_edge_ids


_relation_extractor: RelationExtractor | None = None


def get_relation_extractor() -> RelationExtractor:
    global _relation_extractor
    if _relation_extractor is None:
        _relation_extractor = RelationExtractor()
    return _relation_extractor
