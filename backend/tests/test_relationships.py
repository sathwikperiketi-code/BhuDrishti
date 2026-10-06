"""Operational links preserve references and enforce parent existence."""

from __future__ import annotations

from pathlib import Path
from uuid import uuid4

import pytest
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.db.base import Base
from app.db.models import (
    AuditEventModel, DocumentModel, LandRecordModel, NotificationReadModel,
    ParcelIndexModel, ReviewCaseModel,
)
from app.db.session import build_engine


def _document(document_id: str) -> DocumentModel:
    return DocumentModel(
        id=document_id, file_name="source.pdf", mime_type="application/pdf",
        file_size=10, sha256="a" * 64, storage_key=str(uuid4()), page_count=1,
        status="completed", stage="final_routing", attempts=1,
        pages=[], stages=[], processing_metadata={}, ocr_pages=[],
        fields=[], warnings=[],
    )


def test_document_record_review_audit_and_gis_links_are_traversable(tmp_path: Path) -> None:
    engine = build_engine(f"sqlite:///{(tmp_path / 'relationships.db').as_posix()}")
    Base.metadata.create_all(engine)
    document_id, record_id, event_id = str(uuid4()), str(uuid4()), str(uuid4())
    with Session(engine) as session:
        document = _document(document_id)
        record = LandRecordModel(
            id=record_id, source_document_id=document_id, document=document,
            payload={"recordId": record_id}, validation_status="human_review",
        )
        review = ReviewCaseModel(
            id=str(uuid4()), record=record, document=document,
            status="queued", priority="medium", priority_reasons=[],
            original_record={"recordId": record_id}, reviewed_record={"recordId": record_id},
            field_reviews={}, issue_resolutions=[], validation={}, quality_score=50, version=1,
        )
        parcel = ParcelIndexModel(
            record=record, document=document, polygon=None,
            status="review", validation_status="human_review",
            geometry_source="unavailable",
        )
        event = AuditEventModel(
            id=event_id, record_id=record_id, document=document,
            actor_id="system", actor_role="SYSTEM", event_type="REVIEW_CREATED",
            description="Review created.", event_metadata={},
        )
        receipt = NotificationReadModel(user_id="legacy-user", event=event)
        session.add_all([document, record, review, parcel, event, receipt])
        session.commit()
        session.expunge_all()

        fetched = session.get(DocumentModel, document_id)
        assert fetched.records[0].id == record_id
        assert fetched.review_cases[0].record is fetched.records[0]
        assert fetched.parcels[0].record_id == record_id
        assert fetched.audit_events[0].read_receipts[0].event_id == event_id
        assert fetched.records[0].parcel.record_id == record_id
        assert fetched.records[0].parcel.polygon is None
        assert session.execute(text("PRAGMA foreign_key_check")).all() == []
    engine.dispose()


def test_external_reference_id_is_preserved_while_invalid_parent_links_fail(tmp_path: Path) -> None:
    engine = build_engine(f"sqlite:///{(tmp_path / 'constraints.db').as_posix()}")
    Base.metadata.create_all(engine)
    with Session(engine) as session:
        reference = LandRecordModel(
            id=str(uuid4()), source_document_id="legacy-external-reference",
            document_id=None, payload={}, validation_status="pending",
        )
        session.add(reference)
        session.commit()
        assert reference.source_document_id == "legacy-external-reference"
        assert reference.document is None

        session.add(ReviewCaseModel(
            id=str(uuid4()), record_id=str(uuid4()), document_id=str(uuid4()),
            status="queued", priority="medium", priority_reasons=[],
            original_record={}, reviewed_record={}, field_reviews={},
            issue_resolutions=[], validation={}, quality_score=50, version=1,
        ))
        with pytest.raises(IntegrityError):
            session.commit()
        session.rollback()
        assert session.execute(text("PRAGMA foreign_keys")).scalar_one() == 1
    engine.dispose()
