"""Persisted prototype analytics and bounded categorized search."""

from __future__ import annotations

from collections import Counter
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from app.contracts.auth import AuthenticatedUser
from app.db.models import AuditEventModel, DocumentModel, LandRecordModel, ReviewCaseModel
from app.db.session import get_db
from app.services.auth import Permission, require_permission
from app.services.legacy_visibility import dataset_audit_condition, dataset_record_ids, visible_document_ids


router = APIRouter(tags=["operations"])
_DISCLAIMER = "Counts come from persisted uploaded records and officer actions in this local prototype, not official statistics."
_ACTIVE_REVIEW = {"queued", "in_progress"}
_ACTIVITY_TITLES = {
    "DOCUMENT_UPLOADED": "Document received",
    "PROCESSING_STARTED": "Processing started",
    "PROCESSING_FAILED": "Processing needs attention",
    "VALIDATION_COMPLETED": "Validation completed",
    "REVIEW_CREATED": "Human review required",
    "REVIEW_ASSIGNED": "Review assigned",
    "RECORD_APPROVED": "Officer verification completed",
    "RECORD_REJECTED": "Record rejected after review",
    "GIS_INDEXED": "Verified record indexed in prototype GIS",
}


def _utc(value: datetime | None) -> datetime | None:
    return value.replace(tzinfo=timezone.utc) if value is not None and value.tzinfo is None else value


def _pct(numerator: int, denominator: int) -> float | None:
    return round(numerator / denominator * 100, 1) if denominator else None


@router.get("/analytics/summary", summary="Operational metrics from persisted prototype data")
def analytics_summary(
    session: Session = Depends(get_db),
    _user: AuthenticatedUser = Depends(require_permission(Permission.RECORD_READ)),
) -> dict:
    documents = session.scalars(select(DocumentModel).where(
        DocumentModel.id.in_(visible_document_ids())
    )).all()
    visible_ids = {doc.id for doc in documents}
    processed = [doc for doc in documents if doc.status == "completed"]
    records = session.scalars(select(LandRecordModel).where(
        LandRecordModel.id.in_(dataset_record_ids("operational"))
    )).all()
    cases = session.scalars(select(ReviewCaseModel).order_by(
        ReviewCaseModel.submitted_at.desc(), ReviewCaseModel.id.desc()
    )).all()
    latest_cases: dict[str, ReviewCaseModel] = {}
    for case in cases:
        if case.document_id not in visible_ids:
            continue
        latest_cases.setdefault(case.record_id, case)
    latest = list(latest_cases.values())
    awaiting_review = sum(case.status in _ACTIVE_REVIEW for case in latest)
    approved = sum(case.status == "approved" for case in latest)
    rejected = sum(case.status == "rejected" for case in latest)
    conflicts = sum(any(
        issue.get("severity") == "error"
        or "mismatch" in str(issue.get("code", ""))
        or "conflict" in str(issue.get("code", ""))
        for issue in (doc.validation or {}).get("issues", [])
    ) for doc in processed)
    review_routed = sum((doc.validation or {}).get("routing") == "human_review" for doc in processed)
    quality_scores = [float((doc.score_breakdown or {})["qualityScore"]) for doc in processed
                      if (doc.score_breakdown or {}).get("qualityScore") is not None]
    today = datetime.now(timezone.utc).date()
    daily = Counter(_utc(doc.processed_at).date().isoformat() for doc in processed if doc.processed_at)
    volume = [
        {"date": (today - timedelta(days=day)).isoformat(),
         "count": daily[(today - timedelta(days=day)).isoformat()]}
        for day in range(13, -1, -1)
    ]
    validation = Counter((doc.validation or {}).get("routing", "unavailable") for doc in processed)
    processing = Counter(doc.status for doc in documents)
    events = session.scalars(
        select(AuditEventModel).where(
            AuditEventModel.event_type.in_(_ACTIVITY_TITLES),
            dataset_audit_condition("operational"),
        )
        .order_by(AuditEventModel.timestamp.desc(), AuditEventModel.id.desc()).limit(10)
    ).all()
    activity = [{
        "id": event.id,
        "eventType": event.event_type,
        "title": _ACTIVITY_TITLES[event.event_type],
        "timestamp": _utc(event.timestamp),
        "href": (f"#/documents?id={event.document_id}"
                 if event.event_type in {"DOCUMENT_UPLOADED", "PROCESSING_STARTED", "PROCESSING_FAILED"}
                 else f"#/review/{event.record_id}" if event.event_type in {"REVIEW_CREATED", "REVIEW_ASSIGNED"}
                 else f"#/records/{event.record_id}"),
    } for event in events]
    return {
        "source": "prototype_persisted_data",
        "disclaimer": _DISCLAIMER,
        "generatedAt": datetime.now(timezone.utc),
        "metrics": {
            "documentsTotal": len(documents),
            "documentsProcessed": len(processed),
            "processingFailed": processing["failed"],
            "recordsTotal": len(records),
            "awaitingReview": awaiting_review,
            "validationConflicts": conflicts,
            "approvedRecords": approved,
            "approvalRate": _pct(approved, approved + rejected),
            "reviewRate": _pct(review_routed, len(processed)),
            "conflictRate": _pct(conflicts, len(processed)),
            "averageQualityScore": round(sum(quality_scores) / len(quality_scores), 1) if quality_scores else None,
        },
        "processingVolume": volume,
        "validationDistribution": [{"status": status, "count": validation[status]}
                                   for status in ("approved", "human_review", "rejected", "unavailable")],
        "processingStatusDistribution": [{"status": status, "count": processing[status]}
                                         for status in ("uploaded", "processing", "completed", "failed")],
        "recentActivity": activity,
        "definitions": {
            "approvalRate": "Latest approved cases divided by latest approved and rejected cases.",
            "reviewRate": "Completed documents routed to human review divided by completed documents.",
            "conflictRate": "Completed documents with at least one error, mismatch, or conflict issue divided by completed documents.",
            "validationConflicts": "Number of completed documents with at least one error, mismatch, or conflict issue.",
        },
    }


