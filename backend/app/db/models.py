"""Minimal persistence mapping for the canonical land-record contract."""

from __future__ import annotations

from datetime import datetime
import hashlib
from typing import Any

from sqlalchemy import CheckConstraint, DateTime, Float, ForeignKey, Integer, JSON, String, event, func, inspect
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .base import Base


def _generated_username(context: Any) -> str:
    """Safe fallback for trusted direct model inserts made outside account flows.

    Registration and administrator provisioning set an explicit username. The
    fallback keeps legacy internal fixtures and imports deterministic without
    making an email address or a password part of the generated identity.
    """
    user_id = str(context.get_current_parameters()["id"])
    return f"user_{hashlib.sha256(user_id.encode('utf-8')).hexdigest()[:24]}"


class UserModel(Base):
    """Persisted identity, verification state, and server-controlled role."""

    __tablename__ = "users"
    __table_args__ = (
        CheckConstraint(
            "role IN ('ADMIN', 'REVENUE_OFFICER', 'VERIFIER', 'AUDITOR')", name="ck_users_role",
        ),
        CheckConstraint(
            "status IN ('UNVERIFIED', 'ACTIVE', 'SUSPENDED')", name="ck_users_status",
        ),
        CheckConstraint(
            "requested_role IS NULL OR requested_role IN ('ADMIN', 'REVENUE_OFFICER', 'VERIFIER', 'AUDITOR')",
            name="ck_users_requested_role",
        ),
        CheckConstraint(
            "role_approval_status IS NULL OR role_approval_status IN ('PENDING', 'APPROVED', 'REJECTED')",
            name="ck_users_role_approval_status",
        ),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    email: Mapped[str] = mapped_column(String(254), nullable=False, unique=True, index=True)
    username: Mapped[str] = mapped_column(
        String(32), nullable=False, unique=True, index=True, default=_generated_username,
    )
    name: Mapped[str] = mapped_column(String(160), nullable=False)
    role: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    requested_role: Mapped[str | None] = mapped_column(String(32))
    role_approval_status: Mapped[str | None] = mapped_column(String(16), index=True)
    role_reviewed_by: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("users.id", name="fk_users_role_reviewed_by"),
    )
    role_reviewed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    password_hash: Mapped[str] = mapped_column(String(256), nullable=False)
    is_active: Mapped[bool] = mapped_column(default=False, nullable=False)
    status: Mapped[str] = mapped_column(String(16), nullable=False, index=True, default="UNVERIFIED")
    email_verified_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    failed_login_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    locked_until: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(),
    )
    sessions: Mapped[list["AuthSessionModel"]] = relationship(back_populates="user")
    action_tokens: Mapped[list["AuthActionTokenModel"]] = relationship(back_populates="user")


