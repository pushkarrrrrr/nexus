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
    Index,
    Integer,
    String,
    Text,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship
from sqlalchemy.types import TypeDecorator

from packages.config.nexus_config import get_settings

PgVector: Any
try:
    from pgvector.sqlalchemy import Vector as PgVector
except ImportError:
    PgVector = None


class VectorType(TypeDecorator):
    """Unified dialect-aware Vector column.

    Uses pgvector.sqlalchemy.Vector on PostgreSQL, and sa.JSON on SQLite.
    Embedding dimension defaults dynamically to settings.EMBEDDING_DIMENSION.
    """

    impl = JSON
    cache_ok = True

    def __init__(self, dim: int | None = None, *args: Any, **kwargs: Any) -> None:
        if dim is None:
            settings = get_settings()
            dim = getattr(settings, "embedding_dimension", 1536)
        self.dim = dim
        super().__init__(*args, **kwargs)

    def load_dialect_impl(self, dialect: Any) -> Any:
        if dialect.name == "postgresql" and PgVector is not None:
            return dialect.type_descriptor(PgVector(self.dim))
        return dialect.type_descriptor(JSON())

    def process_bind_param(self, value: Any, dialect: Any) -> Any:
        if value is None:
            return None
        if isinstance(value, (list, tuple)):
            return list(value)
        return value

    def process_result_value(self, value: Any, dialect: Any) -> Any:
        if value is None:
            return None
        if hasattr(value, "tolist"):
            return value.tolist()
        return list(value)


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
    goals: Mapped[list["GoalModel"]] = relationship(
        "GoalModel", back_populates="user", cascade="all, delete-orphan"
    )
    documents: Mapped[list["DocumentModel"]] = relationship(
        "DocumentModel", back_populates="user", cascade="all, delete-orphan"
    )
    knowledge_nodes: Mapped[list["KnowledgeNodeModel"]] = relationship(
        "KnowledgeNodeModel", back_populates="user", cascade="all, delete-orphan"
    )
    knowledge_edges: Mapped[list["KnowledgeEdgeModel"]] = relationship(
        "KnowledgeEdgeModel", back_populates="user", cascade="all, delete-orphan"
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

    id: Mapped[str] = mapped_column(
        String(64), primary_key=True, default=lambda: generate_uuid("sess")
    )
    user_id: Mapped[str | None] = mapped_column(
        String(64), ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True
    )
    surface: Mapped[str] = mapped_column(String(32), nullable=False)  # dashboard, ambient
    title: Mapped[str | None] = mapped_column(String(255), nullable=True)
    os_context: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, onupdate=utcnow, nullable=False
    )

    user: Mapped["UserModel | None"] = relationship("UserModel", back_populates="sessions")
    dags: Mapped[list["TaskDAGModel"]] = relationship(
        "TaskDAGModel", back_populates="session", cascade="all, delete-orphan"
    )
    goals: Mapped[list["GoalModel"]] = relationship(
        "GoalModel", back_populates="session", cascade="all, delete-orphan"
    )
    audit_logs: Mapped[list["AuditLogModel"]] = relationship(
        "AuditLogModel", back_populates="session", cascade="all, delete-orphan"
    )

    def __init__(self, **kwargs: Any) -> None:
        super().__init__(**kwargs)
        if getattr(self, "id", None) is None:
            self.id = generate_uuid("sess")
        if getattr(self, "os_context", None) is None:
            self.os_context = {}
        if getattr(self, "created_at", None) is None:
            self.created_at = utcnow()
        if getattr(self, "updated_at", None) is None:
            self.updated_at = utcnow()


