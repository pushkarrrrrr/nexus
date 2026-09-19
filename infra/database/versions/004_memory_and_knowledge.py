"""memory_and_knowledge

Revision ID: 004_memory_and_knowledge
Revises: 003_tasks_and_state_machine
Create Date: 2026-09-20 02:20:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

from packages.config.nexus_config import get_settings

try:
    from pgvector.sqlalchemy import Vector as PgVector
except ImportError:
    PgVector = None

# revision identifiers, used by Alembic.
revision: str = "004_memory_and_knowledge"
down_revision: str | None = "003_tasks_and_state_machine"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def get_vector_column(dim: int | None = None) -> sa.types.TypeEngine:
    """Return pgvector.Vector for postgresql, or sa.JSON for sqlite/other."""
    if dim is None:
        dim = getattr(get_settings(), "embedding_dimension", 1536)
    bind = op.get_bind()
    if bind.dialect.name == "postgresql" and PgVector is not None:
        return PgVector(dim)
    return sa.JSON()


def upgrade() -> None:
    settings = get_settings()
    dim = getattr(settings, "embedding_dimension", 1536)

    # Enable pgvector extension on PostgreSQL if supported
    bind = op.get_bind()
    if bind.dialect.name == "postgresql":
        op.execute("CREATE EXTENSION IF NOT EXISTS vector")

    vec_col = get_vector_column(dim)

    # 1. Add embedding column to memories
    with op.batch_alter_table("memories") as batch_op:
        batch_op.add_column(sa.Column("embedding", vec_col, nullable=True))

    # 2. Create documents table
    op.create_table(
        "documents",
        sa.Column("id", sa.String(length=64), nullable=False),
        sa.Column("user_id", sa.String(length=64), nullable=False),
        sa.Column("filename", sa.String(length=255), nullable=False),
        sa.Column("file_type", sa.String(length=32), nullable=False),
        sa.Column("file_size_bytes", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("sha256", sa.String(length=64), nullable=False),
        sa.Column("chunk_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("status", sa.String(length=32), nullable=False, server_default="pending"),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("metadata", sa.JSON(), nullable=False, server_default="{}"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_documents_user_id"), "documents", ["user_id"], unique=False)
    op.create_index(op.f("ix_documents_file_type"), "documents", ["file_type"], unique=False)
    op.create_index(op.f("ix_documents_sha256"), "documents", ["sha256"], unique=False)
    op.create_index(op.f("ix_documents_status"), "documents", ["status"], unique=False)

    # 3. Create document_chunks table
    op.create_table(
        "document_chunks",
        sa.Column("id", sa.String(length=64), nullable=False),
        sa.Column("document_id", sa.String(length=64), nullable=False),
        sa.Column("chunk_index", sa.Integer(), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("page_number", sa.Integer(), nullable=True),
        sa.Column("char_start", sa.Integer(), nullable=True),
        sa.Column("char_end", sa.Integer(), nullable=True),
        sa.Column("embedding", vec_col, nullable=True),
        sa.Column("metadata", sa.JSON(), nullable=False, server_default="{}"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["document_id"], ["documents.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_document_chunks_document_id"), "document_chunks", ["document_id"], unique=False
    )


def downgrade() -> None:
    op.drop_table("document_chunks")
    op.drop_table("documents")
    with op.batch_alter_table("memories") as batch_op:
        batch_op.drop_column("embedding")
