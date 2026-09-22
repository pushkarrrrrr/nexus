"""policy_and_trust

Revision ID: 007_policy_and_trust
Revises: 006_agent_plans
Create Date: 2026-09-20 12:00:00.000000

"""

from collections.abc import Sequence
from datetime import UTC, datetime

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "007_policy_and_trust"
down_revision: str | None = "006_agent_plans"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

CORE_CAPABILITIES = [
    {
        "id": "cap_fs_read",
        "name": "filesystem.read",
        "category": "READ",
        "default_risk_level": "LOW",
        "description": "Read file contents and directory listings from local workspace",
        "is_active": True,
    },
    {
        "id": "cap_fs_write",
        "name": "filesystem.write",
        "category": "WRITE",
        "default_risk_level": "MEDIUM",
        "description": "Create new files and directories within workspace",
        "is_active": True,
    },
    {
        "id": "cap_fs_modify",
        "name": "filesystem.modify",
        "category": "MODIFY",
        "default_risk_level": "MEDIUM",
        "description": "Modify existing files with rollback snapshotting",
        "is_active": True,
    },
    {
        "id": "cap_fs_delete",
        "name": "filesystem.delete",
        "category": "DELETE",
        "default_risk_level": "HIGH",
        "description": "Delete files and directories permanently",
        "is_active": True,
    },
    {
        "id": "cap_term_exec",
        "name": "terminal.execute",
        "category": "EXECUTE",
        "default_risk_level": "HIGH",
        "description": "Execute shell/terminal commands in controlled sandbox",
        "is_active": True,
    },
    {
        "id": "cap_browser_open",
        "name": "browser.open",
        "category": "EXTERNAL_ACTION",
        "default_risk_level": "MEDIUM",
        "description": "Open and navigate URLs in web browser",
        "is_active": True,
    },
    {
        "id": "cap_browser_interact",
        "name": "browser.interact",
        "category": "EXTERNAL_ACTION",
        "default_risk_level": "HIGH",
        "description": "Interact with DOM, type, and click on web pages",
        "is_active": True,
    },
    {
        "id": "cap_sys_config",
        "name": "system.configure",
        "category": "MODIFY",
        "default_risk_level": "CRITICAL",
        "description": "Alter system configuration, security policies, and environment variables",
        "is_active": True,
    },
    {
        "id": "cap_net_request",
        "name": "network.request",
        "category": "EXTERNAL_ACTION",
        "default_risk_level": "MEDIUM",
        "description": "Send outbound HTTP requests to external endpoints",
        "is_active": True,
    },
    {
        "id": "cap_db_raw",
        "name": "database.raw_query",
        "category": "EXECUTE",
        "default_risk_level": "HIGH",
        "description": "Execute arbitrary raw SQL queries against databases",
        "is_active": True,
    },
]