class TaskDAGModel(Base):
    __tablename__ = "task_dags"

    id: Mapped[str] = mapped_column(
        String(64), primary_key=True, default=lambda: generate_uuid("dag")
    )
    user_id: Mapped[str | None] = mapped_column(
        String(64), ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True
    )
    session_id: Mapped[str] = mapped_column(
        String(64), ForeignKey("sessions.id", ondelete="CASCADE"), nullable=False
    )
    goal: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(String(32), default="pending", nullable=False)
    execution_metadata: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, nullable=False
    )
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    session: Mapped["SessionModel"] = relationship("SessionModel", back_populates="dags")
    nodes: Mapped[list["DAGNodeModel"]] = relationship(
        "DAGNodeModel", back_populates="dag", cascade="all, delete-orphan"
    )
    events: Mapped[list["TaskEventModel"]] = relationship(
        "TaskEventModel", back_populates="dag", cascade="all, delete-orphan"
    )

    def __init__(self, **kwargs: Any) -> None:
        super().__init__(**kwargs)
        if getattr(self, "id", None) is None:
            self.id = generate_uuid("dag")
        if getattr(self, "status", None) is None:
            self.status = "pending"
        if getattr(self, "execution_metadata", None) is None:
            self.execution_metadata = {}
        if getattr(self, "created_at", None) is None:
            self.created_at = utcnow()


class DAGNodeModel(Base):
    __tablename__ = "dag_nodes"

    id: Mapped[str] = mapped_column(
        String(64), primary_key=True, default=lambda: generate_uuid("step")
    )
    dag_id: Mapped[str] = mapped_column(
        String(64), ForeignKey("task_dags.id", ondelete="CASCADE"), nullable=False
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    agent_name: Mapped[str] = mapped_column(String(64), nullable=False)
    tool_name: Mapped[str | None] = mapped_column(String(64), nullable=True)
    input_payload: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)
    dependencies: Mapped[list[str]] = mapped_column(JSON, default=list, nullable=False)
    status: Mapped[str] = mapped_column(String(32), default="pending", nullable=False)
    result_payload: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    retry_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)

    dag: Mapped["TaskDAGModel"] = relationship("TaskDAGModel", back_populates="nodes")
    events: Mapped[list["TaskEventModel"]] = relationship("TaskEventModel", back_populates="node")

    def __init__(self, **kwargs: Any) -> None:
        super().__init__(**kwargs)
        if getattr(self, "id", None) is None:
            self.id = generate_uuid("step")
        if getattr(self, "status", None) is None:
            self.status = "pending"
        if getattr(self, "dependencies", None) is None:
            self.dependencies = []
        if getattr(self, "retry_count", None) is None:
            self.retry_count = 0


class TaskEventModel(Base):
    __tablename__ = "task_events"

    id: Mapped[str] = mapped_column(
        String(64), primary_key=True, default=lambda: generate_uuid("tevt")
    )
    dag_id: Mapped[str] = mapped_column(
        String(64), ForeignKey("task_dags.id", ondelete="CASCADE"), nullable=False, index=True
    )
    node_id: Mapped[str | None] = mapped_column(
        String(64), ForeignKey("dag_nodes.id", ondelete="SET NULL"), nullable=True
    )
    event_type: Mapped[str] = mapped_column(String(64), nullable=False)
    from_state: Mapped[str | None] = mapped_column(String(32), nullable=True)
    to_state: Mapped[str | None] = mapped_column(String(32), nullable=True)
    message: Mapped[str] = mapped_column(Text, nullable=False)
    payload: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, nullable=False
    )

    dag: Mapped["TaskDAGModel"] = relationship("TaskDAGModel", back_populates="events")
    node: Mapped["DAGNodeModel | None"] = relationship("DAGNodeModel", back_populates="events")

    def __init__(self, **kwargs: Any) -> None:
        super().__init__(**kwargs)
        if getattr(self, "id", None) is None:
            self.id = generate_uuid("tevt")
        if getattr(self, "payload", None) is None:
            self.payload = {}
        if getattr(self, "created_at", None) is None:
            self.created_at = utcnow()


