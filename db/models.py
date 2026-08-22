"""SQLAlchemy ORM models for RAG Support Assistant."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone

from sqlalchemy import (
    JSON,
    Boolean,
    CheckConstraint,
    DateTime,
    Float,
    ForeignKey,
    ForeignKeyConstraint,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
    text,
)
from sqlalchemy.dialects.postgresql import UUID, ExcludeConstraint
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship

from db.crypto import EncryptedText


class Base(DeclarativeBase):
    pass


class Session(Base):
    __tablename__ = "sessions"
    __table_args__ = (UniqueConstraint("id", "tenant_id", name="uq_sessions_id_tenant_id"),)

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
    )
    last_access: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
    )
    tenant_id: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        server_default="default",
        index=True,
    )

    messages: Mapped[list["Message"]] = relationship(
        back_populates="session",
        cascade="all, delete-orphan",
    )


class User(Base):
    __tablename__ = "users"
    __table_args__ = (
        UniqueConstraint("sso_provider", "sso_subject_id", name="uq_users_sso_provider_subject_id"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )
    username: Mapped[str] = mapped_column(String(100), unique=True, index=True)
    password_hash: Mapped[str] = mapped_column(String(255))
    role: Mapped[str] = mapped_column(String(20), default="viewer")
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    tenant_id: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        server_default="default",
        index=True,
    )
    sso_provider: Mapped[str | None] = mapped_column(String(32), nullable=True)
    sso_subject_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
    )


class Message(Base):
    __tablename__ = "messages"
    __table_args__ = (
        ForeignKeyConstraint(
            ["session_id", "tenant_id"],
            ["sessions.id", "sessions.tenant_id"],
            ondelete="CASCADE",
            name="fk_messages_session_tenant",
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    session_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    tenant_id: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    role: Mapped[str] = mapped_column(String(20))
    content: Mapped[str] = mapped_column(EncryptedText, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
    )

    session: Mapped["Session"] = relationship(back_populates="messages")


class Trace(Base):
    __tablename__ = "traces"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    started_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
    )
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    final_route: Mapped[str | None] = mapped_column(String(30), nullable=True)
    final_quality: Mapped[float | None] = mapped_column(Float, nullable=True)
    final_relevance: Mapped[float | None] = mapped_column(Float, nullable=True)

    steps: Mapped[list["TraceStep"]] = relationship(
        back_populates="trace",
        cascade="all, delete-orphan",
    )
    feedbacks: Mapped[list["Feedback"]] = relationship(
        back_populates="trace",
        cascade="all, delete-orphan",
    )


class TraceStep(Base):
    __tablename__ = "trace_steps"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    trace_id: Mapped[str] = mapped_column(
        String(64),
        ForeignKey("traces.id", ondelete="CASCADE"),
    )
    step_order: Mapped[int] = mapped_column(Integer)
    node_name: Mapped[str] = mapped_column(String(50))
    prompt_tokens: Mapped[int | None] = mapped_column(Integer, nullable=True)
    completion_tokens: Mapped[int | None] = mapped_column(Integer, nullable=True)
    model_name: Mapped[str | None] = mapped_column(String(100), nullable=True)
    cost_usd: Mapped[float | None] = mapped_column(Float, nullable=True)
    ts: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
    )
    state_json: Mapped[str | None] = mapped_column(Text, nullable=True)

    trace: Mapped["Trace"] = relationship(back_populates="steps")


class Feedback(Base):
    __tablename__ = "feedback"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    trace_id: Mapped[str] = mapped_column(
        String(64),
        ForeignKey("traces.id", ondelete="CASCADE"),
    )
    session_id: Mapped[str | None] = mapped_column(String(100), nullable=True)
    rating: Mapped[str] = mapped_column(String(10))
    reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    ts: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
    )

    trace: Mapped["Trace"] = relationship(back_populates="feedbacks")


class AuditLog(Base):
    __tablename__ = "audit_log"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    ts: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        index=True,
    )
    actor: Mapped[str] = mapped_column(String(100))
    action: Mapped[str] = mapped_column(String(50))
    resource: Mapped[str] = mapped_column(String(200))
    detail: Mapped[str | None] = mapped_column(EncryptedText, nullable=True)
    ip_address: Mapped[str | None] = mapped_column(String(45), nullable=True)
    tenant_id: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        server_default="default",
        index=True,
    )


class EscalatedTicket(Base):
    __tablename__ = "escalated_tickets"
    __table_args__ = (
        UniqueConstraint("idempotency_key", name="uq_escalated_tickets_idempotency_key"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )
    tenant_id: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        server_default="default",
        index=True,
    )
    session_id: Mapped[str] = mapped_column(String(100), index=True)
    user_question: Mapped[str] = mapped_column(EncryptedText, nullable=False)
    ai_draft: Mapped[str | None] = mapped_column(EncryptedText, nullable=True)
    operator_response: Mapped[str | None] = mapped_column(EncryptedText, nullable=True)
    status: Mapped[str] = mapped_column(String(20), default="open", index=True)
    # Plan §4.3: durable escalation metadata (idempotent service + delivery state).
    idempotency_key: Mapped[str | None] = mapped_column(String(64), nullable=True, index=True)
    source: Mapped[str | None] = mapped_column(String(40), nullable=True)
    trace_id: Mapped[str | None] = mapped_column(String(100), nullable=True)
    delivery_state: Mapped[str] = mapped_column(
        String(20),
        default="pending",
        server_default="pending",
    )
    delivery_error: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
    )
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class EvalResult(Base):
    __tablename__ = "eval_results"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        index=True,
    )
    metric_name: Mapped[str] = mapped_column(String(50), index=True)
    value: Mapped[float] = mapped_column(Float)
    sample_size: Mapped[int] = mapped_column(Integer)
    drift_alert: Mapped[bool] = mapped_column(Boolean, default=False)
    kind: Mapped[str] = mapped_column(String(30), default="nightly", index=True)
    run_id: Mapped[str | None] = mapped_column(String(64), nullable=True, unique=True)
    baseline_experiment_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    candidate_experiment_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    report_path: Mapped[str | None] = mapped_column(String(255), nullable=True)


class KnowledgeGap(Base):
    __tablename__ = "knowledge_gaps"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    tenant_id: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        server_default="default",
        index=True,
    )
    cluster_id: Mapped[str] = mapped_column(String(64), index=True)
    topic_summary: Mapped[str] = mapped_column(Text)
    sample_questions: Mapped[list[str]] = mapped_column(JSON)
    question_count: Mapped[int] = mapped_column(Integer)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        index=True,
    )
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class KbDraft(Base):
    __tablename__ = "kb_drafts"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )
    tenant_id: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        server_default="default",
        index=True,
    )
    topic: Mapped[str] = mapped_column(String(255), nullable=False)
    draft_content: Mapped[str] = mapped_column(Text, nullable=False)
    source_ticket_ids: Mapped[list[str]] = mapped_column(JSON)
    status: Mapped[str] = mapped_column(String(20), default="pending", index=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        index=True,
    )
    reviewed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class DocumentStats(Base):
    __tablename__ = "document_stats"
    __table_args__ = (UniqueConstraint("doc_id", "tenant_id", name="uq_document_stats_doc_tenant"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    doc_id: Mapped[str] = mapped_column(String(255), nullable=False)
    tenant_id: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        server_default="default",
        index=True,
    )
    citation_count: Mapped[int] = mapped_column(Integer, default=0)
    last_cited_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class IngestionJob(Base):
    """Durable tenant-owned ingestion job (public job_id identity)."""

    __tablename__ = "ingestion_jobs"
    __table_args__ = (
        CheckConstraint(
            "status IN ('queued', 'running', 'completed', 'failed')",
            name="ck_ingestion_jobs_status",
        ),
        Index("ix_ingestion_jobs_tenant_id_created_at", "tenant_id", "created_at"),
        Index("ix_ingestion_jobs_status", "status"),
        Index("ix_ingestion_jobs_celery_task_id", "celery_task_id"),
        Index(
            "ix_ingestion_jobs_status_lease_expires_at",
            "status",
            "lease_expires_at",
        ),
        # Tenant-scoped upload idempotency; NULL keys stay non-unique.
        Index(
            "uq_ingestion_jobs_tenant_idempotency_key_hash",
            "tenant_id",
            "idempotency_key_hash",
            unique=True,
            postgresql_where=text("idempotency_key_hash IS NOT NULL"),
            sqlite_where=text("idempotency_key_hash IS NOT NULL"),
        ),
        # Lifecycle bind lookup: which jobs published into a collection.
        Index(
            "ix_ingestion_jobs_tenant_id_index_active_collection",
            "tenant_id",
            "index_active_collection",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        # Application-generated; no server default / extension required.
    )
    tenant_id: Mapped[str] = mapped_column(String(50), nullable=False)
    filename: Mapped[str] = mapped_column(String(255), nullable=False)
    source_path: Mapped[str] = mapped_column(String(512), nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="queued")
    error: Mapped[str | None] = mapped_column(Text, nullable=True)
    result: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    celery_task_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    # Opaque worker lease; never expose in public API/logs.
    lease_token: Mapped[str | None] = mapped_column(String(128), nullable=True)
    heartbeat_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    lease_expires_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    # Upload idempotency internals — never public/log/audit.
    idempotency_key_hash: Mapped[str | None] = mapped_column(String(64), nullable=True)
    payload_fingerprint: Mapped[str | None] = mapped_column(String(64), nullable=True)
    source_ready_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    # Durable index lifecycle bind (plan 2.5b). Mirrors result.index_publication
    # active/previous/generation when a versioned publish succeeds; null when
    # no publication was recorded. Never deletes job-objects or index data.
    index_active_collection: Mapped[str | None] = mapped_column(
        String(255),
        nullable=True,
    )
    index_previous_collection: Mapped[str | None] = mapped_column(
        String(255),
        nullable=True,
    )
    index_manifest_generation: Mapped[int | None] = mapped_column(
        Integer,
        nullable=True,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class ResolutionSupportCase(Base):
    """Durable tenant-owned support-case aggregate."""

    __tablename__ = "support_cases"
    __table_args__ = (
        UniqueConstraint("id", "tenant_id", name="uq_support_cases_id_tenant"),
        CheckConstraint("version >= 1", name="ck_support_cases_version_positive"),
        Index("ix_support_cases_tenant_status", "tenant_id", "status"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True)
    tenant_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    contract_id: Mapped[str] = mapped_column(String(128), nullable=False)
    contract_version: Mapped[str] = mapped_column(String(128), nullable=False)
    contract_digest: Mapped[str] = mapped_column(String(64), nullable=False)
    correlation_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False)
    version: Mapped[int] = mapped_column(Integer, nullable=False)
    opened_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    effective_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class ResolutionCaseEvent(Base):
    """Append-only case event persisted with its resulting case version."""

    __tablename__ = "case_events"
    __table_args__ = (
        ForeignKeyConstraint(
            ["case_id", "tenant_id"],
            ["support_cases.id", "support_cases.tenant_id"],
            ondelete="RESTRICT",
            name="fk_case_events_case_owner",
        ),
        UniqueConstraint(
            "tenant_id",
            "case_id",
            "sequence",
            name="uq_case_events_tenant_case_sequence",
        ),
        UniqueConstraint(
            "tenant_id",
            "case_id",
            "case_version",
            name="uq_case_events_tenant_case_version",
        ),
        UniqueConstraint(
            "tenant_id",
            "case_id",
            "command_id",
            name="uq_case_events_tenant_case_command",
        ),
        CheckConstraint("sequence >= 1", name="ck_case_events_sequence_positive"),
        CheckConstraint("case_version >= 1", name="ck_case_events_version_positive"),
        CheckConstraint("sequence = case_version", name="ck_case_events_sequence_version"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True)
    tenant_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    case_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    sequence: Mapped[int] = mapped_column(Integer, nullable=False)
    case_version: Mapped[int] = mapped_column(Integer, nullable=False)
    event_type: Mapped[str] = mapped_column(String(32), nullable=False)
    command_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    actor_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    correlation_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    from_status: Mapped[str | None] = mapped_column(String(32), nullable=True)
    to_status: Mapped[str] = mapped_column(String(32), nullable=False)
    reason_code: Mapped[str] = mapped_column(String(64), nullable=False)
    occurred_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    recorded_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class ResolutionEvidenceSnapshot(Base):
    """Immutable evidence metadata and protected-content reference."""

    __tablename__ = "evidence_snapshots"
    __table_args__ = (
        UniqueConstraint("id", "tenant_id", name="uq_evidence_snapshots_id_tenant"),
        CheckConstraint(
            "valid_to IS NULL OR valid_to > valid_from",
            name="ck_evidence_snapshots_valid_range",
        ),
        CheckConstraint(
            "((reference_storage = 'development_file' AND "
            "(encryption_profile IS NULL OR "
            "encryption_profile = 'tenant-envelope-v1')) OR "
            "(reference_storage IN ('postgres_encrypted', 'object_store') AND "
            "encryption_profile IS NOT NULL AND "
            "encryption_profile = 'tenant-envelope-v1'))",
            name="ck_evidence_snapshots_protection_profile",
        ),
        Index(
            "ix_evidence_snapshots_tenant_logical_key",
            "tenant_id",
            "logical_key",
            "applicability_key",
        ),
        ExcludeConstraint(
            ("tenant_id", "="),
            ("logical_key", "="),
            ("applicability_key", "="),
            ("authority", "="),
            (text("tstzrange(valid_from, valid_to, '[)')"), "&&"),
            name="ex_evidence_snapshots_temporal_identity",
        ).ddl_if(dialect="postgresql"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True)
    tenant_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    logical_key: Mapped[str] = mapped_column(String(256), nullable=False)
    source_type: Mapped[str] = mapped_column(String(32), nullable=False)
    source_id: Mapped[str] = mapped_column(String(256), nullable=False)
    source_version: Mapped[str] = mapped_column(String(256), nullable=False)
    content_digest: Mapped[str] = mapped_column(String(64), nullable=False)
    valid_from: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    valid_to: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    recorded_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    authority: Mapped[str] = mapped_column(String(128), nullable=False)
    applicability_key: Mapped[str] = mapped_column(String(256), nullable=False)
    visibility: Mapped[str] = mapped_column(String(32), nullable=False)
    reference_storage: Mapped[str] = mapped_column(String(32), nullable=False)
    reference_locator: Mapped[str] = mapped_column(EncryptedText, nullable=False)
    encryption_profile: Mapped[str | None] = mapped_column(String(128), nullable=True)
    redaction_profile: Mapped[str] = mapped_column(String(128), nullable=False)
    retention_class: Mapped[str] = mapped_column(String(128), nullable=False)


class ResolutionEvidenceLink(Base):
    """Append-only relation from a case version to an evidence snapshot."""

    __tablename__ = "case_evidence_links"
    __table_args__ = (
        ForeignKeyConstraint(
            ["tenant_id", "case_id", "case_version"],
            ["case_events.tenant_id", "case_events.case_id", "case_events.case_version"],
            ondelete="RESTRICT",
            name="fk_case_evidence_links_case_version_owner",
        ),
        ForeignKeyConstraint(
            ["evidence_id", "tenant_id"],
            ["evidence_snapshots.id", "evidence_snapshots.tenant_id"],
            ondelete="RESTRICT",
            name="fk_case_evidence_links_evidence_owner",
        ),
        CheckConstraint("case_version >= 1", name="ck_case_evidence_links_version_positive"),
        Index(
            "ix_case_evidence_links_tenant_case_version",
            "tenant_id",
            "case_id",
            "case_version",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True)
    tenant_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    case_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    case_version: Mapped[int] = mapped_column(Integer, nullable=False)
    evidence_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    requirement_id: Mapped[str] = mapped_column(String(128), nullable=False)
    purpose: Mapped[str] = mapped_column(String(32), nullable=False)
    gathered_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    freshness: Mapped[str] = mapped_column(String(32), nullable=False)
