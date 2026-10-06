"""Officer review API contracts. AI evidence and human decisions stay separate."""

from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from typing import Any

from pydantic import Field, model_validator

from app.contracts.auth import AuthenticatedUser
from app.contracts.land_record import ContractModel


class ReviewStatus(StrEnum):
    QUEUED = "queued"
    IN_PROGRESS = "in_progress"
    APPROVED = "approved"
    REJECTED = "rejected"
    SENT_BACK = "sent_back"


class ReviewPriority(StrEnum):
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


class ReviewFieldAction(StrEnum):
    ACCEPT = "accept"
    EDIT = "edit"
    REJECT = "reject"


class ReviewDecision(StrEnum):
    APPROVE = "approve"
    REJECT = "reject"
    SEND_BACK = "send_back"


class IssueResolutionType(StrEnum):
    CORRECTED = "corrected"
    CONFIRMED = "confirmed"
    NOT_APPLICABLE = "not_applicable"


class FieldReviewRequest(ContractModel):
    action: ReviewFieldAction
    reviewed_value: Any | None = None
    reason: str | None = Field(default=None, max_length=1000)

    @model_validator(mode="after")
    def validate_action(self) -> "FieldReviewRequest":
        if self.action == ReviewFieldAction.EDIT and self.reviewed_value is None:
            raise ValueError("reviewedValue is required for edit")
        if self.action != ReviewFieldAction.EDIT and self.reviewed_value is not None:
            raise ValueError("reviewedValue is only accepted for edit")
        if self.action == ReviewFieldAction.REJECT and not (self.reason or "").strip():
            raise ValueError("reason is required for rejected fields")
        return self


class IssueResolutionRequest(ContractModel):
    field_name: str | None = None
    resolution: IssueResolutionType
    reason: str = Field(min_length=4, max_length=1000)


class DecisionRequest(ContractModel):
    decision: ReviewDecision
    reason: str | None = Field(default=None, max_length=2000)

    @model_validator(mode="after")
    def require_reason(self) -> "DecisionRequest":
        if self.decision != ReviewDecision.APPROVE and not (self.reason or "").strip():
            raise ValueError("reason is required for reject and send back")
        return self


class RecommendationRequest(ContractModel):
    recommendation: ReviewDecision
    reason: str = Field(min_length=4, max_length=2000)


class AssignRequest(ContractModel):
    officer_id: str = Field(min_length=1)


class ReviewField(ContractModel):
    field: str
    original_value: Any | None = None
    reviewed_value: Any | None = None
    confidence: float | None = None
    source: dict[str, Any] | None = None
    validation_status: str = "clear"
    review_status: str = "unreviewed"
    reviewer: AuthenticatedUser | None = None
    reviewed_at: datetime | None = None
    reason: str | None = None


class ReviewSummary(ContractModel):
    fields_reviewed: int
    fields_total: int
    warnings_resolved: int
    warnings_total: int
    critical_conflicts: int
    can_approve: bool
    blocking_reasons: list[str] = Field(default_factory=list)


class ReviewCaseSummary(ContractModel):
    record_id: str
    record_number: str | None = None
    document_id: str
    document_name: str
    owner_name: str | None = None
    survey_number: str | None = None
    quality_score: float
    validation_status: str
    primary_conflict: str | None = None
    submitted_at: datetime
    updated_at: datetime
    priority: ReviewPriority
    priority_reasons: list[str] = Field(default_factory=list)
    assigned_officer: AuthenticatedUser | None = None
    status: ReviewStatus


class ReviewList(ContractModel):
    items: list[ReviewCaseSummary]
    total: int


class ReviewCaseDetail(ReviewCaseSummary):
    fields: list[ReviewField]
    original_record: dict[str, Any]
    reviewed_record: dict[str, Any]
    validation: dict[str, Any]
    score_breakdown: dict[str, Any] | None = None
    field_reviews: dict[str, Any] = Field(default_factory=dict)
    issue_resolutions: list[dict[str, Any]] = Field(default_factory=list)
    recommendation: dict[str, Any] | None = None
    summary: ReviewSummary
    started_at: datetime | None = None
    decided_at: datetime | None = None
    decided_by: AuthenticatedUser | None = None
    decision_reason: str | None = None
    gis_indexed: bool = False
    gis_parcel_id: str | None = None