class GoalModel(Base):
    __tablename__ = "goals"

    id: Mapped[str] = mapped_column(
        String(64), primary_key=True, default=lambda: generate_uuid("goal")
    )
    user_id: Mapped[str] = mapped_column(
        String(64), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    session_id: Mapped[str | None] = mapped_column(
        String(64), ForeignKey("sessions.id", ondelete="SET NULL"), nullable=True, index=True
    )
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(String(32), default="active", nullable=False)
    category: Mapped[str] = mapped_column(String(64), default="general", nullable=False)
    progress: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    milestones: Mapped[list[dict[str, Any]]] = mapped_column(JSON, default=list, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, onupdate=utcnow, nullable=False
    )

    user: Mapped["UserModel"] = relationship("UserModel", back_populates="goals")
    session: Mapped["SessionModel | None"] = relationship("SessionModel", back_populates="goals")

    def __init__(self, **kwargs: Any) -> None:
        super().__init__(**kwargs)
        if getattr(self, "id", None) is None:
            self.id = generate_uuid("goal")
        if getattr(self, "status", None) is None:
            self.status = "active"
        if getattr(self, "category", None) is None:
            self.category = "general"
        if getattr(self, "progress", None) is None:
            self.progress = 0.0
        if getattr(self, "milestones", None) is None:
            self.milestones = []
        if getattr(self, "created_at", None) is None:
            self.created_at = utcnow()
        if getattr(self, "updated_at", None) is None:
            self.updated_at = utcnow()


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

    id: Mapped[str] = mapped_column(
        String(64), primary_key=True, default=lambda: generate_uuid("mem")
    )
    user_id: Mapped[str | None] = mapped_column(
        String(64), ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True
    )
    memory_class: Mapped[str] = mapped_column(String(32), nullable=False)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    source_session_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    confidence: Mapped[float] = mapped_column(Float, default=1.0, nullable=False)
    enabled: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    tags: Mapped[list[str]] = mapped_column(JSON, default=list, nullable=False)
    embedding: Mapped[list[float] | None] = mapped_column(VectorType(), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, onupdate=utcnow, nullable=False
    )

    knowledge_nodes: Mapped[list["KnowledgeNodeModel"]] = relationship(
        "KnowledgeNodeModel", back_populates="memory"
    )


class SessionGrantModel(Base):
    __tablename__ = "session_grants"

    id = Column(String(64), primary_key=True, default=lambda: generate_uuid("grant"))
    session_id = Column(String(64), ForeignKey("sessions.id", ondelete="CASCADE"), nullable=False)
    tool_name = Column(String(64), nullable=False)
    pattern = Column(Text, nullable=False)
    granted_at = Column(DateTime(timezone=True), default=utcnow, nullable=False)
    expires_at = Column(DateTime(timezone=True), nullable=False)


class DocumentModel(Base):
    __tablename__ = "documents"

    id: Mapped[str] = mapped_column(
        String(64), primary_key=True, default=lambda: generate_uuid("doc")
    )
    user_id: Mapped[str] = mapped_column(
        String(64), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    filename: Mapped[str] = mapped_column(String(255), nullable=False)
    file_type: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    file_size_bytes: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    sha256: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    chunk_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="pending", index=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    doc_metadata: Mapped[dict[str, Any]] = mapped_column(
        "metadata", JSON, default=dict, nullable=False
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, onupdate=utcnow, nullable=False
    )

    user: Mapped["UserModel"] = relationship("UserModel", back_populates="documents")
    chunks: Mapped[list["DocumentChunkModel"]] = relationship(
        "DocumentChunkModel", back_populates="document", cascade="all, delete-orphan"
    )
    knowledge_nodes: Mapped[list["KnowledgeNodeModel"]] = relationship(
        "KnowledgeNodeModel", back_populates="document"
    )


class DocumentChunkModel(Base):
    __tablename__ = "document_chunks"

    id: Mapped[str] = mapped_column(
        String(64), primary_key=True, default=lambda: generate_uuid("chk")
    )
    document_id: Mapped[str] = mapped_column(
        String(64), ForeignKey("documents.id", ondelete="CASCADE"), nullable=False, index=True
    )
    chunk_index: Mapped[int] = mapped_column(Integer, nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    page_number: Mapped[int | None] = mapped_column(Integer, nullable=True)
    char_start: Mapped[int | None] = mapped_column(Integer, nullable=True)
    char_end: Mapped[int | None] = mapped_column(Integer, nullable=True)
    embedding: Mapped[list[float] | None] = mapped_column(VectorType(), nullable=True)
    chunk_metadata: Mapped[dict[str, Any]] = mapped_column(
        "metadata", JSON, default=dict, nullable=False
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, nullable=False
    )

    document: Mapped["DocumentModel"] = relationship("DocumentModel", back_populates="chunks")


class KnowledgeNodeModel(Base):
    __tablename__ = "knowledge_nodes"
    __table_args__ = (
        Index("ix_knowledge_nodes_user_type", "user_id", "node_type"),
        Index("ix_knowledge_nodes_user_label", "user_id", "label"),
    )

    id: Mapped[str] = mapped_column(
        String(64), primary_key=True, default=lambda: generate_uuid("node")
    )
    user_id: Mapped[str] = mapped_column(
        String(64), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    label: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    node_type: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    properties: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict, nullable=False)
    document_id: Mapped[str | None] = mapped_column(
        String(64), ForeignKey("documents.id", ondelete="SET NULL"), nullable=True, index=True
    )
    memory_id: Mapped[str | None] = mapped_column(
        String(64), ForeignKey("memories.id", ondelete="SET NULL"), nullable=True, index=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, onupdate=utcnow, nullable=False
    )

    user: Mapped["UserModel"] = relationship("UserModel", back_populates="knowledge_nodes")
    document: Mapped["DocumentModel | None"] = relationship(
        "DocumentModel", back_populates="knowledge_nodes"
    )
    memory: Mapped["MemoryModel | None"] = relationship(
        "MemoryModel", back_populates="knowledge_nodes"
    )
    outgoing_edges: Mapped[list["KnowledgeEdgeModel"]] = relationship(
        "KnowledgeEdgeModel",
        foreign_keys="KnowledgeEdgeModel.source_node_id",
        back_populates="source_node",
        cascade="all, delete-orphan",
    )
    incoming_edges: Mapped[list["KnowledgeEdgeModel"]] = relationship(
        "KnowledgeEdgeModel",
        foreign_keys="KnowledgeEdgeModel.target_node_id",
        back_populates="target_node",
        cascade="all, delete-orphan",
    )


class KnowledgeEdgeModel(Base):
    __tablename__ = "knowledge_edges"
    __table_args__ = (
        Index("ix_knowledge_edges_source_rel", "source_node_id", "relation_type"),
        Index("ix_knowledge_edges_target_rel", "target_node_id", "relation_type"),
        Index("ix_knowledge_edges_user_rel", "user_id", "relation_type"),
    )

    id: Mapped[str] = mapped_column(
        String(64), primary_key=True, default=lambda: generate_uuid("edge")
    )
    user_id: Mapped[str] = mapped_column(
        String(64), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    source_node_id: Mapped[str] = mapped_column(
        String(64),
        ForeignKey("knowledge_nodes.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    target_node_id: Mapped[str] = mapped_column(
        String(64),
        ForeignKey("knowledge_nodes.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    relation_type: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    weight: Mapped[float] = mapped_column(Float, default=1.0, nullable=False)
    properties: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, nullable=False
    )

    user: Mapped["UserModel"] = relationship("UserModel", back_populates="knowledge_edges")
    source_node: Mapped["KnowledgeNodeModel"] = relationship(
        "KnowledgeNodeModel",
        foreign_keys=[source_node_id],
        back_populates="outgoing_edges",
    )
    target_node: Mapped["KnowledgeNodeModel"] = relationship(
        "KnowledgeNodeModel",
        foreign_keys=[target_node_id],
        back_populates="incoming_edges",
    )
