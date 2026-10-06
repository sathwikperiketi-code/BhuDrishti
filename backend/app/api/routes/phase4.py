"""Read APIs for audit history, record registry, notifications, and local GIS."""

from __future__ import annotations

from datetime import datetime, timezone

from pathlib import Path

from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, UploadFile
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.contracts.auth import AuthenticatedUser, Role
from app.config import Settings, get_settings
from app.db.models import AuditEventModel, DocumentModel, LandRecordModel, NotificationReadModel, ParcelIndexModel, ReviewCaseModel
from app.db.session import get_db
from app.services.auth import Permission, require_permission
from app.services.auth.service import find_user
from app.services.documents.pipeline import has_explicit_synthetic_notice
from app.services.documents.storage import UploadValidationError, safe_display_name
from app.services.gis import GeometryValidationError, index_verified_record, source_parcel_geometry, validate_geojson_polygon
from app.services.legacy_visibility import Dataset, archived_document_id_set, dataset_audit_condition, dataset_record_ids, visible_document_ids


audit_router = APIRouter(prefix="/audit", tags=["audit"])
records_router = APIRouter(prefix="/records", tags=["records"])
gis_router = APIRouter(prefix="/gis", tags=["gis"])
notifications_router = APIRouter(prefix="/notifications", tags=["notifications"])

_GIS_DISCLAIMER = (
    "Boundaries appear only after an officer uploads source GeoJSON. "
    "Officer-supplied geometry is not independently verified against an official cadastre "
    "and is not an ownership determination."
)
_NOTIFICATION_EVENTS = {
    "REVIEW_ASSIGNED", "CONFLICT_DETECTED", "RECORD_APPROVED",
    "RECORD_REJECTED", "PROCESSING_FAILED",
}
_NOTIFICATION_TITLES = {
    "REVIEW_ASSIGNED": "Review assigned",
    "CONFLICT_DETECTED": "Critical conflict detected",
    "RECORD_APPROVED": "Record approved",
    "RECORD_REJECTED": "Record rejected",
    "PROCESSING_FAILED": "Processing failed",
}


def _utc(value: datetime | None) -> datetime | None:
    return value.replace(tzinfo=timezone.utc) if value is not None and value.tzinfo is None else value


def _audit(session: Session, event: AuditEventModel) -> dict:
    actor = find_user(session, event.actor_id)
    return {
        "id": event.id,
        "recordId": event.record_id,
        "documentId": event.document_id,
        "actorId": event.actor_id,
        "actorName": actor.name if actor else None,
        "actorRole": event.actor_role,
        "eventType": event.event_type,
        "timestamp": _utc(event.timestamp),
        "description": event.description,
        "metadata": event.event_metadata or {},
    }


def _parcel(parcel: ParcelIndexModel) -> dict:
    sourced = parcel.geometry_status == "sourced" and parcel.geometry_source == "officer_geojson" and bool(parcel.polygon)
    return {
        "recordId": parcel.record_id,
        "recordNumber": parcel.record_number,
        "surveyNumber": parcel.survey_number,
        "ownerName": parcel.owner_name,
        "area": parcel.area,
        "areaUnit": parcel.area_unit,
        "state": parcel.state,
        "district": parcel.district,
        "village": parcel.village,
        "status": parcel.status,
        "validationStatus": parcel.validation_status,
        "qualityScore": parcel.quality_score,
        "polygon": parcel.polygon if sourced else None,
        "geometrySource": parcel.geometry_source if sourced else "unavailable",
        "geometryStatus": "sourced" if sourced else "unavailable",
        "geometryReference": parcel.geometry_reference if sourced else None,
        "geometryFileName": parcel.geometry_file_name if sourced else None,
        "geometrySha256": parcel.geometry_sha256 if sourced else None,
        "geometryRecordedAt": _utc(parcel.geometry_recorded_at) if sourced else None,
        "geometryRecordedBy": parcel.geometry_recorded_by if sourced else None,
        "indexedAt": _utc(parcel.indexed_at) if sourced else None,
    }


