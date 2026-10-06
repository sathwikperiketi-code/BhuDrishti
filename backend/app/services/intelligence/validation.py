"""Three independent, deterministic land-record validation layers."""

from __future__ import annotations

from collections.abc import Sequence
import re

from app.config import Settings, get_settings
from app.contracts.land_record import AreaUnit, LandRecord
from app.contracts.processing import ValidationIssue, ValidationLevel, ValidationReport
from app.services.validation import ScoringPolicy, score_and_route

from .models import ScoreBreakdown
from .policy import IntelligencePolicy


_SURVEY_FORMAT = re.compile(r"^[A-Z0-9]+(?:[/-][A-Z0-9]+)*$", re.IGNORECASE)


def _issue(
    level: ValidationLevel,
    code: str,
    message: str,
    *,
    field: str | None = None,
    severity: str = "warning",
    expected: object | None = None,
    actual: object | None = None,
) -> ValidationIssue:
    return ValidationIssue(
        level=level, code=code, message=message, field_name=field,
        severity=severity, expected=expected, actual=actual,
    )


def _value(record: LandRecord, camel_name: str) -> object:
    return record.model_dump(mode="python", by_alias=True).get(camel_name)


def _same(left: str | None, right: str | None) -> bool:
    return bool(left and right and left.strip().casefold() == right.strip().casefold())


def _duplicate(record: LandRecord, reference: LandRecord) -> bool:
    """Duplicate identity requires a shared record number and parcel context."""
    return bool(
        _same(record.record_number, reference.record_number)
        and _same(record.survey_number, reference.survey_number)
        and _same(record.village, reference.village)
    )


def validate_field(
    record: LandRecord,
    *,
    policy: IntelligencePolicy | None = None,
) -> tuple[float, list[ValidationIssue]]:
    """Check required values, syntax, range, units, and extraction confidence."""
    policy = policy or IntelligencePolicy()
    score = 100.0
    issues: list[ValidationIssue] = []
    for field in policy.required_fields:
        value = _value(record, field)
        if value is None or value == "" or value == AreaUnit.UNKNOWN:
            score -= policy.missing_field_deduction
            issues.append(_issue(
                ValidationLevel.FIELD, "required_field_missing",
                f"Required field {field} is missing or unknown.", field=field,
                severity="error", expected="present", actual=value,
            ))

    if record.owner_name is not None and not any(char.isalpha() for char in record.owner_name):
        score -= policy.malformed_field_deduction
        issues.append(_issue(
            ValidationLevel.FIELD, "malformed_owner_name",
            "Owner name contains no letters.", field="ownerName", severity="error",
            expected="a person or entity name", actual=record.owner_name,
        ))
    if record.survey_number is not None and not _SURVEY_FORMAT.fullmatch(record.survey_number):
        score -= policy.malformed_field_deduction
        issues.append(_issue(
            ValidationLevel.FIELD, "malformed_survey_number",
            "Survey number does not match the supported identifier format.",
            field="surveyNumber", severity="error",
            expected="letters/digits with optional slash or hyphen", actual=record.survey_number,
        ))
    if record.area is not None and (record.area <= 0 or record.area > policy.max_area):
        score -= policy.malformed_field_deduction
        issues.append(_issue(
            ValidationLevel.FIELD, "area_out_of_range",
            "Area is outside the configured plausible range.", field="area",
            severity="error", expected=f"> 0 and <= {policy.max_area}", actual=record.area,
        ))
    if record.area_unit == AreaUnit.UNKNOWN:
        score -= policy.malformed_field_deduction
        issues.append(_issue(
            ValidationLevel.FIELD, "unknown_area_unit",
            "Area unit could not be normalized.", field="areaUnit",
            severity="error", expected="supported unit", actual="unknown",
        ))

    for field, confidence in record.extraction_confidence.per_field.items():
        if field in policy.required_fields and _value(record, field) is not None and confidence < policy.low_confidence_below:
            score -= policy.low_confidence_deduction
            issues.append(_issue(
                ValidationLevel.FIELD, "low_extraction_confidence",
                "Extraction confidence is low; inspect the source evidence.", field=field,
                expected=f">= {policy.low_confidence_below:.2f}", actual=confidence,
            ))
    return max(0.0, score), issues


