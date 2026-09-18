"""initial_schema

Revision ID: 001_initial_schema
Revises:
Create Date: 2026-09-18 18:30:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "001_initial_schema"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # 1. sessions
    op.create_table(
        "sessions",
        sa.Column("id", sa.String(length=64), nullable=False),
        sa.Column("surface", sa.String(length=32), nullable=False),
        sa.Column("title", sa.String(length=255), nullable=True),
        sa.Column("os_context", sa.JSON(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )

    # 2. task_dags
    op.create_table(
        "task_dags",
        sa.Column("id", sa.String(length=64), nullable=False),
        sa.Column("session_id", sa.String(length=64), nullable=False),
        sa.Column("goal", sa.Text(), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["session_id"], ["sessions.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_task_dags_session_id"), "task_dags", ["session_id"], unique=False)

    # 3. dag_nodes
    op.create_table(
        "dag_nodes",
        sa.Column("id", sa.String(length=64), nullable=False),
        sa.Column("dag_id", sa.String(length=64), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("agent_name", sa.String(length=64), nullable=False),
        sa.Column("tool_name", sa.String(length=64), nullable=True),
        sa.Column("input_payload", sa.JSON(), nullable=True),
        sa.Column("dependencies", sa.JSON(), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("result_payload", sa.JSON(), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.ForeignKeyConstraint(["dag_id"], ["task_dags.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_dag_nodes_dag_id"), "dag_nodes", ["dag_id"], unique=False)

    # 4. audit_logs
    op.create_table(
        "audit_logs",
        sa.Column("id", sa.String(length=64), nullable=False),
        sa.Column("session_id", sa.String(length=64), nullable=False),
        sa.Column("step_id", sa.String(length=64), nullable=True),
        sa.Column("agent_name", sa.String(length=64), nullable=False),
        sa.Column("tool_name", sa.String(length=64), nullable=False),
        sa.Column("action_type", sa.String(length=32), nullable=False),
        sa.Column("risk_level", sa.String(length=32), nullable=False),
        sa.Column("inputs", sa.JSON(), nullable=False),
        sa.Column("outputs", sa.JSON(), nullable=True),
        sa.Column("error", sa.Text(), nullable=True),
        sa.Column("policy_verdict", sa.String(length=32), nullable=False),
        sa.Column("approval_id", sa.String(length=64), nullable=True),
        sa.Column("snapshot_id", sa.String(length=64), nullable=True),
        sa.Column("duration_ms", sa.Float(), nullable=False),
        sa.Column("undone_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["session_id"], ["sessions.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_audit_logs_session_id"), "audit_logs", ["session_id"], unique=False)

    # 5. file_snapshots
    op.create_table(
        "file_snapshots",
        sa.Column("id", sa.String(length=64), nullable=False),
        sa.Column("audit_event_id", sa.String(length=64), nullable=False),
        sa.Column("file_path", sa.Text(), nullable=False),
        sa.Column("sha256_before", sa.String(length=64), nullable=False),
        sa.Column("sha256_after", sa.String(length=64), nullable=True),
        sa.Column("backup_storage_path", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("restored_at", sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )

    # 6. memories
    op.create_table(
        "memories",
        sa.Column("id", sa.String(length=64), nullable=False),
        sa.Column("memory_class", sa.String(length=32), nullable=False),
        sa.Column("title", sa.String(length=255), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("source_session_id", sa.String(length=64), nullable=True),
        sa.Column("confidence", sa.Float(), nullable=False),
        sa.Column("enabled", sa.Boolean(), nullable=False),
        sa.Column("tags", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_memories_memory_class"), "memories", ["memory_class"], unique=False)

    # 7. session_grants
    op.create_table(
        "session_grants",
        sa.Column("id", sa.String(length=64), nullable=False),
        sa.Column("session_id", sa.String(length=64), nullable=False),
        sa.Column("tool_name", sa.String(length=64), nullable=False),
        sa.Column("pattern", sa.Text(), nullable=False),
        sa.Column("granted_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["session_id"], ["sessions.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_session_grants_session_id"), "session_grants", ["session_id"], unique=False
    )


def downgrade() -> None:
    op.drop_table("session_grants")
    op.drop_table("memories")
    op.drop_table("file_snapshots")
    op.drop_table("audit_logs")
    op.drop_table("dag_nodes")
    op.drop_table("task_dags")
    op.drop_table("sessions")
