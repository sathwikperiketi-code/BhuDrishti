"""Source-grounded extraction, validation, and scoring checks."""

from __future__ import annotations

from copy import deepcopy
from pathlib import Path

import pymupdf as fitz

from app.config import Settings
from app.contracts.land_record import AreaUnit, LandRecord, SourceDocument, ValidationStatus
from app.services.intelligence import (
    IntelligencePolicy,
    analyze_document,
    extract_document,
    validate_cross_system,
    validate_document,
    validate_field,
    validate_record,
)
from app.services.documents.ocr import PDFTextProvider


def _record(**changes: object) -> LandRecord:
    values = {
        "owner_name": "Ramesh Kumar", "survey_number": "142/3A",
        "record_number": "LR-2026-001", "area": 2.47,
        "area_unit": AreaUnit.ACRE, "village": "Rampur",
        "district": "Sangareddy", "state": "Telangana",
    }
    values.update(changes)
    return LandRecord(**values)


def test_extracts_canonical_fields_from_actual_pdf_text_and_coordinates(tmp_path: Path) -> None:
    path = Path(__file__).resolve().parents[2] / "samples" / "land-record.synthetic.pdf"
    with fitz.open(path) as pdf:
        image = tmp_path / "page.png"
        pdf[0].get_pixmap().save(image)
        page = PDFTextProvider().recognize(image, 1, pdf_page=pdf[0])
    record, fields, warnings = extract_document(
        [page], SourceDocument(document_id="source-pdf", file_name=path.name),
    )
    assert warnings == []
    assert record.owner_name == "Ramesh Kumar"
    assert record.survey_number == "314/7B"
    assert record.area == 2.47
    assert record.area_unit == AreaUnit.ACRE
    assert record.ownership_details is not None
    assert record.mutation_records[0].mutation_id == "MUT-2026-001"
    assert record.registration_information.registration_number == "REG-2026-001"
    survey = next(field for field in fields if field.field == "surveyNumber")
    assert survey.source.page == 1
    assert survey.source.bbox is not None
    assert survey.source.bbox_coordinate_system == "normalized"
    assert survey.extraction_method == "labeled-region-rule"
    assert record.provenance["surveyNumber"].bounding_box is not None
    assert record.provenance["surveyNumber"].bounding_box.width > 0
    assert record.extraction_confidence.overall is None
    assert survey.confidence is None


def test_plain_text_fallback_preserves_page_and_does_not_invent_box() -> None:
    source = SourceDocument(document_id="text-only", file_name="text.pdf")
    record, fields, _ = extract_document([{
        "page_number": 2,
        "text": "Owner Name: Asha Devi\nSurvey No.: 51/2\nArea: 1.2 hectares\nVillage: Eastbank\nDistrict: North\nState: Telangana",
        "width": 1000,
        "height": 1400,
        "confidence": None,
    }], source)
    assert record.survey_number == "51/2"
    assert record.area_unit == AreaUnit.HECTARE
    assert record.provenance["surveyNumber"].source_page == 2
    assert record.provenance["surveyNumber"].bounding_box is None
    assert next(field for field in fields if field.field == "surveyNumber").source.bbox is None


def test_region_confidence_is_not_overwritten_by_duplicate_page_text() -> None:
    source = SourceDocument(document_id="scanned-page", file_name="scan.png")
    page = {
        "page_number": 1, "text": "Area: 2.47 acres", "width": 1000, "height": 1400,
        "confidence": 0.91,
        "regions": [{"text": "Area: 2.47 acres", "bbox": [0.2, 0.3, 0.4, 0.03], "confidence": 0.43}],
    }
    record, fields, _ = extract_document(
        [page], source,
    )
    assert record.area == 2.47
    assert next(field for field in fields if field.field == "area").confidence == 0.43


def test_field_validation_flags_missing_format_range_unit_and_low_confidence() -> None:
    record = LandRecord.model_validate({
        "ownerName": "123",
        "surveyNumber": "???",
        "area": 0,
        "areaUnit": "unknown",
        "village": "Rampur",
        "district": "Sangareddy",
        "state": "Telangana",
        "extractionConfidence": {"overall": 0.4, "perField": {"surveyNumber": 0.4}},
    })
    score, issues = validate_field(record)
    codes = {issue.code for issue in issues}
    assert score < 60
    assert {"malformed_owner_name", "malformed_survey_number", "area_out_of_range",
            "unknown_area_unit", "low_extraction_confidence"} <= codes


def test_record_validation_completeness_and_duplicate_combination() -> None:
    incomplete = LandRecord(survey_number="142/3A")
    _, missing_issues = validate_record(incomplete)
    assert any(issue.code == "incomplete_record" for issue in missing_issues)

    record = _record()
    score, issues = validate_record(record, references=[_record()])
    assert score == 65
    assert any(issue.code == "duplicate_combination" for issue in issues)


