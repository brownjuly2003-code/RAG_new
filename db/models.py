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
from sqlalchemy.dialects.postgresql import JSONB, UUID, ExcludeConstraint
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


class TemporalKnowledgeObject(Base):
    """Immutable tenant-owned identity for one authoritative knowledge source."""

    __tablename__ = "knowledge_objects"
    __table_args__ = (
        UniqueConstraint("id", "tenant_id", name="uq_knowledge_objects_id_tenant"),
        UniqueConstraint(
            "tenant_id",
            "source_id",
            "logical_key",
            name="uq_knowledge_objects_source_identity",
        ),
        CheckConstraint(
            "logical_key = trim(logical_key) AND logical_key <> ''",
            name="ck_knowledge_objects_logical_key",
        ),
        CheckConstraint(
            "source_id = trim(source_id) AND source_id <> ''",
            name="ck_knowledge_objects_source_id",
        ),
        CheckConstraint(
            "owner = trim(owner) AND owner <> ''",
            name="ck_knowledge_objects_owner",
        ),
        CheckConstraint(
            "authority = trim(authority) AND authority <> ''",
            name="ck_knowledge_objects_authority",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True)
    tenant_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    logical_key: Mapped[str] = mapped_column(String(256), nullable=False)
    source_id: Mapped[str] = mapped_column(String(256), nullable=False)
    owner: Mapped[str] = mapped_column(String(128), nullable=False)
    authority: Mapped[str] = mapped_column(String(128), nullable=False)


class TemporalKnowledgeApplicability(Base):
    """Normalized exact-five applicability tuple shared by knowledge versions."""

    __tablename__ = "knowledge_applicability"
    __table_args__ = (
        UniqueConstraint("id", "tenant_id", name="uq_knowledge_applicability_id_tenant"),
        UniqueConstraint(
            "tenant_id",
            "product",
            "region",
            "customer_plan",
            "cargo_type",
            "channel",
            name="uq_knowledge_applicability_exact_dimensions",
        ),
        CheckConstraint(
            "product = trim(product) AND product <> '' AND product NOT LIKE '%*%'",
            name="ck_knowledge_applicability_product",
        ),
        CheckConstraint(
            "region = trim(region) AND region <> '' AND region NOT LIKE '%*%'",
            name="ck_knowledge_applicability_region",
        ),
        CheckConstraint(
            "customer_plan = trim(customer_plan) AND customer_plan <> '' "
            "AND customer_plan NOT LIKE '%*%'",
            name="ck_knowledge_applicability_customer_plan",
        ),
        CheckConstraint(
            "cargo_type = trim(cargo_type) AND cargo_type <> '' AND cargo_type NOT LIKE '%*%'",
            name="ck_knowledge_applicability_cargo_type",
        ),
        CheckConstraint(
            "channel = trim(channel) AND channel <> '' AND channel NOT LIKE '%*%'",
            name="ck_knowledge_applicability_channel",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True)
    tenant_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    product: Mapped[str] = mapped_column(String(128), nullable=False)
    region: Mapped[str] = mapped_column(String(128), nullable=False)
    customer_plan: Mapped[str] = mapped_column(String(128), nullable=False)
    cargo_type: Mapped[str] = mapped_column(String(128), nullable=False)
    channel: Mapped[str] = mapped_column(String(128), nullable=False)


class TemporalKnowledgeVersion(Base):
    """Immutable bitemporal knowledge version with one legal system close."""

    __tablename__ = "knowledge_versions"
    __table_args__ = (
        ForeignKeyConstraint(
            ["object_id", "tenant_id"],
            ["knowledge_objects.id", "knowledge_objects.tenant_id"],
            ondelete="RESTRICT",
            name="fk_knowledge_versions_object_owner",
        ),
        ForeignKeyConstraint(
            ["applicability_id", "tenant_id"],
            ["knowledge_applicability.id", "knowledge_applicability.tenant_id"],
            ondelete="RESTRICT",
            name="fk_knowledge_versions_applicability_owner",
        ),
        UniqueConstraint("id", "tenant_id", name="uq_knowledge_versions_id_tenant"),
        UniqueConstraint(
            "id",
            "tenant_id",
            "object_id",
            name="uq_knowledge_versions_id_tenant_object",
        ),
        UniqueConstraint(
            "id",
            "tenant_id",
            "content_digest",
            name="uq_knowledge_versions_id_tenant_digest",
        ),
        CheckConstraint(
            "source_revision = trim(source_revision) AND source_revision <> ''",
            name="ck_knowledge_versions_source_revision",
        ),
        CheckConstraint(
            "content_digest ~ '^[0-9a-f]{64}$'",
            name="ck_knowledge_versions_content_digest",
        ),
        CheckConstraint(
            "valid_to IS NULL OR valid_to > valid_from",
            name="ck_knowledge_versions_valid_range",
        ),
        CheckConstraint(
            "system_to IS NULL OR system_to > system_from",
            name="ck_knowledge_versions_system_range",
        ),
        CheckConstraint(
            "locale = trim(locale) AND locale <> ''",
            name="ck_knowledge_versions_locale",
        ),
        ExcludeConstraint(
            ("tenant_id", "="),
            ("object_id", "="),
            ("applicability_id", "="),
            ("locale", "="),
            (text("tstzrange(valid_from, valid_to, '[)')"), "&&"),
            (text("tstzrange(system_from, system_to, '[)')"), "&&"),
            name="ex_knowledge_versions_bitemporal_identity",
        ).ddl_if(dialect="postgresql"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True)
    tenant_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    object_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    applicability_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    source_revision: Mapped[str] = mapped_column(String(256), nullable=False)
    content_digest: Mapped[str] = mapped_column(String(64), nullable=False)
    valid_from: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    valid_to: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    system_from: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    system_to: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    locale: Mapped[str] = mapped_column(String(32), nullable=False)


class TemporalKnowledgeSupersession(Base):
    """Immutable relationship between two versions of the same object."""

    __tablename__ = "knowledge_supersessions"
    __table_args__ = (
        ForeignKeyConstraint(
            ["predecessor_version_id", "tenant_id", "object_id"],
            [
                "knowledge_versions.id",
                "knowledge_versions.tenant_id",
                "knowledge_versions.object_id",
            ],
            ondelete="RESTRICT",
            name="fk_knowledge_supersessions_predecessor_owner",
        ),
        ForeignKeyConstraint(
            ["successor_version_id", "tenant_id", "object_id"],
            [
                "knowledge_versions.id",
                "knowledge_versions.tenant_id",
                "knowledge_versions.object_id",
            ],
            ondelete="RESTRICT",
            name="fk_knowledge_supersessions_successor_owner",
        ),
        CheckConstraint(
            "predecessor_version_id <> successor_version_id",
            name="ck_knowledge_supersessions_distinct_versions",
        ),
    )

    tenant_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True)
    predecessor_version_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
    )
    successor_version_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
    )
    object_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    reason: Mapped[str] = mapped_column(String(128), nullable=False)
    recorded_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class TemporalKnowledgeConflict(Base):
    """Immutable material conflict between distinct knowledge authorities."""

    __tablename__ = "knowledge_conflicts"
    __table_args__ = (
        ForeignKeyConstraint(
            ["left_version_id", "tenant_id"],
            ["knowledge_versions.id", "knowledge_versions.tenant_id"],
            ondelete="RESTRICT",
            name="fk_knowledge_conflicts_left_owner",
        ),
        ForeignKeyConstraint(
            ["right_version_id", "tenant_id"],
            ["knowledge_versions.id", "knowledge_versions.tenant_id"],
            ondelete="RESTRICT",
            name="fk_knowledge_conflicts_right_owner",
        ),
        UniqueConstraint("id", "tenant_id", name="uq_knowledge_conflicts_id_tenant"),
        UniqueConstraint(
            "tenant_id",
            "left_version_id",
            "right_version_id",
            name="uq_knowledge_conflicts_version_pair",
        ),
        CheckConstraint(
            "left_version_id < right_version_id",
            name="ck_knowledge_conflicts_canonical_pair",
        ),
        CheckConstraint(
            "status IN ('unresolved', 'resolved')",
            name="ck_knowledge_conflicts_status",
        ),
        CheckConstraint(
            "fact_key = trim(fact_key) AND fact_key <> ''",
            name="ck_knowledge_conflicts_fact_key",
        ),
        CheckConstraint(
            "owner = trim(owner) AND owner <> ''",
            name="ck_knowledge_conflicts_owner",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True)
    tenant_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    fact_key: Mapped[str] = mapped_column(String(256), nullable=False)
    left_version_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    right_version_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    status: Mapped[str] = mapped_column(String(16), nullable=False)
    owner: Mapped[str] = mapped_column(String(128), nullable=False)


class TemporalKnowledgeProjectionBinding(Base):
    """Immutable binding between a Chroma generation and knowledge versions."""

    __tablename__ = "knowledge_projection_bindings"
    __table_args__ = (
        UniqueConstraint(
            "id",
            "tenant_id",
            name="uq_knowledge_projection_bindings_id_tenant",
        ),
        UniqueConstraint(
            "tenant_id",
            "manifest_generation",
            name="uq_knowledge_projection_bindings_generation",
        ),
        UniqueConstraint(
            "tenant_id",
            "digest",
            name="uq_knowledge_projection_bindings_digest",
        ),
        CheckConstraint(
            "active_collection ~ '^[A-Za-z0-9](?:[A-Za-z0-9._-]*[A-Za-z0-9])?$'",
            name="ck_knowledge_projection_bindings_collection",
        ),
        CheckConstraint(
            "manifest_generation >= 1",
            name="ck_knowledge_projection_bindings_generation",
        ),
        CheckConstraint(
            "embedding_model = trim(embedding_model) AND embedding_model <> ''",
            name="ck_knowledge_projection_bindings_embedding_model",
        ),
        CheckConstraint(
            "embedding_dimension >= 1",
            name="ck_knowledge_projection_bindings_embedding_dimension",
        ),
        CheckConstraint(
            "index_config_digest ~ '^[0-9a-f]{64}$'",
            name="ck_knowledge_projection_bindings_index_digest",
        ),
        CheckConstraint(
            "digest ~ '^[0-9a-f]{64}$'",
            name="ck_knowledge_projection_bindings_digest",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True)
    tenant_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    active_collection: Mapped[str] = mapped_column(String(63), nullable=False)
    manifest_generation: Mapped[int] = mapped_column(Integer, nullable=False)
    source_versions: Mapped[list[list[str]]] = mapped_column(
        JSON().with_variant(JSONB(), "postgresql"),
        nullable=False,
    )
    embedding_model: Mapped[str] = mapped_column(String(128), nullable=False)
    embedding_dimension: Mapped[int] = mapped_column(Integer, nullable=False)
    index_config_digest: Mapped[str] = mapped_column(String(64), nullable=False)
    digest: Mapped[str] = mapped_column(String(64), nullable=False)
    recorded_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
