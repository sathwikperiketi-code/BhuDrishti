"""Review queue and officer actions, enforced by server-side RBAC."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.contracts.auth import AuthenticatedUser
from app.contracts.review import (
    AssignRequest, DecisionRequest, FieldReviewRequest, IssueResolutionRequest,
    RecommendationRequest, ReviewCaseDetail, ReviewList,
)
from app.db.session import get_db
from app.services.auth import Permission, require_permission
from app.services.legacy_visibility import Dataset
from app.services.review.service import (
    accept_clear_fields, assign_review, decide, latest_case, list_cases, recommend,
    resolve_issue, review_field, serialize_detail, start_review,
)


router = APIRouter(prefix="/reviews", tags=["reviews"])


@router.get("", response_model=ReviewList, summary="Search and filter active human reviews")
def review_queue(
    dataset: Dataset = Query(default="operational"),
    filter_name: str = Query(default="all", alias="filter"),
    search: str = Query(default="", max_length=200),
    sort: str = Query(default="submitted_at"),
    direction: str = Query(default="desc"),
    limit: int = Query(default=50, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    session: Session = Depends(get_db),
    user: AuthenticatedUser = Depends(require_permission(Permission.REVIEW_READ)),
) -> ReviewList:
    return list_cases(
        session, user, filter_name=filter_name, search=search,
        sort=sort, direction=direction, limit=limit, offset=offset, dataset=dataset,
    )


@router.get("/{record_id}", response_model=ReviewCaseDetail, summary="Inspect AI evidence and officer review state")
def review_detail(
    record_id: str,
    dataset: Dataset = Query(default="operational"),
    session: Session = Depends(get_db),
    _: AuthenticatedUser = Depends(require_permission(Permission.REVIEW_READ)),
) -> ReviewCaseDetail:
    return serialize_detail(session, latest_case(session, record_id, dataset))


@router.post("/{record_id}/start", response_model=ReviewCaseDetail, summary="Start human review")
def start(
    record_id: str,
    session: Session = Depends(get_db),
    user: AuthenticatedUser = Depends(require_permission(Permission.REVIEW_EDIT)),
) -> ReviewCaseDetail:
    case = latest_case(session, record_id)
    start_review(session, case, user)
    session.commit()
    session.refresh(case)
    return serialize_detail(session, case)


@router.post("/{record_id}/fields/{field_name}", response_model=ReviewCaseDetail, summary="Accept, correct, or reject one AI field")
def field_action(
    record_id: str,
    field_name: str,
    body: FieldReviewRequest,
    session: Session = Depends(get_db),
    user: AuthenticatedUser = Depends(require_permission(Permission.REVIEW_EDIT)),
) -> ReviewCaseDetail:
    case = latest_case(session, record_id)
    review_field(session, case, user, field_name, body)
    session.commit()
    session.refresh(case)
    return serialize_detail(session, case)


@router.post("/{record_id}/accept-clear-fields", response_model=ReviewCaseDetail, summary="Explicitly accept all clear AI fields")
def accept_clear(
    record_id: str,
    session: Session = Depends(get_db),
    user: AuthenticatedUser = Depends(require_permission(Permission.REVIEW_EDIT)),
) -> ReviewCaseDetail:
    case = latest_case(session, record_id)
    accept_clear_fields(session, case, user)
    session.commit()
    session.refresh(case)
    return serialize_detail(session, case)


@router.post("/{record_id}/issues/{issue_code}/resolve", response_model=ReviewCaseDetail, summary="Record a human resolution for one validation issue")
def issue_resolution(
    record_id: str,
    issue_code: str,
    body: IssueResolutionRequest,
    session: Session = Depends(get_db),
    user: AuthenticatedUser = Depends(require_permission(Permission.REVIEW_EDIT)),
) -> ReviewCaseDetail:
    case = latest_case(session, record_id)
    resolve_issue(session, case, user, issue_code, body)
    session.commit()
    session.refresh(case)
    return serialize_detail(session, case)


@router.post("/{record_id}/recommendation", response_model=ReviewCaseDetail, summary="Record a verifier recommendation without final decision")
def recommendation(
    record_id: str,
    body: RecommendationRequest,
    session: Session = Depends(get_db),
    user: AuthenticatedUser = Depends(require_permission(Permission.REVIEW_RECOMMEND)),
) -> ReviewCaseDetail:
    case = latest_case(session, record_id)
    recommend(session, case, user, body)
    session.commit()
    session.refresh(case)
    return serialize_detail(session, case)


@router.post("/{record_id}/assign", response_model=ReviewCaseDetail, summary="Assign or claim officer work")
def assign(
    record_id: str,
    body: AssignRequest,
    session: Session = Depends(get_db),
    user: AuthenticatedUser = Depends(require_permission(Permission.REVIEW_ASSIGN)),
) -> ReviewCaseDetail:
    case = latest_case(session, record_id)
    assign_review(session, case, user, body)
    session.commit()
    session.refresh(case)
    return serialize_detail(session, case)


@router.post("/{record_id}/decision", response_model=ReviewCaseDetail, summary="Approve, reject, or send a record back")
def decision(
    record_id: str,
    body: DecisionRequest,
    session: Session = Depends(get_db),
    user: AuthenticatedUser = Depends(require_permission(Permission.REVIEW_DECIDE)),
) -> ReviewCaseDetail:
    case = latest_case(session, record_id)
    decide(session, case, user, body)
    session.commit()
    session.refresh(case)
    return serialize_detail(session, case)
