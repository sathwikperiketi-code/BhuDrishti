"""Contracts shared by processing providers and validation services."""

from __future__ import annotations

from datetime import datetime, timezone
from enum import StrEnum
from typing import Any

from pydantic import Field

from .land_record import ContractModel, LandRecord, ValidationStatus


class ProcessingStage(StrEnum):
    UPLOAD = "upload"
    PREPROCESSING = "preprocessing"
    LANGUAGE_DETECTION = "language_detection"
    OCR = "ocr"
    FIELD_EXTRACTION = "field_extraction"
    NORMALIZATION = "normalization"
    VALIDATION = "validation"
    QUALITY_SCORE = "quality_score"
    FINAL_ROUTING = "final_routing"


class ValidationLevel(StrEnum):
    FIELD = "field"
    RECORD = "record"
    CROSS_SYSTEM = "cross_system"


class ValidationIssue(ContractModel):
    level: ValidationLevel
    code: str = Field(min_length=1)
    message: str = Field(min_length=1)
    field_name: str | None = None
    severity: str = "warning"
    expected: Any | None = None
    actual: Any | None = None


class ValidationReport(ContractModel):
    """Independent validation scores and the resulting review route."""

    field_score: float = Field(ge=0, le=100)
    record_score: float = Field(ge=0, le=100)
    cross_system_score: float = Field(ge=0, le=100)
    quality_score: float = Field(ge=0, le=100)
    routing: ValidationStatus
    issues: list[ValidationIssue] = Field(default_factory=list)
    generated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class ProviderExtraction(ContractModel):
    """Result returned by an OCR/document-understanding provider."""

    provider: str = Field(min_length=1)
    document_id: str = Field(min_length=1)
    record: LandRecord
    stages: list[ProcessingStage] = Field(default_factory=list)
    raw_text: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)
    extracted_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class ProviderHealth(ContractModel):
    provider: str = Field(min_length=1)
    available: bool
    deterministic: bool = True
    message: str | None = None
    pdf_text_available: bool | None = None
    ocr_available: bool | None = None
    installed_languages: list[str] = Field(default_factory=list)
    requested_languages: list[str] = Field(default_factory=list)
    unsupported_languages: list[str] = Field(default_factory=list)