def upgrade() -> None:
    now = datetime.now(UTC)

    # 1. capabilities table
    capabilities_table = op.create_table(
        "capabilities",
        sa.Column("id", sa.String(length=64), nullable=False),
        sa.Column("name", sa.String(length=64), nullable=False),
        sa.Column("category", sa.String(length=32), nullable=False),
        sa.Column("default_risk_level", sa.String(length=32), nullable=False),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("is_active", sa.Boolean(), server_default=sa.true(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("name"),
    )
    op.create_index("ix_capabilities_name", "capabilities", ["name"], unique=True)
    op.create_index("ix_capabilities_category", "capabilities", ["category"])
    op.create_index("ix_capabilities_risk_level", "capabilities", ["default_risk_level"])

    # Seed core capabilities
    op.bulk_insert(
        capabilities_table,
        [
            {
                **cap,
                "created_at": now,
                "updated_at": now,
            }
            for cap in CORE_CAPABILITIES
        ],
    )

    # 2. user_permissions table
    op.create_table(
        "user_permissions",
        sa.Column("id", sa.String(length=64), nullable=False),
        sa.Column("user_id", sa.String(length=64), nullable=False),
        sa.Column("capability_name", sa.String(length=64), nullable=False),
        sa.Column("scope", sa.String(length=32), nullable=False),  # ONE_TIME, SESSION, STANDING
        sa.Column("resource_pattern", sa.Text(), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_user_permissions_user_id", "user_permissions", ["user_id"])
    op.create_index("ix_user_permissions_capability_name", "user_permissions", ["capability_name"])
    op.create_index(
        "ix_user_permissions_user_cap", "user_permissions", ["user_id", "capability_name"]
    )

    # 3. approval_requests table
    op.create_table(
        "approval_requests",
        sa.Column("id", sa.String(length=64), nullable=False),
        sa.Column("user_id", sa.String(length=64), nullable=False),
        sa.Column("task_id", sa.String(length=64), nullable=True),
        sa.Column("step_id", sa.String(length=64), nullable=True),
        sa.Column("capability_name", sa.String(length=64), nullable=False),
        sa.Column("action_category", sa.String(length=32), nullable=False),
        sa.Column("risk_level", sa.String(length=32), nullable=False),
        sa.Column("reason", sa.Text(), nullable=False),
        sa.Column("affected_resources", sa.JSON(), server_default="[]", nullable=False),
        sa.Column("parameters", sa.JSON(), server_default="{}", nullable=False),
        sa.Column("status", sa.String(length=32), server_default="PENDING", nullable=False),
        sa.Column("approved_scope", sa.String(length=32), nullable=True),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("resolved_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["task_id"], ["task_dags.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_approval_requests_user_id", "approval_requests", ["user_id"])
    op.create_index("ix_approval_requests_task_id", "approval_requests", ["task_id"])
    op.create_index("ix_approval_requests_status", "approval_requests", ["status"])
    op.create_index("ix_approval_requests_user_status", "approval_requests", ["user_id", "status"])

    # 4. Enhance audit_logs with policy and capability fields
    with op.batch_alter_table("audit_logs") as batch_op:
        batch_op.alter_column("session_id", existing_type=sa.String(length=64), nullable=True)
        batch_op.add_column(
            sa.Column(
                "event_type",
                sa.String(length=32),
                server_default="POLICY_CHECK",
                nullable=False,
            )
        )
        batch_op.add_column(sa.Column("capability_name", sa.String(length=64), nullable=True))
        batch_op.add_column(sa.Column("details", sa.JSON(), server_default="{}", nullable=False))
        batch_op.add_column(sa.Column("ip_address", sa.String(length=64), nullable=True))
        batch_op.add_column(
            sa.Column("status", sa.String(length=32), server_default="SUCCESS", nullable=False)
        )
        batch_op.add_column(sa.Column("timestamp", sa.DateTime(timezone=True), nullable=True))
        batch_op.create_index("ix_audit_logs_event_type", ["event_type"])
        batch_op.create_index("ix_audit_logs_capability_name", ["capability_name"])
        batch_op.create_index("ix_audit_logs_status", ["status"])


def downgrade() -> None:
    # 4. Remove columns from audit_logs
    op.execute("DROP TABLE IF EXISTS _alembic_tmp_audit_logs")
    with op.batch_alter_table("audit_logs") as batch_op:
        batch_op.drop_index("ix_audit_logs_status")
        batch_op.drop_index("ix_audit_logs_capability_name")
        batch_op.drop_index("ix_audit_logs_event_type")
        batch_op.drop_column("timestamp")
        batch_op.drop_column("status")
        batch_op.drop_column("ip_address")
        batch_op.drop_column("details")
        batch_op.drop_column("capability_name")
        batch_op.drop_column("event_type")
        batch_op.alter_column("session_id", existing_type=sa.String(length=64), nullable=False)

    # 3. Drop approval_requests
    op.drop_index("ix_approval_requests_user_status", table_name="approval_requests")
    op.drop_index("ix_approval_requests_status", table_name="approval_requests")
    op.drop_index("ix_approval_requests_task_id", table_name="approval_requests")
    op.drop_index("ix_approval_requests_user_id", table_name="approval_requests")
    op.drop_table("approval_requests")

    # 2. Drop user_permissions
    op.drop_index("ix_user_permissions_user_cap", table_name="user_permissions")
    op.drop_index("ix_user_permissions_capability_name", table_name="user_permissions")
    op.drop_index("ix_user_permissions_user_id", table_name="user_permissions")
    op.drop_table("user_permissions")

    # 1. Drop capabilities
    op.drop_index("ix_capabilities_risk_level", table_name="capabilities")
    op.drop_index("ix_capabilities_category", table_name="capabilities")
    op.drop_index("ix_capabilities_name", table_name="capabilities")
    op.drop_table("capabilities")
