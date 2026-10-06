"""Serializable outputs from deterministic document intelligence.

The confidence values in these models describe extraction evidence.  They are
heuristic signals, not probabilities of ownership or legal verification.
"""

from __future__ import annotations

from typing import Any

from pydantic import Field

from app.contracts.land_record import ContractModel, LandRecord, ValidationStatus
from app.contracts.processing import ValidationReport


class EvidenceSource(ContractModel):
    page: int = Field(ge=1)
    bbox: tuple[float, float, float, float] | None = None
    bbox_coordinate_system: str = "normalized"
    text: str | None = None


class ExtractedField(ContractModel):
    field: str = Field(min_length=1)
    value: Any
    confidence: float | None = Field(default=None, ge=0, le=1)
    source: EvidenceSource
    extraction_method: str
    warnings: list[str] = Field(default_factory=list)


class ScoreBreakdown(ContractModel):
    field_weight: float
    record_weight: float
    cross_system_weight: float
    field_contribution: float
    record_contribution: float
    cross_system_contribution: float
    warning_penalty: float
    unrounded_total: float
    quality_score: float
    reject_below: float
    approve_at_or_above: float
    routing: ValidationStatus


class IntelligenceResult(ContractModel):
    record: LandRecord
    fields: list[ExtractedField]
    validation: ValidationReport
    score_breakdown: ScoreBreakdown
    warnings: list[str] = Field(default_factory=list)
    review_notice: str = (
        "AI-assisted extraction and validation. Human officers remain responsible "
        "for final verification and approval."
    )
