"""reversible_actions

Revision ID: 008_reversible_actions
Revises: 007_policy_and_trust
Create Date: 2026-09-20 16:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "008_reversible_actions"
down_revision: str | None = "007_policy_and_trust"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # 1. Create action_snapshots table
    op.create_table(
        "action_snapshots",
        sa.Column("id", sa.String(length=64), nullable=False),
        sa.Column("user_id", sa.String(length=64), nullable=False),
        sa.Column("task_id", sa.String(length=64), nullable=True),
        sa.Column("step_id", sa.String(length=64), nullable=True),
        sa.Column("capability_name", sa.String(length=64), nullable=False),
        sa.Column("action_type", sa.String(length=32), nullable=False),
        sa.Column("is_reversible", sa.Boolean(), server_default=sa.true(), nullable=False),
        sa.Column("target_path", sa.Text(), nullable=True),
        sa.Column("before_state", sa.JSON(), nullable=True),
        sa.Column("after_state", sa.JSON(), nullable=True),
        sa.Column("diff_patch", sa.Text(), nullable=True),
        sa.Column("status", sa.String(length=32), server_default="CAPTURED", nullable=False),
        sa.Column("reverted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["task_id"], ["task_dags.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_action_snapshots_user_status", "action_snapshots", ["user_id", "status"])
    op.create_index("ix_action_snapshots_task_id", "action_snapshots", ["task_id"])
    op.create_index("ix_action_snapshots_capability_name", "action_snapshots", ["capability_name"])
    op.create_index("ix_action_snapshots_status", "action_snapshots", ["status"])

    # 2. Update approval_requests table with snapshot and diff fields
    with op.batch_alter_table("approval_requests") as batch_op:
        batch_op.add_column(sa.Column("snapshot_id", sa.String(length=64), nullable=True))
        batch_op.add_column(sa.Column("diff_preview", sa.Text(), nullable=True))
        batch_op.add_column(
            sa.Column(
                "is_reversible",
                sa.Boolean(),
                server_default=sa.false(),
                nullable=False,
            )
        )
        batch_op.create_foreign_key(
            "fk_approval_requests_snapshot_id",
            "action_snapshots",
            ["snapshot_id"],
            ["id"],
            ondelete="SET NULL",
        )
        batch_op.create_index("ix_approval_requests_snapshot_id", ["snapshot_id"])


def downgrade() -> None:
    # 2. Revert approval_requests table changes
    with op.batch_alter_table("approval_requests") as batch_op:
        batch_op.drop_index("ix_approval_requests_snapshot_id")
        batch_op.drop_constraint("fk_approval_requests_snapshot_id", type_="foreignkey")
        batch_op.drop_column("is_reversible")
        batch_op.drop_column("diff_preview")
        batch_op.drop_column("snapshot_id")

    # 1. Drop action_snapshots table
    op.drop_index("ix_action_snapshots_status", table_name="action_snapshots")
    op.drop_index("ix_action_snapshots_capability_name", table_name="action_snapshots")
    op.drop_index("ix_action_snapshots_task_id", table_name="action_snapshots")
    op.drop_index("ix_action_snapshots_user_status", table_name="action_snapshots")
    op.drop_table("action_snapshots")
