"""Deterministic OCR-to-land-record intelligence service boundary."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any

from app.config import Settings
from app.contracts.land_record import LandRecord, SourceDocument

from .extraction import extract_document
from .models import EvidenceSource, ExtractedField, IntelligenceResult, ScoreBreakdown
from .policy import IntelligencePolicy
from .validation import validate_cross_system, validate_document, validate_field, validate_record


def analyze_document(
    ocr_pages: Sequence[Mapping[str, Any] | Any],
    source_document: SourceDocument | Mapping[str, Any],
    *,
    references: Sequence[LandRecord] = (),
    settings: Settings | None = None,
    policy: IntelligencePolicy | None = None,
) -> IntelligenceResult:
    """Compose extraction, normalization, validation, scoring, and routing."""
    record, fields, extraction_warnings = extract_document(
        ocr_pages, source_document, policy=policy,
    )
    report, breakdown, validation_warnings = validate_document(
        record, references=references, settings=settings, policy=policy,
    )
    record = record.model_copy(update={"validation_status": report.routing})
    return IntelligenceResult(
        record=record,
        fields=fields,
        validation=report,
        score_breakdown=breakdown,
        warnings=list(dict.fromkeys([*extraction_warnings, *validation_warnings])),
    )


def analyze_record(
    record: LandRecord,
    *,
    references: Sequence[LandRecord] = (),
    settings: Settings | None = None,
    policy: IntelligencePolicy | None = None,
) -> IntelligenceResult:
    """Validate an existing canonical record and retain its provenance."""
    record = LandRecord.model_validate(record)
    report, breakdown, warnings = validate_document(
        record, references=references, settings=settings, policy=policy,
    )
    values = record.model_dump(mode="python", by_alias=True)
    fields: list[ExtractedField] = []
    for field_name, evidence in record.provenance.items():
        value = values.get(field_name)
        if value is None:
            continue
        bbox = evidence.bounding_box
        fields.append(ExtractedField(
            field=field_name,
            value=value,
            confidence=evidence.confidence if evidence.confidence is not None else record.extraction_confidence.per_field.get(field_name),
            source=EvidenceSource(
                page=evidence.source_page or 1,
                bbox=(bbox.x, bbox.y, bbox.width, bbox.height) if bbox else None,
                bbox_coordinate_system="pixels" if bbox else "normalized",
                text=evidence.extracted_text,
            ),
            extraction_method=evidence.extraction_method or "existing-record-provenance",
            warnings=list(evidence.validation_results),
        ))
    return IntelligenceResult(
        record=record.model_copy(update={"validation_status": report.routing}),
        fields=fields,
        validation=report,
        score_breakdown=breakdown,
        warnings=warnings,
    )


__all__ = [
    "EvidenceSource", "ExtractedField", "IntelligencePolicy",
    "IntelligenceResult", "ScoreBreakdown", "analyze_document", "analyze_record",
    "extract_document", "validate_cross_system", "validate_document",
    "validate_field", "validate_record",
]
