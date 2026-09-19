"""agent_plans

Revision ID: 006_agent_plans
Revises: 005_knowledge_graph
Create Date: 2026-09-20 04:30:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "006_agent_plans"
down_revision: str | None = "005_knowledge_graph"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # 1. Create execution_plans table
    op.create_table(
        "execution_plans",
        sa.Column("id", sa.String(length=64), nullable=False),
        sa.Column("task_id", sa.String(length=64), nullable=False),
        sa.Column("user_id", sa.String(length=64), nullable=False),
        sa.Column("goal", sa.Text(), nullable=False),
        sa.Column("current_step_index", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("status", sa.String(length=32), nullable=False, server_default="created"),
        sa.Column("replan_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("max_replans", sa.Integer(), nullable=False, server_default="3"),
        sa.Column("plan_metadata", sa.JSON(), nullable=False, server_default="{}"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["task_id"], ["task_dags.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_execution_plans_task_id", "execution_plans", ["task_id"])
    op.create_index("ix_execution_plans_user_id", "execution_plans", ["user_id"])
    op.create_index("ix_execution_plans_status", "execution_plans", ["status"])
    op.create_index("ix_execution_plans_user_status", "execution_plans", ["user_id", "status"])

    # 2. Create plan_steps table
    op.create_table(
        "plan_steps",
        sa.Column("id", sa.String(length=64), nullable=False),
        sa.Column("plan_id", sa.String(length=64), nullable=False),
        sa.Column("index", sa.Integer(), nullable=False),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column(
            "assigned_agent", sa.String(length=64), nullable=False, server_default="orchestrator"
        ),
        sa.Column("required_tools", sa.JSON(), nullable=False, server_default="[]"),
        sa.Column("dependencies", sa.JSON(), nullable=False, server_default="[]"),
        sa.Column("status", sa.String(length=32), nullable=False, server_default="pending"),
        sa.Column("retry_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("max_retries", sa.Integer(), nullable=False, server_default="2"),
        sa.Column("result_payload", sa.JSON(), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["plan_id"], ["execution_plans.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_plan_steps_plan_id", "plan_steps", ["plan_id"])
    op.create_index("ix_plan_steps_plan_index", "plan_steps", ["plan_id", "index"])


def downgrade() -> None:
    op.drop_index("ix_plan_steps_plan_index", table_name="plan_steps")
    op.drop_index("ix_plan_steps_plan_id", table_name="plan_steps")
    op.drop_table("plan_steps")

    op.drop_index("ix_execution_plans_user_status", table_name="execution_plans")
    op.drop_index("ix_execution_plans_status", table_name="execution_plans")
    op.drop_index("ix_execution_plans_user_id", table_name="execution_plans")
    op.drop_index("ix_execution_plans_task_id", table_name="execution_plans")
    op.drop_table("execution_plans")
