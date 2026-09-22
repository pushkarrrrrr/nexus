"""external_integrations

Revision ID: 009_external_integrations
Revises: 008_reversible_actions
Create Date: 2026-09-20 18:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "009_external_integrations"
down_revision: str | None = "008_reversible_actions"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "user_integrations",
        sa.Column("id", sa.String(length=64), nullable=False),
        sa.Column("user_id", sa.String(length=64), nullable=False),
        sa.Column("provider", sa.String(length=32), nullable=False),
        sa.Column("is_enabled", sa.Boolean(), server_default=sa.true(), nullable=False),
        sa.Column("credentials_encrypted", sa.Text(), nullable=True),
        sa.Column("config", sa.JSON(), server_default="{}", nullable=False),
        sa.Column("status", sa.String(length=32), server_default="DISCONNECTED", nullable=False),
        sa.Column("last_sync_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("user_id", "provider", name="uq_user_integrations_user_provider"),
    )
    op.create_index(
        "ix_user_integrations_user_id",
        "user_integrations",
        ["user_id"],
    )
    op.create_index(
        "ix_user_integrations_provider",
        "user_integrations",
        ["provider"],
    )
    op.create_index(
        "ix_user_integrations_status",
        "user_integrations",
        ["status"],
    )


def downgrade() -> None:
    op.drop_index("ix_user_integrations_status", table_name="user_integrations")
    op.drop_index("ix_user_integrations_provider", table_name="user_integrations")
    op.drop_index("ix_user_integrations_user_id", table_name="user_integrations")
    op.drop_table("user_integrations")