def _operational_parcel(
    parcel: ParcelIndexModel,
    document: DocumentModel | None,
    record: LandRecordModel | None,
    archived_ids: set[str],
) -> bool:
    """Exclude retained demo/legacy rows from operational GIS reads."""
    if (
        parcel.geometry_source not in {"unavailable", "officer_geojson"}
        or not parcel.document_id
        or parcel.document_id in archived_ids
        or document is None
        or document.dataset_scope != "operational"
        or record is None
        or record.document_id != document.id
        or document.demo_scenario
    ):
        return False
    metadata = document.processing_metadata or {}
    payload = record.payload or {}
    pages = document.ocr_pages or []
    if not isinstance(metadata, dict) or not isinstance(payload, dict) or not isinstance(pages, list):
        return False
    source = payload.get("sourceDocument") or {}
    if not isinstance(source, dict) or any(not isinstance(page, dict) for page in pages):
        return False
    return not (
        metadata.get("syntheticSourceDetected")
        or source.get("isSynthetic")
        or has_explicit_synthetic_notice(pages)
    )


def _latest_review(session: Session, record_id: str) -> ReviewCaseModel | None:
    return session.scalar(
        select(ReviewCaseModel)
        .where(ReviewCaseModel.record_id == record_id)
        .order_by(ReviewCaseModel.submitted_at.desc(), ReviewCaseModel.id.desc())
        .limit(1)
    )


def _review(session: Session, case: ReviewCaseModel | None) -> dict | None:
    if case is None:
        return None
    fields = case.field_reviews or {}
    assigned_officer = find_user(session, case.assigned_officer_id)
    decision_actor = find_user(session, case.decided_by)
    return {
        "id": case.id,
        "status": case.status,
        "priority": case.priority,
        "priorityReasons": case.priority_reasons or [],
        "assignedOfficerId": case.assigned_officer_id,
        "assignedOfficerName": assigned_officer.name if assigned_officer else case.assigned_officer_id,
        "originalRecord": case.original_record,
        "reviewedRecord": case.reviewed_record,
        "validation": case.validation,
        "qualityScore": case.quality_score,
        "fieldReviews": [
            {"fieldName": name, **entry}
            for name, entry in fields.items()
        ],
        "issueResolutions": case.issue_resolutions or [],
        "recommendation": case.recommendation,
        "submittedAt": _utc(case.submitted_at),
        "startedAt": _utc(case.started_at),
        "decidedAt": _utc(case.decided_at),
        "decidedBy": case.decided_by,
        "decidedByName": decision_actor.name if decision_actor else case.decided_by,
        "decisionReason": case.decision_reason,
    }


