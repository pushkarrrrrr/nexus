"""knowledge_graph

Revision ID: 005_knowledge_graph
Revises: 004_memory_and_knowledge
Create Date: 2026-09-20 03:25:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "005_knowledge_graph"
down_revision: str | None = "004_memory_and_knowledge"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # 1. Create knowledge_nodes table
    op.create_table(
        "knowledge_nodes",
        sa.Column("id", sa.String(length=64), nullable=False),
        sa.Column("user_id", sa.String(length=64), nullable=False),
        sa.Column("label", sa.String(length=255), nullable=False),
        sa.Column("node_type", sa.String(length=32), nullable=False),
        sa.Column("properties", sa.JSON(), nullable=False, server_default="{}"),
        sa.Column("document_id", sa.String(length=64), nullable=True),
        sa.Column("memory_id", sa.String(length=64), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["document_id"], ["documents.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["memory_id"], ["memories.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_knowledge_nodes_user_id"), "knowledge_nodes", ["user_id"], unique=False
    )
    op.create_index(op.f("ix_knowledge_nodes_label"), "knowledge_nodes", ["label"], unique=False)
    op.create_index(
        op.f("ix_knowledge_nodes_node_type"), "knowledge_nodes", ["node_type"], unique=False
    )
    op.create_index(
        op.f("ix_knowledge_nodes_document_id"), "knowledge_nodes", ["document_id"], unique=False
    )
    op.create_index(
        op.f("ix_knowledge_nodes_memory_id"), "knowledge_nodes", ["memory_id"], unique=False
    )
    op.create_index(
        "ix_knowledge_nodes_user_type", "knowledge_nodes", ["user_id", "node_type"], unique=False
    )
    op.create_index(
        "ix_knowledge_nodes_user_label", "knowledge_nodes", ["user_id", "label"], unique=False
    )

    # 2. Create knowledge_edges table
    op.create_table(
        "knowledge_edges",
        sa.Column("id", sa.String(length=64), nullable=False),
        sa.Column("user_id", sa.String(length=64), nullable=False),
        sa.Column("source_node_id", sa.String(length=64), nullable=False),
        sa.Column("target_node_id", sa.String(length=64), nullable=False),
        sa.Column("relation_type", sa.String(length=64), nullable=False),
        sa.Column("weight", sa.Float(), nullable=False, server_default="1.0"),
        sa.Column("properties", sa.JSON(), nullable=False, server_default="{}"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["source_node_id"], ["knowledge_nodes.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["target_node_id"], ["knowledge_nodes.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_knowledge_edges_user_id"), "knowledge_edges", ["user_id"], unique=False
    )
    op.create_index(
        op.f("ix_knowledge_edges_source_node_id"),
        "knowledge_edges",
        ["source_node_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_knowledge_edges_target_node_id"),
        "knowledge_edges",
        ["target_node_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_knowledge_edges_relation_type"), "knowledge_edges", ["relation_type"], unique=False
    )
    op.create_index(
        "ix_knowledge_edges_source_rel",
        "knowledge_edges",
        ["source_node_id", "relation_type"],
        unique=False,
    )
    op.create_index(
        "ix_knowledge_edges_target_rel",
        "knowledge_edges",
        ["target_node_id", "relation_type"],
        unique=False,
    )
    op.create_index(
        "ix_knowledge_edges_user_rel", "knowledge_edges", ["user_id", "relation_type"], unique=False
    )


def downgrade() -> None:
    op.drop_table("knowledge_edges")
    op.drop_table("knowledge_nodes")
