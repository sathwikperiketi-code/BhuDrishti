"""Synthetic OCR records used only by automated tests."""

from __future__ import annotations

from datetime import datetime, timezone
from uuid import NAMESPACE_URL, uuid5

from app.contracts.land_record import AreaUnit, LandRecord, SourceDocument
from app.services.intelligence import analyze_document
from app.services.intelligence.models import IntelligenceResult


DEMO_CASE_IDS = (
    "clean-record",
    "low-confidence-area",
    "survey-conflict",
    "missing-field",
    "duplicate-record",
)

_BASE_LINES: list[tuple[str, str, float]] = [
    ("Owner Name", "Ramesh Kumar", 0.97),
    ("Father or Guardian Name", "Suresh Kumar", 0.95),
    ("Survey No.", "142/3A", 0.94),
    ("Khasra No.", "142/3A", 0.93),
    ("Khata No.", "8291", 0.94),
    ("Record No.", "LR-2026-001", 0.95),
    ("Area", "2.47 acres", 0.96),
    ("Village", "Rampur", 0.95),
    ("Mandal", "Sangareddy", 0.94),
    ("District", "Sangareddy", 0.95),
    ("State", "Telangana", 0.96),
    ("Land Classification", "Agricultural", 0.92),
    ("Ownership Details", "1/1 share", 0.89),
    ("Mutation Records", "MUT-2026-001, 2026-01-03, transfer", 0.88),
    ("Registration Information", "REG-2026-001, 2026-01-02", 0.90),
]


def demo_ocr_pages(case_id: str) -> list[dict[str, object]]:
    """Return an explicit synthetic OCR page; never accepts uploaded bytes."""
    if case_id not in DEMO_CASE_IDS:
        raise ValueError(f"Unknown synthetic case: {case_id}")
    lines = list(_BASE_LINES)
    if case_id == "low-confidence-area":
        lines = [
            (label, value, 0.43 if label == "Area" else confidence)
            for label, value, confidence in lines
        ]
    if case_id == "missing-field":
        lines = [item for item in lines if item[0] != "Owner Name"]
    record_numbers = {
        "clean-record": "LR-2026-001",
        "low-confidence-area": "LR-2026-002",
        "survey-conflict": "LR-2026-003",
        "missing-field": "LR-2026-004",
        "duplicate-record": "LR-2026-001",
    }
    lines = [
        (label, record_numbers[case_id] if label == "Record No." else value, confidence)
        for label, value, confidence in lines
    ]
    regions: list[dict[str, object]] = []
    positions = {
        "Owner Name": 0.234, "Father or Guardian Name": 0.274,
        "Survey No.": 0.311, "Khasra No.": 0.350,
        "Khata No.": 0.389, "Record No.": 0.426,
        "Area": 0.466, "Village": 0.548, "Mandal": 0.587,
        "District": 0.626, "State": 0.665,
        "Land Classification": 0.704, "Ownership Details": 0.743,
        "Mutation Records": 0.782, "Registration Information": 0.821,
    }
    for label, value, confidence in lines:
        regions.append({
            "text": f"{label}: {value}",
            "bbox": [0.16, positions[label], 0.60, 0.036],
            "confidence": confidence,
        })
    return [{
        "page_number": 1,
        "text": "\n".join(str(region["text"]) for region in regions),
        "width": 1000,
        "height": 1400,
        "confidence": 0.93,
        "regions": regions,
        "language": "en",
    }]


def demo_source_document(case_id: str) -> SourceDocument:
    if case_id not in DEMO_CASE_IDS:
        raise ValueError(f"Unknown synthetic case: {case_id}")
    return SourceDocument(
        document_id=case_id,
        file_name=f"{case_id}.synthetic.pdf",
        mime_type="application/pdf",
        page_count=1,
        language="en",
        uploaded_at=datetime(2026, 1, 1, tzinfo=timezone.utc),
        is_synthetic=True,
    )


def demo_references(
    case_id: str,
    *,
    extracted_record: LandRecord | None = None,
) -> list[LandRecord]:
    """Supply deterministic comparison records with intentional differences."""
    if case_id not in DEMO_CASE_IDS and case_id not in {"poor-quality-document", "human-correction"}:
        raise ValueError(f"Unknown synthetic case: {case_id}")
    survey = "142/3A"
    if case_id == "survey-conflict":
        # The Phase 1 fixture used the inverse synthetic survey value from the
        # new OCR scenario. Keep either comparison demonstrably conflicting.
        survey = "142/3A" if extracted_record and extracted_record.survey_number == "142/3B" else "142/3B"
    record_number = {
        "survey-conflict": "LR-2026-003",
        "duplicate-record": "LR-2026-001",
    }.get(case_id, "REF-142-3A")
    return [LandRecord(
        owner_name="Ramesh Kumar",
        survey_number=survey,
        khasra_number=survey,
        khata_number="8291",
        record_number=record_number,
        area=2.47,
        area_unit=AreaUnit.ACRE,
        village="Rampur",
        mandal_or_tehsil="Sangareddy",
        district="Sangareddy",
        state="Telangana",
    )]


def analyze_demo_case(case_id: str) -> IntelligenceResult:
    """Run an isolated synthetic fixture through the same analysis functions."""
    result = analyze_document(
        demo_ocr_pages(case_id), demo_source_document(case_id),
        references=demo_references(case_id),
    )
    return result.model_copy(update={
        "record": result.record.model_copy(update={
            "record_id": uuid5(NAMESPACE_URL, f"bhudrishti-intelligence-test:{case_id}"),
        }),
        "validation": result.validation.model_copy(update={
            "generated_at": result.record.source_document.uploaded_at,
        }),
        "warnings": ["Synthetic test fixture; not an official land record.", *result.warnings],
    })