def validate_record(
    record: LandRecord,
    *,
    references: Sequence[LandRecord] = (),
    policy: IntelligencePolicy | None = None,
) -> tuple[float, list[ValidationIssue]]:
    """Check completeness, internal consistency, and duplicate combinations."""
    policy = policy or IntelligencePolicy()
    score = 100.0
    issues: list[ValidationIssue] = []
    missing = [field for field in policy.required_fields if _value(record, field) in (None, "", AreaUnit.UNKNOWN)]
    if missing:
        score -= policy.incomplete_record_deduction
        issues.append(_issue(
            ValidationLevel.RECORD, "incomplete_record",
            "The extracted record is incomplete.", severity="warning",
            expected="all required fields", actual=missing,
        ))
    if record.ownership_details and record.ownership_details.owners and record.owner_name:
        if not any(_same(record.owner_name, owner) for owner in record.ownership_details.owners):
            score -= 20.0
            issues.append(_issue(
                ValidationLevel.RECORD, "owner_ownership_mismatch",
                "Owner name differs from the ownership detail names.",
                field="ownershipDetails", expected=record.owner_name,
                actual=record.ownership_details.owners,
            ))
    duplicates = [reference for reference in references if _duplicate(record, reference)]
    if duplicates:
        score -= policy.duplicate_record_deduction
        issues.append(_issue(
            ValidationLevel.RECORD, "duplicate_combination",
            "A record with the same record number, survey number, and village already exists.",
            field="recordNumber", actual=record.record_number,
            expected="unique record and parcel combination",
        ))
    return max(0.0, score), issues


def validate_cross_system(
    record: LandRecord,
    references: Sequence[LandRecord],
    *,
    policy: IntelligencePolicy | None = None,
) -> tuple[float, list[ValidationIssue]]:
    """Compare extracted values with supplied reference records.

    References are inputs from the caller; this layer makes no assertion that
    they are official or current. An unavailable comparison routes toward human
    review instead of counting as a passed check.
    """
    policy = policy or IntelligencePolicy()
    if not references:
        return policy.no_reference_score, [_issue(
            ValidationLevel.CROSS_SYSTEM, "reference_unavailable",
            "No reference record was supplied for cross-system comparison.",
            expected="reference record", actual=None,
        )]

    ranked: list[tuple[int, LandRecord]] = []
    for reference in references:
        rank = 0
        if _same(record.record_number, reference.record_number):
            rank = 3
        elif _same(record.survey_number, reference.survey_number) and _same(record.village, reference.village):
            rank = 2
        elif _same(record.khata_number, reference.khata_number) and _same(record.village, reference.village):
            rank = 1
        if rank:
            ranked.append((rank, reference))
    if not ranked:
        return policy.no_reference_score, [_issue(
            ValidationLevel.CROSS_SYSTEM, "reference_not_found",
            "No supplied reference record matched the extracted parcel identifiers.",
            expected="matching reference", actual=record.survey_number,
        )]
    highest_rank = max(rank for rank, _ in ranked)
    reference = next(item for rank, item in ranked if rank == highest_rank)
    score = 100.0
    issues: list[ValidationIssue] = []
    equally_ranked = [item for rank, item in ranked if rank == highest_rank]
    if len(equally_ranked) > 1 and any(
        (candidate.survey_number and not _same(candidate.survey_number, reference.survey_number))
        or (candidate.village and not _same(candidate.village, reference.village))
        or (
            candidate.area is not None and reference.area is not None
            and candidate.area_unit == reference.area_unit
            and abs(candidate.area - reference.area) > policy.area_relative_tolerance * max(reference.area, 1e-9)
        )
        for candidate in equally_ranked if candidate is not reference
    ):
        score -= policy.cross_conflict_deduction
        issues.append(_issue(
            ValidationLevel.CROSS_SYSTEM, "related_record_conflict",
            "Supplied reference records disagree about this parcel.",
            expected="consistent related records", actual="conflicting reference values",
        ))
    if _duplicate(record, reference):
        score -= 55.0
        issues.append(_issue(
            ValidationLevel.CROSS_SYSTEM, "duplicate_reference_record",
            "The extracted record duplicates an existing reference record.",
            field="recordNumber", expected="unique record", actual=record.record_number,
        ))
    if record.survey_number and reference.survey_number and not _same(record.survey_number, reference.survey_number):
        score -= policy.cross_conflict_deduction
        issues.append(_issue(
            ValidationLevel.CROSS_SYSTEM, "survey_number_mismatch",
            "Extracted survey number differs from the reference record.",
            field="surveyNumber", expected=reference.survey_number,
            actual=record.survey_number,
        ))
    if record.village and reference.village and not _same(record.village, reference.village):
        score -= policy.cross_conflict_deduction
        issues.append(_issue(
            ValidationLevel.CROSS_SYSTEM, "village_mismatch",
            "Extracted village differs from the reference record.",
            field="village", expected=reference.village, actual=record.village,
        ))
    if record.area is not None and reference.area is not None and reference.area > 0:
        # This comparison is valid only when both records use the same unit.
        if record.area_unit == reference.area_unit:
            relative_difference = abs(record.area - reference.area) / reference.area
            if relative_difference > policy.area_relative_tolerance:
                score -= policy.cross_area_deduction
                issues.append(_issue(
                    ValidationLevel.CROSS_SYSTEM, "area_mismatch",
                    "Extracted area differs from the reference beyond the configured tolerance.",
                    field="area", expected=reference.area, actual=record.area,
                ))
        else:
            score -= policy.cross_conflict_deduction
            issues.append(_issue(
                ValidationLevel.CROSS_SYSTEM, "area_unit_mismatch",
                "Area units differ; the values were not compared numerically.",
                field="areaUnit", expected=reference.area_unit,
                actual=record.area_unit,
            ))
    if (
        _same(record.record_number, reference.record_number)
        and record.owner_name and reference.owner_name
        and not _same(record.owner_name, reference.owner_name)
    ):
        score -= 35.0
        issues.append(_issue(
            ValidationLevel.CROSS_SYSTEM, "related_record_owner_conflict",
            "Related reference record lists a different owner name.",
            field="ownerName", expected=reference.owner_name,
            actual=record.owner_name,
        ))
    return max(0.0, score), issues


