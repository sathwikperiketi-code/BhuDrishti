"""Append-only audit writes shared by processing, review, and GIS services."""

from __future__ import annotations

from datetime import datetime, timezone
from enum import StrEnum
from typing import Any
from uuid import uuid4

from sqlalchemy.orm import Session

from app.db.models import AuditEventModel


class AuditEventType(StrEnum):
    DOCUMENT_UPLOADED = "DOCUMENT_UPLOADED"
    PROCESSING_STARTED = "PROCESSING_STARTED"
    PREPROCESSING_COMPLETED = "PREPROCESSING_COMPLETED"
    OCR_COMPLETED = "OCR_COMPLETED"
    EXTRACTION_COMPLETED = "EXTRACTION_COMPLETED"
    VALIDATION_COMPLETED = "VALIDATION_COMPLETED"
    CONFLICT_DETECTED = "CONFLICT_DETECTED"
    PROCESSING_FAILED = "PROCESSING_FAILED"
    REVIEW_CREATED = "REVIEW_CREATED"
    REVIEW_ASSIGNED = "REVIEW_ASSIGNED"
    REVIEW_STARTED = "REVIEW_STARTED"
    FIELD_EDITED = "FIELD_EDITED"
    FIELD_ACCEPTED = "FIELD_ACCEPTED"
    FIELD_REJECTED = "FIELD_REJECTED"
    ISSUE_RESOLVED = "ISSUE_RESOLVED"
    REVIEW_RECOMMENDED = "REVIEW_RECOMMENDED"
    RECORD_APPROVED = "RECORD_APPROVED"
    RECORD_REJECTED = "RECORD_REJECTED"
    RECORD_SENT_BACK = "RECORD_SENT_BACK"
    GEOMETRY_IMPORTED = "GEOMETRY_IMPORTED"
    GEOMETRY_REPLACED = "GEOMETRY_REPLACED"
    GEOMETRY_WITHDRAWN = "GEOMETRY_WITHDRAWN"
    GIS_INDEXED = "GIS_INDEXED"


def append_event(
    session: Session,
    *,
    record_id: str,
    actor_id: str,
    actor_role: str,
    event_type: str | AuditEventType,
    description: str,
    document_id: str | None = None,
    metadata: dict[str, Any] | None = None,
) -> AuditEventModel:
    """Stage an audit event in the caller's transaction; never auto-commit."""
    if not record_id or not actor_id or not actor_role or not description:
        raise ValueError("Audit event requires record, actor, role, and description.")
    event = AuditEventModel(
        id=str(uuid4()),
        record_id=record_id,
        document_id=document_id,
        actor_id=actor_id,
        actor_role=actor_role,
        event_type=str(event_type),
        timestamp=datetime.now(timezone.utc),
        description=description,
        event_metadata=dict(metadata or {}),
    )
    session.add(event)
    return event