@audit_router.get("/events", summary="Browse immutable audit events")
def list_audit_events(
    dataset: Dataset = Query(default="operational"),
    record_id: str | None = Query(default=None, alias="recordId"),
    event_type: str | None = Query(default=None, alias="eventType"),
    limit: int = Query(default=100, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
    session: Session = Depends(get_db),
    _user: AuthenticatedUser = Depends(require_permission(Permission.AUDIT_READ)),
) -> dict:
    statement = select(AuditEventModel).where(dataset_audit_condition(dataset))
    if record_id:
        statement = statement.where(AuditEventModel.record_id == record_id)
    if event_type:
        statement = statement.where(AuditEventModel.event_type == event_type)
    total = session.scalar(select(func.count()).select_from(statement.subquery())) or 0
    rows = session.scalars(
        statement.order_by(AuditEventModel.timestamp.desc(), AuditEventModel.id.desc())
        .limit(limit).offset(offset)
    ).all()
    return {"items": [_audit(session, item) for item in rows], "total": total}


@records_router.get("", summary="List processed land records")
def list_records(
    dataset: Dataset = Query(default="operational"),
    q: str = Query(default="", max_length=200),
    limit: int = Query(default=100, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
    session: Session = Depends(get_db),
    _user: AuthenticatedUser = Depends(require_permission(Permission.RECORD_READ)),
) -> dict:
    # Reference inputs are validation evidence, not processed registry entries.
    statement = select(LandRecordModel).where(
        LandRecordModel.id.in_(dataset_record_ids(dataset))
    )
    if q.strip():
        needle = f"%{q.strip()}%"
        statement = statement.where(
            LandRecordModel.record_number.ilike(needle)
            | LandRecordModel.owner_name.ilike(needle)
            | LandRecordModel.survey_number.ilike(needle)
            | LandRecordModel.payload["khataNumber"].as_string().ilike(needle)
            | LandRecordModel.payload["village"].as_string().ilike(needle)
            | LandRecordModel.district.ilike(needle)
        )
    total = session.scalar(select(func.count()).select_from(statement.subquery())) or 0
    rows = session.scalars(
        statement.order_by(LandRecordModel.updated_at.desc(), LandRecordModel.id.desc())
        .limit(limit).offset(offset)
    ).all()
    items = []
    for row in rows:
        case = _latest_review(session, row.id)
        parcel = session.get(ParcelIndexModel, row.id)
        items.append({
            "recordId": row.id,
            "recordNumber": row.record_number,
            "ownerName": row.owner_name,
            "surveyNumber": row.survey_number,
            "village": (row.payload or {}).get("village"),
            "district": row.district,
            "validationStatus": row.validation_status,
            "recordStatus": parcel.status if parcel else (case.status if case else row.validation_status),
            "qualityScore": case.quality_score if case else (parcel.quality_score if parcel else None),
            "updatedAt": _utc(row.updated_at),
        })
    return {"items": items, "total": total}


@records_router.get("/{record_id}", summary="Inspect a record with review and audit evidence")
def get_record(
    record_id: str,
    dataset: Dataset = Query(default="operational"),
    session: Session = Depends(get_db),
    user: AuthenticatedUser = Depends(require_permission(Permission.RECORD_READ)),
) -> dict:
    stored = session.scalar(select(LandRecordModel).where(
        LandRecordModel.id == record_id,
        LandRecordModel.id.in_(dataset_record_ids(dataset)),
    ))
    if stored is None:
        raise HTTPException(status_code=404, detail="Record not found.")
    case = _latest_review(session, record_id)
    parcel = session.get(ParcelIndexModel, record_id)
    # A verified officer correction is the canonical view. The original AI
    # snapshot remains in the review row and audit event stream.
    record = case.reviewed_record if case and case.status == "approved" else stored.payload
    events = session.scalars(
        select(AuditEventModel).where(
            AuditEventModel.record_id == record_id, dataset_audit_condition(dataset),
        )
        .order_by(AuditEventModel.timestamp.desc(), AuditEventModel.id.desc())
    ).all() if user.role in {Role.ADMIN, Role.REVENUE_OFFICER, Role.AUDITOR} else []
    return {
        "record": record,
        "review": _review(session, case),
        "auditEvents": [_audit(session, event) for event in events],
        "parcel": _parcel(parcel) if parcel else None,
    }


@gis_router.get("/parcels", summary="Search processed parcel metadata and sourced boundaries")
def list_parcels(
    state: str | None = None,
    district: str | None = None,
    village: str | None = None,
    validation_status: str | None = Query(default=None, alias="validationStatus"),
    record_status: str | None = Query(default=None, alias="recordStatus"),
    q: str | None = Query(default=None, max_length=200),
    session: Session = Depends(get_db),
    _user: AuthenticatedUser = Depends(require_permission(Permission.GIS_READ)),
) -> dict:
    statement = select(ParcelIndexModel).where(
        ParcelIndexModel.document_id.is_not(None),
        ParcelIndexModel.document_id.in_(visible_document_ids()),
        ParcelIndexModel.geometry_source.in_(("unavailable", "officer_geojson")),
    )
    for value, column in ((state, ParcelIndexModel.state), (district, ParcelIndexModel.district), (village, ParcelIndexModel.village),
                          (validation_status, ParcelIndexModel.validation_status), (record_status, ParcelIndexModel.status)):
        if value:
            statement = statement.where(column == value)
    if q and q.strip():
        needle = f"%{q.strip()}%"
        statement = statement.where(
            ParcelIndexModel.record_number.ilike(needle)
            | ParcelIndexModel.survey_number.ilike(needle)
            | ParcelIndexModel.owner_name.ilike(needle)
            | ParcelIndexModel.village.ilike(needle)
        )
    rows = session.scalars(statement.order_by(ParcelIndexModel.indexed_at.desc(), ParcelIndexModel.record_id.desc())).all()
    document_ids = {row.document_id for row in rows if row.document_id}
    record_ids = {row.record_id for row in rows}
    documents = {document.id: document for document in session.scalars(
        select(DocumentModel).where(DocumentModel.id.in_(document_ids))
    )}
    records = {record.id: record for record in session.scalars(
        select(LandRecordModel).where(LandRecordModel.id.in_(record_ids))
    )}
    archived = archived_document_id_set(session)
    visible = [row for row in rows if _operational_parcel(
        row, documents.get(row.document_id), records.get(row.record_id), archived,
    )]
    return {"synthetic": False, "disclaimer": _GIS_DISCLAIMER, "items": [_parcel(row) for row in visible], "total": len(visible)}


@gis_router.get("/parcels/{record_id}", summary="Inspect a processed parcel and any sourced boundary")
def get_parcel(
    record_id: str,
    session: Session = Depends(get_db),
    _user: AuthenticatedUser = Depends(require_permission(Permission.GIS_READ)),
) -> dict:
    parcel = session.get(ParcelIndexModel, record_id)
    document = session.get(DocumentModel, parcel.document_id) if parcel and parcel.document_id else None
    record = session.get(LandRecordModel, record_id) if parcel else None
    if parcel is None or not _operational_parcel(parcel, document, record, archived_document_id_set(session)):
        raise HTTPException(status_code=404, detail="Parcel not found.")
    return {"synthetic": False, "disclaimer": _GIS_DISCLAIMER, "parcel": _parcel(parcel)}


@gis_router.post("/parcels/{record_id}/geometry", summary="Attach officer-sourced parcel GeoJSON")
def import_parcel_geometry(
    record_id: str,
    file: UploadFile = File(...),
    source_reference: str = Form(..., alias="sourceReference"),
    session: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
    user: AuthenticatedUser = Depends(require_permission(Permission.REVIEW_DECIDE)),
) -> dict:
    record = session.get(LandRecordModel, record_id)
    case = _latest_review(session, record_id)
    if record is None or case is None or not record.document_id or case.document_id != record.document_id:
        raise HTTPException(status_code=404, detail="Processed record not found.")
    document = session.get(DocumentModel, record.document_id)
    if document is None or document.dataset_scope != "operational" or document.id in archived_document_id_set(session):
        raise HTTPException(status_code=404, detail="Processed record not found.")
    if (
        document.demo_scenario
        or (document.processing_metadata or {}).get("syntheticSourceDetected")
        or ((record.payload or {}).get("sourceDocument") or {}).get("isSynthetic")
        or has_explicit_synthetic_notice(document.ocr_pages or [])
    ):
        raise HTTPException(status_code=409, detail={
            "code": "synthetic_source", "message": "Sample documents cannot supply operational parcel boundaries.",
        })
    if case.status != "approved" or not case.decided_by or record.validation_status != "approved":
        raise HTTPException(status_code=409, detail={
            "code": "officer_approval_required", "message": "An officer must approve this record before geometry is attached.",
        })
    reference = source_reference.strip()
    if not 4 <= len(reference) <= 256 or any(ord(char) < 32 for char in reference):
        raise HTTPException(status_code=422, detail={
            "code": "invalid_source_reference", "message": "Give a source reference between 4 and 256 characters.",
        })
    try:
        file_name = safe_display_name(file.filename)
    except UploadValidationError as exc:
        raise HTTPException(status_code=422, detail={"code": exc.code, "message": str(exc)}) from exc
    if Path(file_name).suffix.casefold() not in {".geojson", ".json"}:
        raise HTTPException(status_code=422, detail={
            "code": "unsupported_file", "message": "Upload a .geojson or .json file.",
        })
    declared_type = (file.content_type or "").partition(";")[0].strip().casefold()
    if declared_type not in {"", "application/octet-stream", "application/json", "application/geo+json", "text/json"}:
        raise HTTPException(status_code=422, detail={
            "code": "mime_mismatch", "message": "The file must be GeoJSON.",
        })
    content = bytearray()
    while chunk := file.file.read(64 * 1024):
        if len(content) + len(chunk) > settings.geometry_upload_max_bytes:
            raise HTTPException(status_code=413, detail={
                "code": "file_too_large", "message": "The GeoJSON exceeds the configured upload limit.",
            })
        content.extend(chunk)
    try:
        ring = validate_geojson_polygon(bytes(content))
    except GeometryValidationError as exc:
        raise HTTPException(status_code=422, detail={"code": exc.code, "message": str(exc)}) from exc
    parcel = session.get(ParcelIndexModel, record_id)
    if parcel is None:
        parcel = index_verified_record(session, case)
    parcel = source_parcel_geometry(
        session, parcel=parcel, document=document, review_case=case,
        user=user, settings=settings, ring=ring, content=bytes(content),
        file_name=file_name, source_reference=reference,
    )
    return {"synthetic": False, "disclaimer": _GIS_DISCLAIMER, "parcel": _parcel(parcel)}


@notifications_router.get("", summary="Show meaningful workflow notifications")
def list_notifications(
    limit: int = Query(default=30, ge=1, le=100),
    session: Session = Depends(get_db),
    user: AuthenticatedUser = Depends(require_permission(Permission.RECORD_READ)),
) -> dict:
    statement = select(AuditEventModel).where(
        AuditEventModel.event_type.in_(_NOTIFICATION_EVENTS),
        dataset_audit_condition("operational"),
    )
    rows = session.scalars(statement.order_by(AuditEventModel.timestamp.desc(), AuditEventModel.id.desc()).limit(200)).all()
    read_ids = set(session.scalars(
        select(NotificationReadModel.event_id).where(NotificationReadModel.user_id == user.id)
    ).all())
    items = []
    notified_conflicts: set[str] = set()
    for event in rows:
        assignment = event.event_metadata or {}
        if event.event_type == "REVIEW_ASSIGNED" and assignment.get("newOfficerId", assignment.get("assignedOfficerId")) != user.id and user.role != Role.ADMIN:
            continue
        if event.event_type == "CONFLICT_DETECTED" and user.role == Role.AUDITOR:
            # Auditor sees history in the audit page; this alert is operational.
            continue
        if event.event_type == "CONFLICT_DETECTED":
            if event.record_id in notified_conflicts:
                continue
            notified_conflicts.add(event.record_id)
        items.append({
            **_audit(session, event),
            "title": _NOTIFICATION_TITLES[event.event_type],
            "read": event.id in read_ids,
            "href": (
                f"#/documents?id={event.document_id}"
                if event.event_type == "PROCESSING_FAILED" and event.document_id
                else f"#/review/{event.record_id}"
                if event.event_type in {"REVIEW_ASSIGNED", "CONFLICT_DETECTED"}
                else f"#/records/{event.record_id}"
            ),
        })
        if len(items) >= limit:
            break
    return {"items": items, "total": len(items)}


@notifications_router.post("/{event_id}/read", summary="Mark one visible notification as read")
def mark_notification_read(
    event_id: str,
    session: Session = Depends(get_db),
    user: AuthenticatedUser = Depends(require_permission(Permission.RECORD_READ)),
) -> dict:
    event = session.get(AuditEventModel, event_id)
    if event is None or event.event_type not in _NOTIFICATION_EVENTS:
        raise HTTPException(status_code=404, detail="Notification not found.")
    if session.scalar(select(AuditEventModel.id).where(
        AuditEventModel.id == event.id, dataset_audit_condition("operational"),
    )) is None:
        raise HTTPException(status_code=404, detail="Notification not found.")
    assignment = event.event_metadata or {}
    if event.event_type == "REVIEW_ASSIGNED" and assignment.get("newOfficerId", assignment.get("assignedOfficerId")) != user.id and user.role != Role.ADMIN:
        raise HTTPException(status_code=404, detail="Notification not found.")
    if event.event_type == "CONFLICT_DETECTED" and user.role == Role.AUDITOR:
        raise HTTPException(status_code=404, detail="Notification not found.")
    receipt = session.get(NotificationReadModel, (user.id, event.id))
    if receipt is None:
        session.add(NotificationReadModel(user_id=user.id, event_id=event.id))
        session.commit()
    return {"eventId": event.id, "read": True}
