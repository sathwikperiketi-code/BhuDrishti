"""Human review state changes with immutable AI evidence and audit writes."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any
from uuid import uuid4

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.contracts.auth import AuthenticatedUser, Role
from app.contracts.land_record import LandRecord, ValidationStatus
from app.contracts.processing import ValidationReport
from app.contracts.review import (
    AssignRequest, DecisionRequest, FieldReviewRequest, IssueResolutionRequest,
    IssueResolutionType, RecommendationRequest, ReviewCaseDetail, ReviewCaseSummary,
    ReviewDecision, ReviewField, ReviewFieldAction, ReviewList, ReviewPriority,
    ReviewStatus, ReviewSummary,
)
from app.db.models import DocumentModel, LandRecordModel, ParcelIndexModel, ReviewCaseModel, UserModel
from app.services.audit import AuditEventType, append_event
from app.services.auth.service import find_user
from app.services.legacy_visibility import Dataset, dataset_document_ids
from app.services.intelligence.models import ScoreBreakdown
from app.services.intelligence.validation import validate_field


_FIELD_ORDER = (
    "ownerName", "fatherOrGuardianName", "surveyNumber", "khasraNumber",
    "khataNumber", "recordNumber", "area", "areaUnit", "village",
    "mandalOrTehsil", "district", "state", "landClassification",
    "ownershipDetails", "mutationRecords", "registrationInformation",
)
_REQUIRED_FIELDS = frozenset({"ownerName", "surveyNumber", "area", "areaUnit", "village", "district", "state"})
_PROTECTED_FIELDS = frozenset({
    "recordId", "sourceDocument", "extractionConfidence", "validationStatus",
    "provenance", "extensions",
})
_CRITICAL_CODES = frozenset({
    "survey_number_mismatch", "village_mismatch", "area_mismatch", "area_unit_mismatch",
    "related_record_conflict", "related_record_owner_conflict", "duplicate_reference_record",
    "duplicate_combination", "required_field_missing", "malformed_owner_name",
    "malformed_survey_number", "area_out_of_range", "unknown_area_unit",
})
_CONCRETE_REFERENCE_CODES = frozenset({
    "survey_number_mismatch", "village_mismatch", "area_mismatch",
    "area_unit_mismatch", "related_record_owner_conflict",
})


@dataclass(frozen=True, slots=True)
class ReviewPriorityPolicy:
    """Visible, adjustable rules; there is no opaque priority model."""

    low_confidence_below: float = 0.70
    high_pending_hours: int = 18
    high_priority_score_below: float = 70.0


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _utc(value: datetime | None) -> datetime | None:
    if value is None:
        return None
    return value.replace(tzinfo=timezone.utc) if value.tzinfo is None else value


def _issue_key(issue: dict[str, Any]) -> tuple[str, str | None]:
    return str(issue.get("code", "")), issue.get("fieldName")


def _issues(case: ReviewCaseModel) -> list[dict[str, Any]]:
    return list((case.validation or {}).get("issues") or [])


def _is_critical(issue: dict[str, Any]) -> bool:
    return issue.get("severity") == "error" or issue.get("code") in _CRITICAL_CODES


def requires_review(report: ValidationReport) -> bool:
    """Every validation result needs an officer disposition."""
    return True


def _priority(case: ReviewCaseModel, policy: ReviewPriorityPolicy | None = None) -> tuple[ReviewPriority, list[dict[str, str]]]:
    policy = policy or ReviewPriorityPolicy()
    reasons: list[dict[str, str]] = []
    issues = _issues(case)
    critical = [issue for issue in issues if _is_critical(issue)]
    if critical:
        reasons.append({"code": "critical_conflict", "message": critical[0].get("message", "Critical validation conflict")})
    if any(issue.get("code") in {"required_field_missing", "incomplete_record"} for issue in issues):
        reasons.append({"code": "missing_field", "message": "A required field is missing."})
    if any("duplicate" in str(issue.get("code")) for issue in issues):
        reasons.append({"code": "possible_duplicate", "message": "Possible duplicate record."})
    confidence = (case.original_record or {}).get("extractionConfidence") or {}
    per_field = confidence.get("perField") or {}
    low = [name for name, value in per_field.items() if isinstance(value, (int, float)) and value < policy.low_confidence_below]
    if low:
        reasons.append({"code": "low_confidence", "message": f"Confidence below {policy.low_confidence_below:.0%}: {', '.join(low[:3])}."})
    age_hours = (_now() - (_utc(case.submitted_at) or _now())).total_seconds() / 3600
    if age_hours >= policy.high_pending_hours and case.status in {"queued", "in_progress"}:
        reasons.append({"code": "pending_age", "message": f"Pending for {int(age_hours)} hours."})
    if case.quality_score < policy.high_priority_score_below:
        reasons.append({"code": "low_quality_score", "message": f"Quality score {case.quality_score:g} requires close review."})
    high = bool(critical or any(reason["code"] in {"missing_field", "possible_duplicate", "pending_age"} for reason in reasons))
    priority = ReviewPriority.HIGH if high else ReviewPriority.MEDIUM if reasons else ReviewPriority.LOW
    return priority, reasons


def create_review_case(
    session: Session,
    document: DocumentModel,
    record: LandRecord,
    report: ValidationReport,
    breakdown: ScoreBreakdown,
) -> ReviewCaseModel:
    """Stage officer disposition for every processed document.

    Each attempt gets a new row, so a send-back/reprocess never changes a prior
    AI snapshot. The latest attempt is the active review for the record. The
    validation route is a quality recommendation, including when it says
    approved; only an officer decision can approve the canonical record.
    """
    snapshot = record.model_dump(mode="json", by_alias=True)
    case = ReviewCaseModel(
        id=str(uuid4()), record_id=str(record.record_id), document_id=document.id,
        status=ReviewStatus.QUEUED.value, priority=ReviewPriority.MEDIUM.value,
        priority_reasons=[], assigned_officer_id=None,
        original_record=snapshot, reviewed_record=dict(snapshot), field_reviews={},
        issue_resolutions=[], recommendation=None,
        validation=report.model_dump(mode="json", by_alias=True),
        quality_score=breakdown.quality_score,
        primary_conflict=next((issue.message for issue in report.issues if _is_critical(issue.model_dump(mode="json", by_alias=True))), None)
        or (report.issues[0].message if report.issues else None),
        submitted_at=_now(), updated_at=_now(), version=1,
    )
    case.priority, case.priority_reasons = _priority(case)
    case.priority = case.priority.value
    session.add(case)
    append_event(
        session, record_id=case.record_id, document_id=document.id,
        actor_id="system", actor_role="SYSTEM", event_type=AuditEventType.REVIEW_CREATED,
        description="Human review required after AI-assisted validation.",
        metadata={"reviewCaseId": case.id, "qualityScore": case.quality_score,
                  "priority": case.priority, "priorityReasons": case.priority_reasons},
    )
    return case


def latest_case(session: Session, record_id: str, dataset: Dataset = "operational") -> ReviewCaseModel:
    case = session.scalar(
        select(ReviewCaseModel).where(
            ReviewCaseModel.record_id == record_id,
            ReviewCaseModel.document_id.in_(dataset_document_ids(dataset)),
        )
        .order_by(ReviewCaseModel.submitted_at.desc(), ReviewCaseModel.id.desc()).limit(1)
    )
    if case is None:
        raise HTTPException(status_code=404, detail="Review case not found.")
    return case


def _latest_cases(session: Session) -> list[ReviewCaseModel]:
    rows = session.scalars(select(ReviewCaseModel).order_by(ReviewCaseModel.submitted_at.desc(), ReviewCaseModel.id.desc())).all()
    seen: set[str] = set()
    latest: list[ReviewCaseModel] = []
    for row in rows:
        if row.record_id not in seen:
            seen.add(row.record_id)
            latest.append(row)
    return latest


def _field_names(case: ReviewCaseModel) -> list[str]:
    original = case.original_record or {}
    present = {field for field in _FIELD_ORDER if original.get(field) not in (None, "", [])}
    present |= _REQUIRED_FIELDS
    present |= {str(issue.get("fieldName")) for issue in _issues(case) if issue.get("fieldName") in _FIELD_ORDER}
    return [field for field in _FIELD_ORDER if field in present]


def _missing_required(record: dict[str, Any], field: str) -> bool:
    value = record.get(field)
    return value in (None, "", []) or (field == "areaUnit" and value == "unknown")


def _resolution_for(case: ReviewCaseModel, issue: dict[str, Any]) -> dict[str, Any] | None:
    key = _issue_key(issue)
    return next((entry for entry in (case.issue_resolutions or []) if (entry.get("code"), entry.get("fieldName")) == key), None)


def _summary(case: ReviewCaseModel) -> ReviewSummary:
    field_names = _field_names(case)
    reviews = case.field_reviews or {}
    reviewed = sum(1 for field in field_names if field in reviews)
    rejected = [field for field in field_names if (reviews.get(field) or {}).get("action") == "reject"]
    issues = _issues(case)
    resolved = sum(1 for issue in issues if _resolution_for(case, issue))
    unresolved_critical = sum(1 for issue in issues if _is_critical(issue) and not _resolution_for(case, issue))
    missing_required = [field for field in _REQUIRED_FIELDS if _missing_required(case.reviewed_record or {}, field)]
    blocking: list[str] = []
    if reviewed < len(field_names):
        blocking.append(f"Review every field ({reviewed}/{len(field_names)} complete).")
    if rejected:
        blocking.append(f"Rejected fields need correction: {', '.join(sorted(rejected))}.")
    if resolved < len(issues):
        blocking.append(f"Resolve or acknowledge all validation issues ({resolved}/{len(issues)} complete).")
    if missing_required:
        blocking.append(f"Required fields are missing: {', '.join(sorted(missing_required))}.")
    # Acknowledging an earlier issue cannot make a newly malformed reviewed
    # value approvable. Recheck the current canonical values at decision time.
    try:
        reviewed_record = LandRecord.model_validate(case.reviewed_record or {})
        _, current_field_issues = validate_field(reviewed_record)
        invalid = [issue for issue in current_field_issues
                   if issue.severity == "error" and issue.code != "required_field_missing"]
        if invalid:
            blocking.append("Reviewed values still fail field validation: " +
                            ", ".join(sorted({f"{issue.field_name} ({issue.code})" for issue in invalid})) + ".")
    except ValueError:
        blocking.append("Reviewed values do not match the land-record schema.")
    if case.status not in {ReviewStatus.QUEUED.value, ReviewStatus.IN_PROGRESS.value}:
        blocking.append("This review attempt already has a final disposition.")
    return ReviewSummary(
        fields_reviewed=reviewed, fields_total=len(field_names),
        warnings_resolved=resolved, warnings_total=len(issues),
        critical_conflicts=unresolved_critical, can_approve=not blocking,
        blocking_reasons=blocking,
    )


def _user(session: Session, user_id: str | None) -> AuthenticatedUser | None:
    return find_user(session, user_id)


def serialize_summary(session: Session, case: ReviewCaseModel, document: DocumentModel | None = None) -> ReviewCaseSummary:
    priority, reasons = _priority(case)
    original = case.original_record or {}
    document_name = document.file_name if document else ((original.get("sourceDocument") or {}).get("fileName") or "Source document")
    return ReviewCaseSummary(
        record_id=case.record_id, record_number=original.get("recordNumber"),
        document_id=case.document_id, document_name=document_name,
        owner_name=original.get("ownerName"), survey_number=original.get("surveyNumber"),
        quality_score=case.quality_score,
        validation_status=(case.reviewed_record or {}).get("validationStatus", "human_review"),
        primary_conflict=case.primary_conflict, submitted_at=_utc(case.submitted_at) or _now(),
        updated_at=_utc(case.updated_at) or _now(), priority=priority,
        priority_reasons=[reason["message"] for reason in reasons],
        assigned_officer=_user(session, case.assigned_officer_id), status=ReviewStatus(case.status),
    )


def serialize_detail(session: Session, case: ReviewCaseModel) -> ReviewCaseDetail:
    document = session.get(DocumentModel, case.document_id)
    base = serialize_summary(session, case, document)
    original = case.original_record or {}
    reviewed = case.reviewed_record or {}
    provenance = original.get("provenance") or {}
    confidences = ((original.get("extractionConfidence") or {}).get("perField") or {})
    reviews = case.field_reviews or {}
    parcel = session.get(ParcelIndexModel, case.record_id)
    fields: list[ReviewField] = []
    for field in _field_names(case):
        review = reviews.get(field) or {}
        evidence = provenance.get(field) or (provenance.get("area") if field == "areaUnit" else None)
        field_issues = [issue for issue in _issues(case) if issue.get("fieldName") == field]
        fields.append(ReviewField(
            field=field, original_value=original.get(field), reviewed_value=reviewed.get(field),
            confidence=confidences.get(field) or (confidences.get("area") if field == "areaUnit" else None),
            source=evidence, validation_status="conflict" if any(_is_critical(issue) for issue in field_issues) else "warning" if field_issues else "clear",
            review_status=review.get("action", "unreviewed"), reviewer=_user(session, review.get("reviewerId")),
            reviewed_at=datetime.fromisoformat(review["reviewedAt"]) if review.get("reviewedAt") else None,
            reason=review.get("reason"),
        ))
    return ReviewCaseDetail(
        **base.model_dump(), fields=fields, original_record=original,
        reviewed_record=reviewed, validation=case.validation or {},
        score_breakdown=document.score_breakdown if document else None,
        field_reviews=reviews, issue_resolutions=case.issue_resolutions or [],
        recommendation=case.recommendation, summary=_summary(case),
        started_at=_utc(case.started_at), decided_at=_utc(case.decided_at),
        decided_by=_user(session, case.decided_by), decision_reason=case.decision_reason,
        gis_indexed=bool(parcel and parcel.status == "verified" and parcel.geometry_status == "sourced" and parcel.indexed_at),
        gis_parcel_id=parcel.record_id if parcel and parcel.status == "verified" and parcel.geometry_status == "sourced" and parcel.indexed_at else None,
    )


def list_cases(
    session: Session, user: AuthenticatedUser, *, filter_name: str = "all", search: str = "",
    sort: str = "submitted_at", direction: str = "desc", limit: int = 50, offset: int = 0,
    dataset: Dataset = "operational",
) -> ReviewList:
    selected = set(session.scalars(dataset_document_ids(dataset)).all())
    rows = [case for case in _latest_cases(session)
            if case.status in {"queued", "in_progress"} and case.document_id in selected]
    searchable = search.strip().casefold()
    if searchable:
        def matches(case: ReviewCaseModel) -> bool:
            original = case.original_record or {}
            document = session.get(DocumentModel, case.document_id)
            haystack = " ".join(str(value or "") for value in (
                case.record_id, original.get("recordNumber"), original.get("ownerName"),
                original.get("surveyNumber"), case.primary_conflict,
                document.file_name if document else "",
            )).casefold()
            return searchable in haystack
        rows = [case for case in rows if matches(case)]
    def has_issue(case: ReviewCaseModel, codes: set[str]) -> bool:
        return any(issue.get("code") in codes for issue in _issues(case))
    if filter_name == "high_priority":
        rows = [case for case in rows if _priority(case)[0] == ReviewPriority.HIGH]
    elif filter_name == "low_confidence":
        rows = [case for case in rows if any(issue.get("code") == "low_extraction_confidence" for issue in _issues(case)) or any(reason["code"] == "low_confidence" for reason in _priority(case)[1])]
    elif filter_name == "conflicts":
        rows = [case for case in rows if has_issue(case, _CRITICAL_CODES - {"required_field_missing"})]
    elif filter_name == "missing_fields":
        rows = [case for case in rows if has_issue(case, {"required_field_missing", "incomplete_record"})]
    elif filter_name == "assigned_to_me":
        rows = [case for case in rows if case.assigned_officer_id == user.id]
    elif filter_name == "unassigned":
        rows = [case for case in rows if case.assigned_officer_id is None]
    elif filter_name != "all":
        raise HTTPException(status_code=422, detail="Unknown review filter.")
    reverse = direction == "desc"
    if sort == "submitted_at":
        rows.sort(key=lambda case: (_utc(case.submitted_at) or _now(), case.id), reverse=reverse)
    elif sort == "quality_score":
        rows.sort(key=lambda case: (case.quality_score, case.id), reverse=reverse)
    elif sort == "priority":
        order = {ReviewPriority.LOW: 0, ReviewPriority.MEDIUM: 1, ReviewPriority.HIGH: 2}
        rows.sort(key=lambda case: (order[_priority(case)[0]], _utc(case.submitted_at) or _now()), reverse=reverse)
    else:
        raise HTTPException(status_code=422, detail="Unknown review sort.")
    if direction not in {"asc", "desc"}:
        raise HTTPException(status_code=422, detail="Unknown sort direction.")
    total = len(rows)
    return ReviewList(items=[serialize_summary(session, case, session.get(DocumentModel, case.document_id)) for case in rows[offset:offset + limit]], total=total)


def _ensure_open(case: ReviewCaseModel) -> None:
    if case.status not in {ReviewStatus.QUEUED.value, ReviewStatus.IN_PROGRESS.value}:
        raise HTTPException(status_code=409, detail="Review attempt is already closed.")


def start_review(session: Session, case: ReviewCaseModel, user: AuthenticatedUser) -> None:
    _ensure_open(case)
    if case.status == ReviewStatus.IN_PROGRESS.value:
        return
    case.status = ReviewStatus.IN_PROGRESS.value
    case.started_at = _now()
    case.updated_at = _now()
    case.version += 1
    if case.assigned_officer_id is None and user.role in {Role.ADMIN, Role.REVENUE_OFFICER}:
        case.assigned_officer_id = user.id
    append_event(
        session, record_id=case.record_id, document_id=case.document_id,
        actor_id=user.id, actor_role=user.role.value, event_type=AuditEventType.REVIEW_STARTED,
        description=f"{user.name} started officer review.", metadata={"reviewCaseId": case.id},
    )


def _canonical_field_value(record: dict[str, Any], field: str, value: Any) -> tuple[dict[str, Any], Any]:
    candidate = {**record, field: value}
    try:
        parsed = LandRecord.model_validate(candidate)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=f"Invalid value for {field}: {exc}") from exc
    clean = parsed.model_dump(mode="json", by_alias=True)
    return clean, clean.get(field)


def _apply_field_review(
    session: Session, case: ReviewCaseModel, user: AuthenticatedUser,
    field: str, body: FieldReviewRequest,
) -> None:
    _ensure_open(case)
    if field not in _field_names(case) or field in _PROTECTED_FIELDS:
        raise HTTPException(status_code=404, detail="Reviewable field not found.")
    start_review(session, case, user)
    original = (case.original_record or {}).get(field)
    current = (case.reviewed_record or {}).get(field)
    if body.action == ReviewFieldAction.EDIT:
        reviewed, final_value = _canonical_field_value(case.reviewed_record, field, body.reviewed_value)
        case.reviewed_record = reviewed
        event_type = AuditEventType.FIELD_EDITED
        description = f"{user.name} corrected {field}."
    elif body.action == ReviewFieldAction.ACCEPT:
        if original in (None, "", []):
            raise HTTPException(status_code=422, detail="A missing AI value cannot be accepted; enter a correction.")
        reviewed, final_value = _canonical_field_value(case.reviewed_record, field, original)
        case.reviewed_record = reviewed
        event_type = AuditEventType.FIELD_ACCEPTED
        description = f"{user.name} accepted the AI value for {field}."
    else:
        final_value = current
        event_type = AuditEventType.FIELD_REJECTED
        description = f"{user.name} rejected the AI value for {field}."
    reviews = dict(case.field_reviews or {})
    reviews[field] = {
        "action": body.action.value, "originalValue": original,
        "reviewedValue": final_value if body.action != ReviewFieldAction.REJECT else None,
        "reviewerId": user.id, "reviewerRole": user.role.value,
        "reviewedAt": _now().isoformat(), "reason": (body.reason or "").strip() or None,
    }
    case.field_reviews = reviews
    # A later field change invalidates any earlier human explanation of a
    # validation issue for that field. The prior resolution remains in audit.
    case.issue_resolutions = [
        entry for entry in (case.issue_resolutions or []) if entry.get("fieldName") != field
    ]
    case.updated_at = _now()
    case.version += 1
    append_event(
        session, record_id=case.record_id, document_id=case.document_id,
        actor_id=user.id, actor_role=user.role.value, event_type=event_type,
        description=description,
        metadata={"reviewCaseId": case.id, "field": field, "originalValue": original,
                  "previousValue": current, "newValue": final_value if body.action != ReviewFieldAction.REJECT else None,
                  "reason": (body.reason or "").strip() or None},
    )


def review_field(session: Session, case: ReviewCaseModel, user: AuthenticatedUser, field: str, body: FieldReviewRequest) -> None:
    _apply_field_review(session, case, user, field, body)


def accept_clear_fields(session: Session, case: ReviewCaseModel, user: AuthenticatedUser) -> int:
    _ensure_open(case)
    issue_fields = {issue.get("fieldName") for issue in _issues(case) if issue.get("fieldName")}
    eligible = [
        field for field in _field_names(case)
        if field not in issue_fields and field not in (case.field_reviews or {})
        and (case.original_record or {}).get(field) not in (None, "", [])
    ]
    for field in eligible:
        _apply_field_review(session, case, user, field, FieldReviewRequest(action=ReviewFieldAction.ACCEPT))
    return len(eligible)


def resolve_issue(session: Session, case: ReviewCaseModel, user: AuthenticatedUser, code: str, body: IssueResolutionRequest) -> None:
    _ensure_open(case)
    matching = [issue for issue in _issues(case) if issue.get("code") == code and (body.field_name is None or issue.get("fieldName") == body.field_name)]
    if not matching:
        raise HTTPException(status_code=404, detail="Validation issue not found.")
    if len(matching) > 1:
        raise HTTPException(status_code=422, detail="fieldName is required when an issue code affects multiple fields.")
    issue = matching[0]
    field_name = issue.get("fieldName")
    if body.resolution == IssueResolutionType.CORRECTED:
        field = issue.get("fieldName")
        if not field or (case.field_reviews or {}).get(field, {}).get("action") != ReviewFieldAction.EDIT.value:
            raise HTTPException(status_code=422, detail="Corrected resolution requires an officer edit to the issue field.")
        expected = issue.get("expected")
        current = (case.reviewed_record or {}).get(field)
        if code in _CONCRETE_REFERENCE_CODES and expected is not None and isinstance(expected, (str, int, float)) and str(current).casefold() != str(expected).casefold():
            raise HTTPException(status_code=422, detail="The reviewed value must match the reference value for a corrected resolution.")
        if current in (None, "", []):
            raise HTTPException(status_code=422, detail="Corrected value must be present.")
        if code in {"required_field_missing", "malformed_owner_name", "malformed_survey_number", "area_out_of_range", "unknown_area_unit"}:
            _, remaining = validate_field(LandRecord.model_validate(case.reviewed_record))
            if any(item.code == code and item.field_name == field for item in remaining):
                raise HTTPException(status_code=422, detail="The corrected value still fails this field validation check.")
    elif body.resolution == IssueResolutionType.CONFIRMED:
        field = issue.get("fieldName")
        if field and field not in (case.field_reviews or {}):
            raise HTTPException(status_code=422, detail="Review the affected field before confirming a discrepancy.")
    resolution = {
        "code": code, "issueCode": code, "fieldName": field_name, "resolution": body.resolution.value,
        "reason": body.reason.strip(), "actorId": user.id, "actorRole": user.role.value,
        "at": _now().isoformat(), "timestamp": _now().isoformat(),
    }
    case.issue_resolutions = [
        entry for entry in (case.issue_resolutions or [])
        if (entry.get("code"), entry.get("fieldName")) != (code, field_name)
    ] + [resolution]
    case.updated_at = _now()
    case.version += 1
    append_event(
        session, record_id=case.record_id, document_id=case.document_id,
        actor_id=user.id, actor_role=user.role.value, event_type=AuditEventType.ISSUE_RESOLVED,
        description=f"{user.name} recorded resolution for {code}.",
        metadata={"reviewCaseId": case.id, **resolution},
    )


def recommend(session: Session, case: ReviewCaseModel, user: AuthenticatedUser, body: RecommendationRequest) -> None:
    _ensure_open(case)
    start_review(session, case, user)
    case.recommendation = {
        "value": body.recommendation.value, "reason": body.reason.strip(),
        "reviewerId": user.id, "reviewerRole": user.role.value, "at": _now().isoformat(),
    }
    case.updated_at = _now()
    case.version += 1
    append_event(
        session, record_id=case.record_id, document_id=case.document_id,
        actor_id=user.id, actor_role=user.role.value, event_type=AuditEventType.REVIEW_RECOMMENDED,
        description=f"{user.name} recommended {body.recommendation.value.replace('_', ' ')}.",
        metadata={"reviewCaseId": case.id, **case.recommendation},
    )


def assign_review(session: Session, case: ReviewCaseModel, user: AuthenticatedUser, body: AssignRequest) -> None:
    _ensure_open(case)
    stored_assignee = session.get(UserModel, body.officer_id)
    assigned = _user(session, body.officer_id) if stored_assignee and stored_assignee.is_active else None
    if assigned is None or assigned.role not in {Role.ADMIN, Role.REVENUE_OFFICER}:
        raise HTTPException(status_code=422, detail="Assign to an active administrator or revenue officer.")
    if user.role != Role.ADMIN and assigned.id != user.id:
        raise HTTPException(status_code=403, detail="Revenue officers may only claim their own work.")
    previous = case.assigned_officer_id
    case.assigned_officer_id = assigned.id
    case.updated_at = _now()
    case.version += 1
    append_event(
        session, record_id=case.record_id, document_id=case.document_id,
        actor_id=user.id, actor_role=user.role.value, event_type=AuditEventType.REVIEW_ASSIGNED,
        description=f"Review assigned to {assigned.name}.",
        metadata={"reviewCaseId": case.id, "previousOfficerId": previous, "newOfficerId": assigned.id},
    )


def decide(session: Session, case: ReviewCaseModel, user: AuthenticatedUser, body: DecisionRequest) -> None:
    _ensure_open(case)
    if case.assigned_officer_id and case.assigned_officer_id != user.id and user.role != Role.ADMIN:
        raise HTTPException(status_code=403, detail="This review is assigned to another officer.")
    if body.decision == ReviewDecision.APPROVE:
        summary = _summary(case)
        if not summary.can_approve:
            raise HTTPException(status_code=409, detail={"code": "approval_blocked", "reasons": summary.blocking_reasons})
        case.status = ReviewStatus.APPROVED.value
        reviewed = dict(case.reviewed_record or {})
        reviewed["validationStatus"] = ValidationStatus.APPROVED.value
        case.reviewed_record = reviewed
        record = session.get(LandRecordModel, case.record_id)
        if record is None:
            raise HTTPException(status_code=409, detail="Processed land record no longer exists.")
        canonical = LandRecord.model_validate(reviewed)
        record.payload = canonical.model_dump(mode="json", by_alias=True)
        record.owner_name = canonical.owner_name
        record.survey_number = canonical.survey_number
        record.record_number = canonical.record_number
        record.area = canonical.area
        record.area_unit = canonical.area_unit.value if canonical.area_unit else None
        record.district = canonical.district
        record.state = canonical.state
        record.validation_status = ValidationStatus.APPROVED.value
        event_type = AuditEventType.RECORD_APPROVED
        description = f"{user.name} verified the record after human review."
    elif body.decision == ReviewDecision.REJECT:
        case.status = ReviewStatus.REJECTED.value
        record = session.get(LandRecordModel, case.record_id)
        if record:
            record.validation_status = ValidationStatus.REJECTED.value
        event_type = AuditEventType.RECORD_REJECTED
        description = f"{user.name} rejected the record."
        from app.services.gis import set_parcel_review_status
        set_parcel_review_status(session, case.record_id, "rejected")
    else:
        case.status = ReviewStatus.SENT_BACK.value
        record = session.get(LandRecordModel, case.record_id)
        if record:
            record.validation_status = ValidationStatus.HUMAN_REVIEW.value
        event_type = AuditEventType.RECORD_SENT_BACK
        description = f"{user.name} sent the record back for reprocessing."
        from app.services.gis import set_parcel_review_status
        set_parcel_review_status(session, case.record_id, "sent_back")
    case.decided_at = _now()
    case.decided_by = user.id
    case.decision_reason = (body.reason or "").strip() or None
    case.updated_at = _now()
    case.version += 1
    append_event(
        session, record_id=case.record_id, document_id=case.document_id,
        actor_id=user.id, actor_role=user.role.value, event_type=event_type,
        description=description,
        metadata={"reviewCaseId": case.id, "decision": body.decision.value,
                  "reason": case.decision_reason, "qualityScore": case.quality_score,
                  "fieldReviews": case.field_reviews, "issueResolutions": case.issue_resolutions},
    )
    if body.decision == ReviewDecision.APPROVE:
        from app.services.gis import index_verified_record
        index_verified_record(session, case)
