"""self_correction_recovery

Revision ID: 011_self_correction_recovery
Revises: 010_proactive_triggers
Create Date: 2026-09-24 02:50:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "011_self_correction_recovery"
down_revision: str | None = "010_proactive_triggers"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # 1. Create replan_records table
    op.create_table(
        "replan_records",
        sa.Column("id", sa.String(length=64), nullable=False),
        sa.Column("plan_id", sa.String(length=64), nullable=False),
        sa.Column("step_id", sa.String(length=64), nullable=False),
        sa.Column("task_id", sa.String(length=64), nullable=False),
        sa.Column("user_id", sa.String(length=64), nullable=False),
        sa.Column("iteration", sa.Integer(), server_default="1", nullable=False),
        sa.Column("error_category", sa.String(length=64), nullable=False),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("diagnosis", sa.Text(), nullable=False),
        sa.Column("strategy", sa.String(length=64), nullable=False),
        sa.Column("recovery_steps", sa.JSON(), server_default="[]", nullable=False),
        sa.Column("snapshot_id", sa.String(length=64), nullable=True),
        sa.Column("rollback_performed", sa.Boolean(), server_default=sa.false(), nullable=False),
        sa.Column("status", sa.String(length=32), server_default="replanned", nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["plan_id"], ["execution_plans.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["step_id"], ["plan_steps.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["task_id"], ["task_dags.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_replan_records_plan_id",
        "replan_records",
        ["plan_id"],
    )
    op.create_index(
        "ix_replan_records_step_id",
        "replan_records",
        ["step_id"],
    )
    op.create_index(
        "ix_replan_records_user_id",
        "replan_records",
        ["user_id"],
    )
    op.create_index(
        "ix_replan_records_plan_step",
        "replan_records",
        ["plan_id", "step_id"],
    )
    op.create_index(
        "ix_replan_records_user_created",
        "replan_records",
        ["user_id", "created_at"],
    )

    # 2. Add columns to plan_steps using batch_alter_table for SQLite compatibility
    with op.batch_alter_table("plan_steps") as batch_op:
        batch_op.add_column(
            sa.Column("is_recovery_step", sa.Boolean(), server_default=sa.false(), nullable=False)
        )
        batch_op.add_column(
            sa.Column("replaces_step_id", sa.String(length=64), nullable=True)
        )


def downgrade() -> None:
    # 1. Remove columns from plan_steps using batch_alter_table
    with op.batch_alter_table("plan_steps") as batch_op:
        batch_op.drop_column("replaces_step_id")
        batch_op.drop_column("is_recovery_step")

    # 2. Drop replan_records indexes and table
    op.drop_index("ix_replan_records_user_created", table_name="replan_records")
    op.drop_index("ix_replan_records_plan_step", table_name="replan_records")
    op.drop_index("ix_replan_records_user_id", table_name="replan_records")
    op.drop_index("ix_replan_records_step_id", table_name="replan_records")
    op.drop_index("ix_replan_records_plan_id", table_name="replan_records")
    op.drop_table("replan_records")