def _contains(column, needle: str):
    escaped = needle.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
    return column.ilike(f"%{escaped}%", escape="\\")


@router.get("/search", summary="Categorized record, document, and survey search")
def search(
    q: str = Query(min_length=2, max_length=100),
    session: Session = Depends(get_db),
    _user: AuthenticatedUser = Depends(require_permission(Permission.RECORD_READ)),
) -> dict:
    query = q.strip()
    if len(query) < 2:
        raise HTTPException(status_code=422, detail="Enter at least two non-space characters.")
    record_columns = (
        LandRecordModel.id, LandRecordModel.record_number,
        LandRecordModel.owner_name, LandRecordModel.survey_number,
        LandRecordModel.payload["khataNumber"].as_string(),
        LandRecordModel.payload["village"].as_string(),
        LandRecordModel.district,
    )
    record_statement = select(LandRecordModel).where(
        LandRecordModel.id.in_(dataset_record_ids("operational")),
        or_(*(_contains(column, query) for column in record_columns)),
    ).order_by(LandRecordModel.updated_at.desc(), LandRecordModel.id.desc()).limit(8)
    records = session.scalars(record_statement).all()
    documents = session.scalars(
        select(DocumentModel).where(
            DocumentModel.id.in_(visible_document_ids()),
            or_(_contains(DocumentModel.id, query), _contains(DocumentModel.file_name, query)),
        ).order_by(DocumentModel.uploaded_at.desc(), DocumentModel.id.desc()).limit(6)
    ).all()
    surveys = session.scalars(select(LandRecordModel).where(
        LandRecordModel.id.in_(dataset_record_ids("operational")),
        _contains(LandRecordModel.survey_number, query),
    ).order_by(LandRecordModel.updated_at.desc(), LandRecordModel.id.desc()).limit(6)).all()
    record_items = [{
        "id": row.id, "title": row.record_number or row.id,
        "subtitle": " · ".join(filter(None, [row.owner_name, (row.payload or {}).get("village"), row.district])),
        "href": f"#/records/{row.id}", "recordNumber": row.record_number,
        "ownerName": row.owner_name, "surveyNumber": row.survey_number,
        "khataNumber": (row.payload or {}).get("khataNumber"),
        "village": (row.payload or {}).get("village"), "district": row.district,
    } for row in records]
    document_items = [{
        "id": row.id, "title": row.file_name,
        "subtitle": row.status.replace("_", " ").capitalize(),
        "href": f"#/documents?id={row.id}", "fileName": row.file_name,
        "status": row.status,
    } for row in documents]
    survey_items = [{
        "id": row.id, "title": row.survey_number,
        "subtitle": f"{row.record_number or 'Record'} · {(row.payload or {}).get('village') or row.district or 'Location unavailable'}",
        "href": f"#/records/{row.id}", "recordId": row.id,
    } for row in surveys]
    return {
        "query": query, "total": len(record_items) + len(document_items) + len(survey_items),
        "records": record_items, "documents": document_items, "surveys": survey_items,
    }
