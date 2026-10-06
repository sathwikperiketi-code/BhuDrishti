"""Versioned public contracts for uploaded document processing.

Bounding boxes in OCR regions and extracted-field evidence are normalized to
the range 0..1, unlike the legacy synthetic fixture's pixel coordinates.
"""

from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from typing import Any
from typing import Literal

from pydantic import Field

from .land_record import ContractModel
from .review import ReviewStatus


class DocumentStatus(StrEnum):
    UPLOADED = "uploaded"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"


class StageStatus(StrEnum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"


class StageProgress(ContractModel):
    stage: str
    status: StageStatus
    started_at: datetime | None = None
    completed_at: datetime | None = None
    message: str | None = None


class DocumentError(ContractModel):
    code: str
    message: str


class DocumentPage(ContractModel):
    page_number: int = Field(ge=1)
    image_url: str
    width: int = Field(gt=0)
    height: int = Field(gt=0)


class OCRRegion(ContractModel):
    text: str
    bbox: list[float] = Field(min_length=4, max_length=4)
    confidence: float | None = Field(default=None, ge=0, le=1)


class OCRPage(ContractModel):
    page_number: int = Field(ge=1)
    text: str
    width: int = Field(gt=0)
    height: int = Field(gt=0)
    confidence: float | None = Field(default=None, ge=0, le=1)
    regions: list[OCRRegion] = Field(default_factory=list)
    language: str | None = None


class DocumentSummary(ContractModel):
    id: str
    file_name: str
    mime_type: str
    file_size: int = Field(ge=0)
    page_count: int = Field(ge=1)
    language: str | None = None
    uploaded_at: datetime
    status: DocumentStatus
    review_status: ReviewStatus | None = None
    stage: str
    provider: str | None = None
    is_synthetic: bool = False
    dataset_scope: Literal["operational", "sample"] = "operational"
    dataset_reason: str | None = None


class DocumentDetail(DocumentSummary):
    updated_at: datetime
    processed_at: datetime | None = None
    attempts: int = 0
    pages: list[DocumentPage] = Field(default_factory=list)
    stages: list[StageProgress] = Field(default_factory=list)
    processing_metadata: dict[str, Any] = Field(default_factory=dict)
    ocr_pages: list[OCRPage] = Field(default_factory=list)
    extraction: dict[str, Any] | None = None
    fields: list[dict[str, Any]] = Field(default_factory=list)
    validation: dict[str, Any] | None = None
    score_breakdown: dict[str, Any] | None = None
    warnings: list[str] = Field(default_factory=list)
    error: DocumentError | None = None


class DocumentList(ContractModel):
    items: list[DocumentSummary]
    total: int


class ProcessingStatus(ContractModel):
    id: str
    status: DocumentStatus
    stage: str
    attempts: int
    stages: list[StageProgress]
    error: DocumentError | None = None
    updated_at: datetime
