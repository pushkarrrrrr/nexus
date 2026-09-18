"""identity_and_user_context

Revision ID: 002_identity_and_user_context
Revises: 001_initial_schema
Create Date: 2026-09-18 19:30:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "002_identity_and_user_context"
down_revision: str | None = "001_initial_schema"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # 1. users table
    op.create_table(
        "users",
        sa.Column("id", sa.String(length=64), nullable=False),
        sa.Column("email", sa.String(length=255), nullable=False),
        sa.Column("hashed_password", sa.String(length=255), nullable=False),
        sa.Column("full_name", sa.String(length=255), nullable=True),
        sa.Column("is_active", sa.Boolean(), server_default=sa.true(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_users_email"), "users", ["email"], unique=True)

    # 2. user_preferences table
    op.create_table(
        "user_preferences",
        sa.Column("id", sa.String(length=64), nullable=False),
        sa.Column("user_id", sa.String(length=64), nullable=False),
        sa.Column("timezone", sa.String(length=64), server_default="UTC", nullable=False),
        sa.Column("model_preferences", sa.JSON(), nullable=False),
        sa.Column("permission_preferences", sa.JSON(), nullable=False),
        sa.Column("privacy_settings", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_user_preferences_user_id"), "user_preferences", ["user_id"], unique=True
    )

    # 3. Add user_id to sessions
    with op.batch_alter_table("sessions") as batch_op:
        batch_op.add_column(sa.Column("user_id", sa.String(length=64), nullable=True))
        batch_op.create_foreign_key(
            "fk_sessions_user_id", "users", ["user_id"], ["id"], ondelete="SET NULL"
        )
        batch_op.create_index(op.f("ix_sessions_user_id"), ["user_id"], unique=False)

    # 4. Add user_id to task_dags
    with op.batch_alter_table("task_dags") as batch_op:
        batch_op.add_column(sa.Column("user_id", sa.String(length=64), nullable=True))
        batch_op.create_foreign_key(
            "fk_task_dags_user_id", "users", ["user_id"], ["id"], ondelete="SET NULL"
        )
        batch_op.create_index(op.f("ix_task_dags_user_id"), ["user_id"], unique=False)

    # 5. Add user_id to audit_logs
    with op.batch_alter_table("audit_logs") as batch_op:
        batch_op.add_column(sa.Column("user_id", sa.String(length=64), nullable=True))
        batch_op.create_foreign_key(
            "fk_audit_logs_user_id", "users", ["user_id"], ["id"], ondelete="SET NULL"
        )
        batch_op.create_index(op.f("ix_audit_logs_user_id"), ["user_id"], unique=False)

    # 6. Add user_id to memories
    with op.batch_alter_table("memories") as batch_op:
        batch_op.add_column(sa.Column("user_id", sa.String(length=64), nullable=True))
        batch_op.create_foreign_key(
            "fk_memories_user_id", "users", ["user_id"], ["id"], ondelete="SET NULL"
        )
        batch_op.create_index(op.f("ix_memories_user_id"), ["user_id"], unique=False)


def downgrade() -> None:
    with op.batch_alter_table("memories") as batch_op:
        batch_op.drop_index(op.f("ix_memories_user_id"))
        batch_op.drop_constraint("fk_memories_user_id", type_="foreignkey")
        batch_op.drop_column("user_id")

    with op.batch_alter_table("audit_logs") as batch_op:
        batch_op.drop_index(op.f("ix_audit_logs_user_id"))
        batch_op.drop_constraint("fk_audit_logs_user_id", type_="foreignkey")
        batch_op.drop_column("user_id")

    with op.batch_alter_table("task_dags") as batch_op:
        batch_op.drop_index(op.f("ix_task_dags_user_id"))
        batch_op.drop_constraint("fk_task_dags_user_id", type_="foreignkey")
        batch_op.drop_column("user_id")

    with op.batch_alter_table("sessions") as batch_op:
        batch_op.drop_index(op.f("ix_sessions_user_id"))
        batch_op.drop_constraint("fk_sessions_user_id", type_="foreignkey")
        batch_op.drop_column("user_id")

    op.drop_table("user_preferences")
    op.drop_table("users")
