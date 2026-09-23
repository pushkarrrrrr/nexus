"""proactive_triggers

Revision ID: 010_proactive_triggers
Revises: 009_external_integrations
Create Date: 2026-09-24 01:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "010_proactive_triggers"
down_revision: str | None = "009_external_integrations"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "proactive_triggers",
        sa.Column("id", sa.String(length=64), nullable=False),
        sa.Column("user_id", sa.String(length=64), nullable=False),
        sa.Column("name", sa.String(length=128), nullable=False),
        sa.Column("trigger_type", sa.String(length=32), nullable=False),
        sa.Column("condition", sa.JSON(), server_default="{}", nullable=False),
        sa.Column("action_capability", sa.String(length=64), nullable=False),
        sa.Column("action_params", sa.JSON(), server_default="{}", nullable=False),
        sa.Column("is_active", sa.Boolean(), server_default=sa.true(), nullable=False),
        sa.Column("cooldown_seconds", sa.Integer(), server_default="300", nullable=False),
        sa.Column("last_triggered_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("trigger_count", sa.Integer(), server_default="0", nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_proactive_triggers_user_id",
        "proactive_triggers",
        ["user_id"],
    )
    op.create_index(
        "ix_proactive_triggers_trigger_type",
        "proactive_triggers",
        ["trigger_type"],
    )
    op.create_index(
        "ix_proactive_triggers_is_active",
        "proactive_triggers",
        ["is_active"],
    )
    op.create_index(
        "ix_proactive_triggers_user_active",
        "proactive_triggers",
        ["user_id", "is_active"],
    )

    op.create_table(
        "trigger_events",
        sa.Column("id", sa.String(length=64), nullable=False),
        sa.Column("trigger_id", sa.String(length=64), nullable=False),
        sa.Column("user_id", sa.String(length=64), nullable=False),
        sa.Column("event_type", sa.String(length=64), nullable=False),
        sa.Column("observed_data", sa.JSON(), server_default="{}", nullable=False),
        sa.Column("action_proposed", sa.String(length=64), nullable=False),
        sa.Column("approval_id", sa.String(length=64), nullable=True),
        sa.Column("status", sa.String(length=32), server_default="detected", nullable=False),
        sa.Column("result_payload", sa.JSON(), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["trigger_id"], ["proactive_triggers.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["approval_id"], ["approval_requests.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_trigger_events_trigger_id",
        "trigger_events",
        ["trigger_id"],
    )
    op.create_index(
        "ix_trigger_events_user_id",
        "trigger_events",
        ["user_id"],
    )
    op.create_index(
        "ix_trigger_events_status",
        "trigger_events",
        ["status"],
    )
    op.create_index(
        "ix_trigger_events_user_status",
        "trigger_events",
        ["user_id", "status"],
    )


def downgrade() -> None:
    op.drop_index("ix_trigger_events_user_status", table_name="trigger_events")
    op.drop_index("ix_trigger_events_status", table_name="trigger_events")
    op.drop_index("ix_trigger_events_user_id", table_name="trigger_events")
    op.drop_index("ix_trigger_events_trigger_id", table_name="trigger_events")
    op.drop_table("trigger_events")

    op.drop_index("ix_proactive_triggers_user_active", table_name="proactive_triggers")
    op.drop_index("ix_proactive_triggers_is_active", table_name="proactive_triggers")
    op.drop_index("ix_proactive_triggers_trigger_type", table_name="proactive_triggers")
    op.drop_index("ix_proactive_triggers_user_id", table_name="proactive_triggers")
    op.drop_table("proactive_triggers")