class AuthActionTokenModel(Base):
    """Single-use email verification and password reset proof.

    Only a cryptographic digest of the bearer token is stored in token_hash.
    """

    __tablename__ = "auth_action_tokens"
    __table_args__ = (CheckConstraint(
        "purpose IN ('EMAIL_VERIFICATION', 'PASSWORD_RESET')", name="ck_auth_action_tokens_purpose",
    ),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    user_id: Mapped[str] = mapped_column(String(36), ForeignKey("users.id"), nullable=False, index=True)
    purpose: Mapped[str] = mapped_column(String(24), nullable=False, index=True)
    token_hash: Mapped[str] = mapped_column(String(64), nullable=False, unique=True, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    used_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    user: Mapped[UserModel] = relationship(back_populates="action_tokens")


class AuthSessionModel(Base):
    """Revocable session record required in addition to a valid signed bearer."""

    __tablename__ = "auth_sessions"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    user_id: Mapped[str] = mapped_column(String(36), ForeignKey("users.id"), nullable=False, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    user: Mapped[UserModel] = relationship(back_populates="sessions")


class AuthSigningKeyModel(Base):
    """Stable local-development signing key when no environment secret is set."""

    __tablename__ = "auth_signing_keys"

    id: Mapped[str] = mapped_column(String(32), primary_key=True)
    secret_hex: Mapped[str] = mapped_column(String(128), nullable=False)


class LandRecordModel(Base):
    """Relational index plus JSON payload for forward-compatible extensions."""

    __tablename__ = "land_records"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    record_number: Mapped[str | None] = mapped_column(String(128), index=True)
    owner_name: Mapped[str | None] = mapped_column(String(256), index=True)
    survey_number: Mapped[str | None] = mapped_column(String(128), index=True)
    area: Mapped[float | None] = mapped_column(Float)
    area_unit: Mapped[str | None] = mapped_column(String(32))
    district: Mapped[str | None] = mapped_column(String(128), index=True)
    state: Mapped[str | None] = mapped_column(String(128), index=True)
    validation_status: Mapped[str] = mapped_column(String(32), default="pending", index=True)
    source_document_id: Mapped[str | None] = mapped_column(String(256), index=True)
    # The legacy source ID also represents external reference inputs. Only an
    # uploaded document receives this constrained link.
    document_id: Mapped[str | None] = mapped_column(String(36), ForeignKey("documents.id"), index=True)
    payload: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )
    document: Mapped["DocumentModel | None"] = relationship(back_populates="records")
    review_cases: Mapped[list["ReviewCaseModel"]] = relationship(back_populates="record")
    parcel: Mapped["ParcelIndexModel | None"] = relationship(back_populates="record")


class DocumentModel(Base):
    """Uploaded source bytes and durable processing state.

    The storage key is generated by the server and never serialized to clients.
    JSON columns retain intermediate evidence for retry and inspection.
    """

    __tablename__ = "documents"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    file_name: Mapped[str] = mapped_column(String(180), nullable=False)
    mime_type: Mapped[str] = mapped_column(String(64), nullable=False)
    file_size: Mapped[int] = mapped_column(Integer, nullable=False)
    sha256: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    storage_key: Mapped[str] = mapped_column(String(36), nullable=False, unique=True)
    page_count: Mapped[int] = mapped_column(Integer, nullable=False)
    dataset_scope: Mapped[str] = mapped_column(String(16), nullable=False, default="operational", server_default="operational", index=True)
    dataset_reason: Mapped[str | None] = mapped_column(String(64))
    language: Mapped[str | None] = mapped_column(String(64))
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="uploaded", index=True)
    stage: Mapped[str] = mapped_column(String(32), nullable=False, default="upload")
    provider: Mapped[str | None] = mapped_column(String(80))
    attempts: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    pages: Mapped[list[dict[str, Any]]] = mapped_column(JSON, nullable=False, default=list)
    stages: Mapped[list[dict[str, Any]]] = mapped_column(JSON, nullable=False, default=list)
    processing_metadata: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False, default=dict)
    ocr_pages: Mapped[list[dict[str, Any]]] = mapped_column(JSON, nullable=False, default=list)
    extraction: Mapped[dict[str, Any] | None] = mapped_column(JSON)
    fields: Mapped[list[dict[str, Any]]] = mapped_column(JSON, nullable=False, default=list)
    validation: Mapped[dict[str, Any] | None] = mapped_column(JSON)
    score_breakdown: Mapped[dict[str, Any] | None] = mapped_column(JSON)
    warnings: Mapped[list[str]] = mapped_column(JSON, nullable=False, default=list)
    error: Mapped[dict[str, str] | None] = mapped_column(JSON)
    uploaded_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )
    processed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    # Retained for historical scenario rows. The operational upload API never
    # sets this marker and uses real text/OCR evidence.
    demo_scenario: Mapped[str | None] = mapped_column(String(64), index=True)
    records: Mapped[list[LandRecordModel]] = relationship(back_populates="document")
    review_cases: Mapped[list["ReviewCaseModel"]] = relationship(back_populates="document")
    parcels: Mapped[list["ParcelIndexModel"]] = relationship(back_populates="document")
    audit_events: Mapped[list["AuditEventModel"]] = relationship(back_populates="document")


