"""
SQLAlchemy Declarative Models for NEXUS
Compatible with both PostgreSQL and SQLite
"""

import uuid
from datetime import UTC, datetime

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
from sqlalchemy.orm import declarative_base, relationship

Base = declarative_base()


def utcnow():
    return datetime.now(UTC)


def generate_uuid(prefix: str = "id") -> str:
    return f"{prefix}_{uuid.uuid4().hex[:16]}"


class SessionModel(Base):
    __tablename__ = "sessions"

    id = Column(String(64), primary_key=True, default=lambda: generate_uuid("sess"))
    surface = Column(String(32), nullable=False)  # dashboard, ambient
    title = Column(String(255), nullable=True)
    os_context = Column(JSON, default=dict)
    created_at = Column(DateTime(timezone=True), default=utcnow, nullable=False)
    updated_at = Column(DateTime(timezone=True), default=utcnow, onupdate=utcnow, nullable=False)

    dags = relationship("TaskDAGModel", back_populates="session", cascade="all, delete-orphan")
    audit_logs = relationship(
        "AuditLogModel", back_populates="session", cascade="all, delete-orphan"
    )


class TaskDAGModel(Base):
    __tablename__ = "task_dags"

    id = Column(String(64), primary_key=True, default=lambda: generate_uuid("dag"))
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
