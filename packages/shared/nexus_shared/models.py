"""
SQLAlchemy Declarative Models for NEXUS
Compatible with both PostgreSQL and SQLite
"""

import uuid
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import (
    JSON,
    Boolean,
    Column,
    DateTime,
    Float,
    ForeignKey,
    String,
    Text,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    pass


def utcnow():
    return datetime.now(UTC)


def generate_uuid(prefix: str = "id") -> str:
    return f"{prefix}_{uuid.uuid4().hex[:16]}"


class UserModel(Base):
    __tablename__ = "users"

    id: Mapped[str] = mapped_column(
        String(64), primary_key=True, default=lambda: generate_uuid("usr")
    )
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True, nullable=False)
    hashed_password: Mapped[str] = mapped_column(String(255), nullable=False)
    full_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, onupdate=utcnow, nullable=False
    )

    preferences: Mapped["UserPreferenceModel | None"] = relationship(
        "UserPreferenceModel", back_populates="user", uselist=False, cascade="all, delete-orphan"
    )
    sessions: Mapped[list["SessionModel"]] = relationship(
        "SessionModel", back_populates="user", cascade="all, delete-orphan"
    )


class UserPreferenceModel(Base):
    __tablename__ = "user_preferences"

    id: Mapped[str] = mapped_column(
        String(64), primary_key=True, default=lambda: generate_uuid("pref")
    )
    user_id: Mapped[str] = mapped_column(
        String(64), ForeignKey("users.id", ondelete="CASCADE"), unique=True, nullable=False
    )
    timezone: Mapped[str] = mapped_column(String(64), default="UTC", nullable=False)
    model_preferences: Mapped[dict[str, Any]] = mapped_column(
        JSON,
        default=lambda: {
            "default_provider": "openai",
            "fast_model": "gpt-4o-mini",
            "reasoning_model": "gpt-4o",
            "temperature": 0.2,
        },
        nullable=False,
    )
    permission_preferences: Mapped[dict[str, Any]] = mapped_column(
        JSON,
        default=lambda: {
            "auto_grant_low_risk": True,
            "require_hitl_high_risk": True,
            "session_grant_ttl_minutes": 60,
        },
        nullable=False,
    )
    privacy_settings: Mapped[dict[str, Any]] = mapped_column(
        JSON,
        default=lambda: {
            "store_audit_payloads": True,
            "telemetry_enabled": False,
            "allow_external_rag": False,
        },
        nullable=False,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, onupdate=utcnow, nullable=False
    )

    user: Mapped["UserModel"] = relationship("UserModel", back_populates="preferences")

    def __init__(self, **kwargs: Any) -> None:
        super().__init__(**kwargs)
        if getattr(self, "id", None) is None:
            self.id = generate_uuid("pref")
        if getattr(self, "timezone", None) is None:
            self.timezone = "UTC"
        if getattr(self, "model_preferences", None) is None:
            self.model_preferences = {
                "default_provider": "openai",
                "fast_model": "gpt-4o-mini",
                "reasoning_model": "gpt-4o",
                "temperature": 0.2,
            }
        if getattr(self, "permission_preferences", None) is None:
            self.permission_preferences = {
                "auto_grant_low_risk": True,
                "require_hitl_high_risk": True,
                "session_grant_ttl_minutes": 60,
            }
        if getattr(self, "privacy_settings", None) is None:
            self.privacy_settings = {
                "store_audit_payloads": True,
                "telemetry_enabled": False,
                "allow_external_rag": False,
            }
        if getattr(self, "created_at", None) is None:
            self.created_at = utcnow()
        if getattr(self, "updated_at", None) is None:
            self.updated_at = utcnow()


class SessionModel(Base):
    __tablename__ = "sessions"

    id = Column(String(64), primary_key=True, default=lambda: generate_uuid("sess"))
    user_id = Column(
        String(64), ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True
    )
    surface = Column(String(32), nullable=False)  # dashboard, ambient
    title = Column(String(255), nullable=True)
    os_context = Column(JSON, default=dict)
    created_at = Column(DateTime(timezone=True), default=utcnow, nullable=False)
    updated_at = Column(DateTime(timezone=True), default=utcnow, onupdate=utcnow, nullable=False)

    user = relationship("UserModel", back_populates="sessions")
    dags = relationship("TaskDAGModel", back_populates="session", cascade="all, delete-orphan")
    audit_logs = relationship(
        "AuditLogModel", back_populates="session", cascade="all, delete-orphan"
    )