class DemoRunModel(Base):
    """Historical presentation run pointer retained for audit visibility."""

    __tablename__ = "demo_runs"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    scenario_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    document_id: Mapped[str] = mapped_column(String(36), nullable=False, unique=True)
    created_by: Mapped[str] = mapped_column(String(64), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    archived_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class NotificationReadModel(Base):
    """Per-user read receipt; source audit events stay append-only."""

    __tablename__ = "notification_reads"

    user_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    event_id: Mapped[str] = mapped_column(String(36), ForeignKey("audit_events.id"), primary_key=True)
    read_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    event: Mapped["AuditEventModel"] = relationship(back_populates="read_receipts")


class ReviewCaseModel(Base):
    """Officer workflow state; original AI output remains an immutable snapshot."""

    __tablename__ = "review_cases"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    record_id: Mapped[str] = mapped_column(String(36), ForeignKey("land_records.id"), nullable=False, index=True)
    document_id: Mapped[str] = mapped_column(String(36), ForeignKey("documents.id"), nullable=False, index=True)
    status: Mapped[str] = mapped_column(String(24), nullable=False, default="queued", index=True)
    priority: Mapped[str] = mapped_column(String(16), nullable=False, default="medium", index=True)
    priority_reasons: Mapped[list[dict[str, Any]]] = mapped_column(JSON, nullable=False, default=list)
    assigned_officer_id: Mapped[str | None] = mapped_column(String(64), index=True)
    original_record: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False)
    reviewed_record: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False)
    field_reviews: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False, default=dict)
    issue_resolutions: Mapped[list[dict[str, Any]]] = mapped_column(JSON, nullable=False, default=list)
    recommendation: Mapped[dict[str, Any] | None] = mapped_column(JSON)
    validation: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False, default=dict)
    quality_score: Mapped[float] = mapped_column(Float, nullable=False)
    primary_conflict: Mapped[str | None] = mapped_column(String(512))
    submitted_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    decided_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    decided_by: Mapped[str | None] = mapped_column(String(64))
    decision_reason: Mapped[str | None] = mapped_column(String(1000))
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    record: Mapped[LandRecordModel] = relationship(back_populates="review_cases")
    document: Mapped[DocumentModel] = relationship(back_populates="review_cases")


@event.listens_for(ReviewCaseModel, "before_update")
def _protect_original_ai_snapshot(_mapper: object, _connection: object, target: ReviewCaseModel) -> None:
    if inspect(target).attrs.original_record.history.has_changes():
        raise ValueError("The original AI extraction snapshot cannot be changed.")


class AuditEventModel(Base):
    """Application-append-only event with actor and before/after metadata."""

    __tablename__ = "audit_events"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    record_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    document_id: Mapped[str | None] = mapped_column(String(36), ForeignKey("documents.id"), index=True)
    actor_id: Mapped[str] = mapped_column(String(64), nullable=False)
    actor_role: Mapped[str] = mapped_column(String(32), nullable=False)
    event_type: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    timestamp: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), index=True)
    description: Mapped[str] = mapped_column(String(1000), nullable=False)
    event_metadata: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False, default=dict)
    document: Mapped[DocumentModel | None] = relationship(back_populates="audit_events")
    read_receipts: Mapped[list[NotificationReadModel]] = relationship(back_populates="event")


@event.listens_for(AuditEventModel, "before_update")
def _reject_audit_update(*_: object) -> None:
    raise ValueError("Audit events are append-only.")


@event.listens_for(AuditEventModel, "before_delete")
def _reject_audit_delete(*_: object) -> None:
    raise ValueError("Audit events are append-only.")


class ParcelIndexModel(Base):
    """Processed record metadata with optional officer-sourced parcel geometry."""

    __tablename__ = "parcel_index"

    record_id: Mapped[str] = mapped_column(String(36), ForeignKey("land_records.id"), primary_key=True)
    document_id: Mapped[str | None] = mapped_column(String(36), ForeignKey("documents.id"), index=True)
    record_number: Mapped[str | None] = mapped_column(String(128), index=True)
    survey_number: Mapped[str | None] = mapped_column(String(128), index=True)
    owner_name: Mapped[str | None] = mapped_column(String(256), index=True)
    area: Mapped[float | None] = mapped_column(Float)
    area_unit: Mapped[str | None] = mapped_column(String(32))
    state: Mapped[str | None] = mapped_column(String(128), index=True)
    district: Mapped[str | None] = mapped_column(String(128), index=True)
    village: Mapped[str | None] = mapped_column(String(128), index=True)
    status: Mapped[str] = mapped_column(String(24), nullable=False, default="review", index=True)
    validation_status: Mapped[str] = mapped_column(String(32), nullable=False, default="human_review")
    quality_score: Mapped[float | None] = mapped_column(Float)
    polygon: Mapped[list[list[float]] | None] = mapped_column(JSON)
    geometry_source: Mapped[str] = mapped_column(String(32), nullable=False, default="unavailable")
    geometry_status: Mapped[str] = mapped_column(String(16), nullable=False, default="unavailable")
    geometry_reference: Mapped[str | None] = mapped_column(String(256))
    geometry_file_name: Mapped[str | None] = mapped_column(String(180))
    geometry_sha256: Mapped[str | None] = mapped_column(String(64))
    geometry_recorded_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    geometry_recorded_by: Mapped[str | None] = mapped_column(String(64))
    geometry_storage_key: Mapped[str | None] = mapped_column(String(36))
    indexed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    record: Mapped[LandRecordModel] = relationship(back_populates="parcel")
    document: Mapped[DocumentModel | None] = relationship(back_populates="parcels")