def test_cross_system_conflicts_surface_expected_and_actual() -> None:
    record = _record()
    reference = LandRecord(
        owner_name="Ramesh Kumar", record_number="LR-2026-001",
        survey_number="142/3B", area=3.0, area_unit=AreaUnit.ACRE,
        village="Other Village", district="Sangareddy", state="Telangana",
    )
    score, issues = validate_cross_system(record, [reference])
    assert score == 0
    by_code = {issue.code: issue for issue in issues}
    assert by_code["survey_number_mismatch"].actual == "142/3A"
    assert by_code["survey_number_mismatch"].expected == "142/3B"
    assert by_code["village_mismatch"].actual == "Rampur"
    assert by_code["area_mismatch"].expected == 3.0


def test_related_references_disagree_and_area_units_are_not_compared_as_same_unit() -> None:
    record = _record(record_number="LR-2026-009")
    reference_a = _record(record_number="LR-2026-009")
    reference_b = _record(record_number="LR-2026-009", survey_number="142/3B")
    _, issues = validate_cross_system(record, [reference_a, reference_b])
    assert any(issue.code == "related_record_conflict" for issue in issues)

    changed_unit = _record(record_number="REF-142-3A", area_unit=AreaUnit.HECTARE)
    score, issues = validate_cross_system(record, [changed_unit])
    assert score == 25
    assert any(issue.code == "area_unit_mismatch" for issue in issues)
    assert not any(issue.code == "area_mismatch" for issue in issues)


def test_no_reference_does_not_count_as_passing_cross_system_check() -> None:
    report, breakdown, warnings = validate_document(_record())
    assert report.cross_system_score == 50
    assert report.routing == ValidationStatus.HUMAN_REVIEW
    assert any(issue.code == "reference_unavailable" for issue in report.issues)
    assert breakdown.warning_penalty == 7
    assert warnings


def test_scoring_is_transparent_and_thresholds_are_configurable() -> None:
    settings = Settings(_env_file=None, reject_threshold=70, approve_threshold=90)
    report, breakdown, _ = validate_document(
        _record(record_number="LR-2026-003"),
        references=[LandRecord(
            record_number="LR-2026-003", survey_number="142/3B",
            area=2.47, area_unit=AreaUnit.ACRE, village="Rampur",
        )],
        settings=settings,
        policy=IntelligencePolicy(warning_penalty=5),
    )
    assert breakdown.field_weight == 0.5
    assert breakdown.record_weight == 0.3
    assert breakdown.cross_system_weight == 0.2
    assert breakdown.field_contribution == 50
    assert breakdown.record_contribution == 30
    assert breakdown.cross_system_contribution == 5
    assert breakdown.warning_penalty == 5
    assert breakdown.quality_score == report.quality_score == 80
    assert report.routing == ValidationStatus.HUMAN_REVIEW
    assert breakdown.reject_below == 70
    assert breakdown.approve_at_or_above == 90


def test_analysis_composes_real_extraction_validation_and_evidence() -> None:
    page = {
        "page_number": 1, "width": 1000, "height": 1400,
        "text": "Owner Name: Ramesh Kumar\nSurvey No: 142/3A\nArea: 2.47 acres\nVillage: Rampur\nDistrict: Sangareddy\nState: Telangana\nRecord No: LR-2026-003",
        "regions": [],
    }
    reference = _record(record_number="LR-2026-003", survey_number="142/3B")
    analysis = analyze_document(
        [page], SourceDocument(document_id="actual-text", file_name="record.pdf"),
        references=[reference],
    )
    assert analysis.validation.routing == ValidationStatus.HUMAN_REVIEW
    assert any(issue.code == "survey_number_mismatch" for issue in analysis.validation.issues)
    assert analysis.record.survey_number == "142/3A"
    assert analysis.fields[0].source.text in page["text"]
    assert analysis.score_breakdown == analyze_document(
        [page], SourceDocument(document_id="actual-text", file_name="record.pdf"),
        references=[reference],
    ).score_breakdown


def test_invalid_box_is_ignored_without_inventing_coordinates() -> None:
    page = {
        "page_number": 1, "width": 1000, "height": 1400,
        "text": "Owner Name: Ramesh Kumar",
        "regions": [{"text": "Owner Name: Ramesh Kumar", "bbox": [0.1, 0.1, 0.4, 0.03]}],
    }
    page = deepcopy(page)
    page["regions"][0]["bbox"] = [-1, 0, 1, 1]
    record, fields, _ = extract_document([page], SourceDocument(document_id="invalid-box", file_name="box.pdf"))
    assert record.owner_name == "Ramesh Kumar"
    assert next(field for field in fields if field.field == "ownerName").source.bbox is None