class TaskDAGModel(Base):
    __tablename__ = "task_dags"

    id = Column(String(64), primary_key=True, default=lambda: generate_uuid("dag"))
    user_id = Column(
        String(64), ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True
    )
    session_id = Column(String(64), ForeignKey("sessions.id", ondelete="CASCADE"), nullable=False)
    goal = Column(Text, nullable=False)
    status = Column(String(32), default="pending", nullable=False)
    created_at = Column(DateTime(timezone=True), default=utcnow, nullable=False)
    completed_at = Column(DateTime(timezone=True), nullable=True)

    session = relationship("SessionModel", back_populates="dags")
    nodes = relationship("DAGNodeModel", back_populates="dag", cascade="all, delete-orphan")


class DAGNodeModel(Base):
    __tablename__ = "dag_nodes"

    id = Column(String(64), primary_key=True, default=lambda: generate_uuid("step"))
    dag_id = Column(String(64), ForeignKey("task_dags.id", ondelete="CASCADE"), nullable=False)
    name = Column(String(255), nullable=False)
    agent_name = Column(String(64), nullable=False)
    tool_name = Column(String(64), nullable=True)
    input_payload = Column(JSON, nullable=True)
    dependencies = Column(JSON, default=list, nullable=False)
    status = Column(String(32), default="pending", nullable=False)
    result_payload = Column(JSON, nullable=True)
    error_message = Column(Text, nullable=True)

    dag = relationship("TaskDAGModel", back_populates="nodes")


class AuditLogModel(Base):
    __tablename__ = "audit_logs"

    id = Column(String(64), primary_key=True, default=lambda: generate_uuid("evt"))
    user_id = Column(
        String(64), ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True
    )
    session_id = Column(String(64), ForeignKey("sessions.id", ondelete="CASCADE"), nullable=False)
    step_id = Column(String(64), nullable=True)
    agent_name = Column(String(64), nullable=False)
    tool_name = Column(String(64), nullable=False)
    action_type = Column(String(32), nullable=False)
    risk_level = Column(String(32), nullable=False)
    inputs = Column(JSON, default=dict, nullable=False)
    outputs = Column(JSON, nullable=True)
    error = Column(Text, nullable=True)
    policy_verdict = Column(String(32), nullable=False)
    approval_id = Column(String(64), nullable=True)
    snapshot_id = Column(String(64), nullable=True)
    duration_ms = Column(Float, default=0.0, nullable=False)
    undone_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), default=utcnow, nullable=False)

    session = relationship("SessionModel", back_populates="audit_logs")


class FileSnapshotModel(Base):
    __tablename__ = "file_snapshots"

    id = Column(String(64), primary_key=True, default=lambda: generate_uuid("snap"))
    audit_event_id = Column(String(64), nullable=False)
    file_path = Column(Text, nullable=False)
    sha256_before = Column(String(64), nullable=False)
    sha256_after = Column(String(64), nullable=True)
    backup_storage_path = Column(Text, nullable=False)
    created_at = Column(DateTime(timezone=True), default=utcnow, nullable=False)
    restored_at = Column(DateTime(timezone=True), nullable=True)


class MemoryModel(Base):
    __tablename__ = "memories"

    id = Column(String(64), primary_key=True, default=lambda: generate_uuid("mem"))
    user_id = Column(
        String(64), ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True
    )
    memory_class = Column(String(32), nullable=False)
    title = Column(String(255), nullable=False)
    content = Column(Text, nullable=False)
    source_session_id = Column(String(64), nullable=True)
    confidence = Column(Float, default=1.0, nullable=False)
    enabled = Column(Boolean, default=True, nullable=False)
    tags = Column(JSON, default=list, nullable=False)
    created_at = Column(DateTime(timezone=True), default=utcnow, nullable=False)
    updated_at = Column(DateTime(timezone=True), default=utcnow, onupdate=utcnow, nullable=False)


class SessionGrantModel(Base):
    __tablename__ = "session_grants"

    id = Column(String(64), primary_key=True, default=lambda: generate_uuid("grant"))
    session_id = Column(String(64), ForeignKey("sessions.id", ondelete="CASCADE"), nullable=False)
    tool_name = Column(String(64), nullable=False)
    pattern = Column(Text, nullable=False)
    granted_at = Column(DateTime(timezone=True), default=utcnow, nullable=False)
    expires_at = Column(DateTime(timezone=True), nullable=False)
