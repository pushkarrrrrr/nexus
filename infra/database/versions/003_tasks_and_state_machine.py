"""tasks_and_state_machine

Revision ID: 003_tasks_and_state_machine
Revises: 002_identity_and_user_context
Create Date: 2026-09-19 19:30:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "003_tasks_and_state_machine"
down_revision: str | None = "002_identity_and_user_context"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # 1. Update task_dags with execution_metadata
    with op.batch_alter_table("task_dags") as batch_op:
        batch_op.add_column(
            sa.Column("execution_metadata", sa.JSON(), server_default="{}", nullable=False)
        )

    # 2. Update dag_nodes with timestamps and retry_count
    with op.batch_alter_table("dag_nodes") as batch_op:
        batch_op.add_column(sa.Column("started_at", sa.DateTime(timezone=True), nullable=True))
        batch_op.add_column(sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True))
        batch_op.add_column(
            sa.Column("retry_count", sa.Integer(), server_default="0", nullable=False)
        )

    # 3. Create task_events table
    op.create_table(
        "task_events",
        sa.Column("id", sa.String(length=64), nullable=False),
        sa.Column("dag_id", sa.String(length=64), nullable=False),
        sa.Column("node_id", sa.String(length=64), nullable=True),
        sa.Column("event_type", sa.String(length=64), nullable=False),
        sa.Column("from_state", sa.String(length=32), nullable=True),
        sa.Column("to_state", sa.String(length=32), nullable=True),
        sa.Column("message", sa.Text(), nullable=False),
        sa.Column("payload", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["dag_id"], ["task_dags.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["node_id"], ["dag_nodes.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_task_events_dag_id"), "task_events", ["dag_id"], unique=False)

    # 4. Create goals table
    op.create_table(
        "goals",
        sa.Column("id", sa.String(length=64), nullable=False),
        sa.Column("user_id", sa.String(length=64), nullable=False),
        sa.Column("session_id", sa.String(length=64), nullable=True),
        sa.Column("title", sa.String(length=255), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("status", sa.String(length=32), server_default="active", nullable=False),
        sa.Column("category", sa.String(length=64), server_default="general", nullable=False),
        sa.Column("progress", sa.Float(), server_default="0.0", nullable=False),
        sa.Column("milestones", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["session_id"], ["sessions.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_goals_user_id"), "goals", ["user_id"], unique=False)
    op.create_index(op.f("ix_goals_session_id"), "goals", ["session_id"], unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_goals_session_id"), table_name="goals")
    op.drop_index(op.f("ix_goals_user_id"), table_name="goals")
    op.drop_table("goals")

    op.drop_index(op.f("ix_task_events_dag_id"), table_name="task_events")
    op.drop_table("task_events")

    with op.batch_alter_table("dag_nodes") as batch_op:
        batch_op.drop_column("retry_count")
        batch_op.drop_column("completed_at")
        batch_op.drop_column("started_at")

    with op.batch_alter_table("task_dags") as batch_op:
        batch_op.drop_column("execution_metadata")
