"""Canonical land-record contracts.

The canonical record is deliberately explicit.  New source-specific metadata can be
added under ``extensions`` and provenance is kept in a separate, typed map; callers
cannot silently add database columns by returning arbitrary model fields.
"""

from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from enum import StrEnum
from typing import Any
from uuid import UUID, uuid4

from pydantic import BaseModel, ConfigDict, Field, field_validator


class ContractModel(BaseModel):
    """Base contract configuration shared by request and response models."""

    model_config = ConfigDict(
        alias_generator=lambda name: _to_camel(name),
        populate_by_name=True,
        extra="forbid",
        use_enum_values=False,
    )


def _to_camel(name: str) -> str:
    parts = name.split("_")
    return parts[0] + "".join(part[:1].upper() + part[1:] for part in parts[1:])


class AreaUnit(StrEnum):
    """Units accepted by the normalization and validation layers."""

    ACRE = "acre"
    HECTARE = "hectare"
    SQUARE_METER = "square_meter"
    SQUARE_FEET = "square_feet"
    GUNTHA = "guntha"
    CENT = "cent"
    UNKNOWN = "unknown"


class LandClassification(StrEnum):
    AGRICULTURAL = "agricultural"
    RESIDENTIAL = "residential"
    COMMERCIAL = "commercial"
    FOREST = "forest"
    WATER = "water"
    GOVERNMENT = "government"
    OTHER = "other"
    UNKNOWN = "unknown"


class ValidationStatus(StrEnum):
    PENDING = "pending"
    APPROVED = "approved"
    HUMAN_REVIEW = "human_review"
    REJECTED = "rejected"


class BoundingBox(ContractModel):
    """Document coordinates in pixels, relative to the source page."""

    x: float = Field(ge=0)
    y: float = Field(ge=0)
    width: float = Field(gt=0)
    height: float = Field(gt=0)


class FieldProvenance(ContractModel):
    """Evidence attached to one extracted field."""

    source_page: int | None = Field(default=None, ge=1)
    bounding_box: BoundingBox | None = None
    extracted_text: str | None = None
    confidence: float | None = Field(default=None, ge=0, le=1)
    extraction_method: str | None = None
    validation_results: list[str] = Field(default_factory=list)


class SourceDocument(ContractModel):
    """Identity and provenance of an uploaded source document."""

    document_id: str = Field(min_length=1)
    file_name: str = Field(min_length=1)
    mime_type: str | None = None
    sha256: str | None = Field(default=None, min_length=16)
    page_count: int | None = Field(default=None, ge=1)
    language: str | None = None
    uploaded_at: datetime | None = None
    is_synthetic: bool = False


class OwnershipDetails(ContractModel):
    """Ownership information as transcribed from a record.

    This is descriptive evidence only; it does not make a legal determination.
    """

    owners: list[str] = Field(default_factory=list)
    share_fraction: Decimal | None = Field(default=None, ge=Decimal("0"), le=Decimal("1"))
    tenure_type: str | None = None
    notes: str | None = None

    @field_validator("owners")
    @classmethod
    def normalize_owner_names(cls, owners: list[str]) -> list[str]:
        return [owner.strip() for owner in owners if owner.strip()]


class MutationRecord(ContractModel):
    mutation_id: str = Field(min_length=1)
    mutation_date: date | None = None
    mutation_type: str | None = None
    status: str | None = None
    details: str | None = None


class RegistrationInformation(ContractModel):
    registration_number: str | None = None
    registration_date: date | None = None
    sub_registrar_office: str | None = None
    deed_type: str | None = None


class ExtractionConfidence(ContractModel):
    """Measured OCR signals, never legal conclusions.

    ``None`` means the source provides no measurable recognition confidence,
    as with text embedded in a PDF. It must not be presented as a percentage.
    """

    overall: float | None = Field(default=None, ge=0, le=1)
    per_field: dict[str, float] = Field(default_factory=dict)

    @field_validator("per_field")
    @classmethod
    def validate_field_confidence(cls, values: dict[str, float]) -> dict[str, float]:
        for field_name, confidence in values.items():
            if not 0 <= confidence <= 1:
                raise ValueError(f"confidence for {field_name!r} must be between 0 and 1")
        return values


class LandRecord(ContractModel):
    """Canonical, extensible record returned by extraction and validation services."""

    record_id: UUID = Field(default_factory=uuid4)
    owner_name: str | None = None
    father_or_guardian_name: str | None = None
    survey_number: str | None = None
    khasra_number: str | None = None
    khata_number: str | None = None
    record_number: str | None = None
    area: float | None = Field(default=None, ge=0)
    area_unit: AreaUnit | None = None
    village: str | None = None
    mandal_or_tehsil: str | None = None
    district: str | None = None
    state: str | None = None
    land_classification: LandClassification | None = None
    ownership_details: OwnershipDetails | None = None
    mutation_records: list[MutationRecord] = Field(default_factory=list)
    registration_information: RegistrationInformation | None = None
    source_document: SourceDocument | None = None
    extraction_confidence: ExtractionConfidence = Field(
        default_factory=ExtractionConfidence
    )
    validation_status: ValidationStatus = ValidationStatus.PENDING
    provenance: dict[str, FieldProvenance] = Field(default_factory=dict)
    extensions: dict[str, Any] = Field(default_factory=dict)

    @field_validator(
        "owner_name",
        "father_or_guardian_name",
        "survey_number",
        "khasra_number",
        "khata_number",
        "record_number",
        "village",
        "mandal_or_tehsil",
        "district",
        "state",
        mode="before",
    )
    @classmethod
    def blank_strings_are_missing(cls, value: str | None) -> str | None:
        if isinstance(value, str):
            value = value.strip()
            return value or None
        return value
