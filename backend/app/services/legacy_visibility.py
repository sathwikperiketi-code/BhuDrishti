"""Dataset selectors for operational and explicitly requested sample reads."""

from __future__ import annotations

from typing import Literal

from sqlalchemy import and_, or_, select
from sqlalchemy.orm import Session

from app.db.models import AuditEventModel, DemoRunModel, DocumentModel, LandRecordModel


Dataset = Literal["operational", "sample"]


def archived_document_ids():
    # Retain legacy markers in the guard for databases created directly from
    # models, or rows imported without running the migration backfill.
    return select(DocumentModel.id).where(or_(
        DocumentModel.dataset_scope == "sample",
        DocumentModel.demo_scenario.is_not(None),
        DocumentModel.id.in_(select(DemoRunModel.document_id)),
    ))


def visible_document_ids():
    return select(DocumentModel.id).where(
        DocumentModel.dataset_scope == "operational",
        DocumentModel.id.not_in(archived_document_ids()),
    )


def dataset_document_ids(dataset: Dataset):
    return archived_document_ids() if dataset == "sample" else visible_document_ids()


def dataset_record_ids(dataset: Dataset):
    """Use the constrained link, with a legacy source-ID fallback if absent."""
    document_ids = dataset_document_ids(dataset)
    return select(LandRecordModel.id).where(or_(
        LandRecordModel.document_id.in_(document_ids),
        and_(LandRecordModel.document_id.is_(None),
             LandRecordModel.source_document_id.in_(document_ids)),
    ))


def dataset_audit_condition(dataset: Dataset):
    """Include record-linked events with no document ID, but no orphan events."""
    document_ids = dataset_document_ids(dataset)
    record_ids = dataset_record_ids(dataset)
    return or_(
        AuditEventModel.document_id.in_(document_ids),
        and_(AuditEventModel.document_id.is_(None), AuditEventModel.record_id.in_(record_ids)),
    )


def archived_document_id_set(session: Session) -> set[str]:
    return set(session.scalars(archived_document_ids()).all())
