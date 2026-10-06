"""Validation service boundary and pure prototype scoring policy.

Field, record and cross-system checks are separate future service methods.
This module intentionally makes no claim that those checks already exist.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol, Sequence

from app.config import Settings
from app.contracts.land_record import LandRecord, ValidationStatus
from app.contracts.processing import ValidationIssue, ValidationReport


class ValidationService(Protocol):
    def validate_field(self, record: LandRecord) -> tuple[float, list[ValidationIssue]]: ...

    def validate_record(self, record: LandRecord) -> tuple[float, list[ValidationIssue]]: ...

    def validate_cross_system(
        self, record: LandRecord, references: Sequence[LandRecord]
    ) -> tuple[float, list[ValidationIssue]]: ...


@dataclass(frozen=True, slots=True)
class ScoringPolicy:
    field_weight: float
    record_weight: float
    cross_system_weight: float
    reject_below: float
    approve_at_or_above: float

    @classmethod
    def from_settings(cls, settings: Settings) -> "ScoringPolicy":
        return cls(
            field_weight=settings.field_score_weight,
            record_weight=settings.record_score_weight,
            cross_system_weight=settings.cross_system_score_weight,
            reject_below=settings.reject_threshold,
            approve_at_or_above=settings.approve_threshold,
        )

    def __post_init__(self) -> None:
        weights = (self.field_weight, self.record_weight, self.cross_system_weight)
        if any(weight < 0 or weight > 1 for weight in weights):
            raise ValueError("score weights must each be between 0 and 1")
        if abs(sum(weights) - 1.0) > 1e-6:
            raise ValueError("score weights must sum to 1")
        if not 0 <= self.reject_below < self.approve_at_or_above <= 100:
            raise ValueError("routing thresholds must satisfy 0 <= reject < approve <= 100")


def score_and_route(
    field_score: float,
    record_score: float,
    cross_system_score: float,
    *,
    warning_penalty: float = 0,
    policy: ScoringPolicy,
) -> ValidationReport:
    """Combine already-computed check scores and select a review route.

    This does not execute any validation checks. It only applies the configured
    score weights and thresholds to independently supplied scores.
    """

    scores = (field_score, record_score, cross_system_score)
    if any(not 0 <= score <= 100 for score in scores):
        raise ValueError("component scores must each be between 0 and 100")
    if warning_penalty < 0:
        raise ValueError("warning_penalty cannot be negative")

    weighted_score = (
        policy.field_weight * field_score
        + policy.record_weight * record_score
        + policy.cross_system_weight * cross_system_score
        - warning_penalty
    )
    bounded_score = max(0.0, min(100.0, weighted_score))
    if bounded_score < policy.reject_below:
        route = ValidationStatus.REJECTED
    elif bounded_score < policy.approve_at_or_above:
        route = ValidationStatus.HUMAN_REVIEW
    else:
        route = ValidationStatus.APPROVED

    return ValidationReport(
        field_score=field_score,
        record_score=record_score,
        cross_system_score=cross_system_score,
        quality_score=bounded_score,
        routing=route,
    )