def validate_document(
    record: LandRecord,
    *,
    references: Sequence[LandRecord] = (),
    settings: Settings | None = None,
    policy: IntelligencePolicy | None = None,
) -> tuple[ValidationReport, ScoreBreakdown, list[str]]:
    """Run all three layers, apply 50/30/20 scoring, then select a route."""
    policy = policy or IntelligencePolicy()
    settings = settings or get_settings()
    canonical_references = [LandRecord.model_validate(item) for item in references]
    field_score, field_issues = validate_field(record, policy=policy)
    record_score, record_issues = validate_record(record, references=canonical_references, policy=policy)
    cross_score, cross_issues = validate_cross_system(record, canonical_references, policy=policy)
    issues = [*field_issues, *record_issues, *cross_issues]
    warning_penalty = sum(
        policy.no_reference_warning_penalty
        if issue.code in {"reference_unavailable", "reference_not_found"}
        else policy.warning_penalty
        for issue in issues if issue.severity == "warning"
    )
    scoring_policy = ScoringPolicy.from_settings(settings)
    report = score_and_route(
        field_score, record_score, cross_score,
        warning_penalty=warning_penalty, policy=scoring_policy,
    ).model_copy(update={"issues": issues})
    field_contribution = field_score * scoring_policy.field_weight
    record_contribution = record_score * scoring_policy.record_weight
    cross_contribution = cross_score * scoring_policy.cross_system_weight
    unrounded_total = field_contribution + record_contribution + cross_contribution - warning_penalty
    breakdown = ScoreBreakdown(
        field_weight=scoring_policy.field_weight,
        record_weight=scoring_policy.record_weight,
        cross_system_weight=scoring_policy.cross_system_weight,
        field_contribution=field_contribution,
        record_contribution=record_contribution,
        cross_system_contribution=cross_contribution,
        warning_penalty=warning_penalty,
        unrounded_total=unrounded_total,
        quality_score=report.quality_score,
        reject_below=scoring_policy.reject_below,
        approve_at_or_above=scoring_policy.approve_at_or_above,
        routing=report.routing,
    )
    warnings = list(dict.fromkeys(issue.message for issue in issues if issue.severity == "warning"))
    return report, breakdown, warnings
