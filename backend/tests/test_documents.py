"""End-to-end checks for real uploaded bytes, durable stages, and safe intake."""

from __future__ import annotations

from hashlib import sha256
from io import BytesIO
from pathlib import Path
from uuid import uuid4

import pymupdf as fitz
from fastapi.testclient import TestClient
from PIL import Image, ImageDraw, ImageFont
import pytest
from sqlalchemy import select
from sqlalchemy.orm import sessionmaker

from app.config import Settings, get_settings
from app.contracts.auth import Role
from app.db.base import Base
from app.db.models import AuditEventModel, DocumentModel, LandRecordModel, ReviewCaseModel
from app.db.session import build_engine, get_db
from app.main import app
from app.services.auth.service import create_user
from app.services.documents import pipeline
from app.services.documents.ocr import LocalOCRProvider, OCRUnavailableError, local_ocr_capabilities
from app.services.documents.storage import document_dir
from app.services.intelligence.extraction import extract_document
from app.contracts.land_record import AreaUnit, LandRecord, SourceDocument, ValidationStatus


@pytest.fixture
def live_client(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    settings = Settings(
        _env_file=None,
        database_url=f"sqlite:///{(tmp_path / 'documents.db').as_posix()}",
        document_storage_dir=str(tmp_path / "uploads"),
        upload_max_bytes=2 * 1024 * 1024,
    )
    engine = build_engine(settings.database_url)
    Base.metadata.create_all(bind=engine)
    factory = sessionmaker(bind=engine, autoflush=False, autocommit=False, expire_on_commit=False)
    with factory() as session:
        create_user(session, email="officer@example.test", name="Test Officer", password="test-officer-password", role=Role.REVENUE_OFFICER)
        create_user(session, email="auditor@example.test", name="Test Auditor", password="test-auditor-password", role=Role.AUDITOR)
        session.commit()

    def override_db():
        with factory() as session:
            yield session

    app.dependency_overrides[get_db] = override_db
    app.dependency_overrides[get_settings] = lambda: settings
    monkeypatch.setattr(pipeline, "SessionLocal", factory)
    with TestClient(app) as client:
        login = client.post("/api/v1/auth/login", json={"email": "officer@example.test", "password": "test-officer-password"})
        assert login.status_code == 200
        client.headers.update({"Authorization": f"Bearer {login.json()['accessToken']}"})
        yield client, settings, factory
    app.dependency_overrides.clear()
    engine.dispose()


def _pdf_bytes(
    pages: int = 1, *, survey: str = "142/3A", owner: str = "Ramesh Kumar",
    record_number: str = "LR-2026-001",
) -> bytes:
    document = fitz.open()
    for index in range(pages):
        page = document.new_page(width=600, height=800)
        page.insert_text(
            (70, 100),
            f"Land Record\nOwner Name: {owner}\nSurvey No: {survey}\n"
            f"Record No: {record_number}\nArea: 2.47 acres\nVillage: Rampur\n"
            "District: Sangareddy\nState: Telangana",
            fontsize=15,
        )
        page.insert_text((70, 380), f"Page {index + 1}", fontsize=15)
    output = document.tobytes()
    document.close()
    return output


def _png_bytes() -> bytes:
    image = Image.new("RGB", (1400, 950), "white")
    draw = ImageDraw.Draw(image)
    font_path = Path(r"C:\Windows\Fonts\arial.ttf")
    font = ImageFont.truetype(str(font_path), 50) if font_path.is_file() else ImageFont.load_default()
    for index, line in enumerate((
        "Owner Name: Ramesh Kumar", "Survey No: 142/3A", "Area: 2.47 acres",
        "Village: Rampur", "District: Sangareddy", "State: Telangana",
    )):
        draw.text((80, 100 + index * 110), line, fill="black", font=font)
    output = BytesIO()
    image.save(output, format="PNG")
    return output.getvalue()


def _scanned_pdf_bytes() -> bytes:
    compressed = BytesIO()
    with Image.open(BytesIO(_png_bytes())) as image:
        image.save(compressed, format="JPEG", quality=88)
    document = fitz.open()
    page = document.new_page(width=1400, height=950)
    page.insert_image(page.rect, stream=compressed.getvalue())
    page.insert_text((15, 940), "Scanned with Adobe Scan", fontsize=7)
    output = document.tobytes()
    document.close()
    return output


def test_upload_validates_signature_type_size_and_filename(live_client) -> None:
    client, settings, _ = live_client
    pdf = _pdf_bytes()
    response = client.post("/api/v1/documents/upload", files={"file": ("record.pdf", pdf, "application/pdf")})
    assert response.status_code == 201
    detail = response.json()
    assert detail["fileName"] == "record.pdf"
    assert detail["mimeType"] == "application/pdf"
    assert detail["fileSize"] == len(pdf)
    assert detail["pageCount"] == 1
    assert detail["status"] == "uploaded"
    assert detail["isSynthetic"] is False
    assert "storageKey" not in detail
    assert "document_storage" not in str(detail)
    assert detail["pages"][0]["imageUrl"].startswith("/api/v1/documents/")
    assert client.get(detail["pages"][0]["imageUrl"]).content.startswith(b"\x89PNG")
    with TestClient(app) as anonymous:
        assert anonymous.get(detail["pages"][0]["imageUrl"]).status_code == 401
    auditor = client.post("/api/v1/auth/login", json={"email": "auditor@example.test", "password": "test-auditor-password"}).json()
    assert client.get(detail["pages"][0]["imageUrl"], headers={"Authorization": f"Bearer {auditor['accessToken']}"}).status_code == 200
    assert client.get("/api/v1/documents").json()["total"] == 1

    mismatched = client.post("/api/v1/documents/upload", files={"file": ("spoof.pdf", _png_bytes(), "application/pdf")})
    assert mismatched.status_code == 400
    assert mismatched.json()["detail"]["code"] == "invalid_signature"
    unsupported = client.post("/api/v1/documents/upload", files={"file": ("record.txt", b"hello", "text/plain")})
    assert unsupported.status_code == 400
    assert unsupported.json()["detail"]["code"] == "unsupported_file"
    unsafe = client.post("/api/v1/documents/upload", files={"file": ("../record.pdf", pdf, "application/pdf")})
    assert unsafe.status_code == 400
    assert unsafe.json()["detail"]["code"] == "unsafe_filename"
    too_large = client.post("/api/v1/documents/upload", files={"file": ("large.pdf", b"%PDF-" + b"x" * (settings.upload_max_bytes + 1), "application/pdf")})
    assert too_large.status_code == 413
    assert too_large.json()["detail"]["code"] == "file_too_large"


def test_pdf_pages_and_complete_processing_are_persisted(live_client) -> None:
    client, _, factory = live_client
    uploaded = client.post("/api/v1/documents/upload", files={"file": ("two-pages.pdf", _pdf_bytes(2), "application/pdf")}).json()
    document_id = uploaded["id"]
    assert uploaded["pageCount"] == 2
    assert client.get(uploaded["pages"][1]["imageUrl"]).status_code == 200

    started = client.post(f"/api/v1/documents/{document_id}/process")
    assert started.status_code == 202
    detail = client.get(f"/api/v1/documents/{document_id}").json()
    assert detail["status"] == "completed", detail.get("error")
    assert detail["provider"] == "pdf-embedded-text"
    assert detail["processingMetadata"]["pagesProcessed"] == 2
    assert detail["processingMetadata"]["denoise"] is True
    assert detail["ocrPages"][0]["text"].startswith("Land Record")
    assert detail["extraction"]["ownerName"] == "Ramesh Kumar"
    assert detail["extraction"]["sourceDocument"]["isSynthetic"] is False
    assert detail["validation"]["routing"] in {"approved", "human_review", "rejected"}
    assert detail["scoreBreakdown"]["qualityScore"] == detail["validation"]["qualityScore"]
    assert all(stage["status"] == "completed" for stage in detail["stages"])
    survey = next(field for field in detail["fields"] if field["field"] == "surveyNumber")
    assert survey["source"]["page"] == 1
    assert survey["source"]["bbox"] is not None
    assert all(0 <= value <= 1 for value in survey["source"]["bbox"])
    assert client.get(f"/api/v1/documents/{document_id}/processing-status").json()["status"] == "completed"
    with factory() as session:
        stored = session.scalar(select(LandRecordModel).where(LandRecordModel.source_document_id == document_id))
        assert stored is not None
        assert stored.payload["surveyNumber"] == "142/3A"


def test_uploaded_two_column_pdf_extracts_real_cells_and_persists_evidence(live_client) -> None:
    client, _, factory = live_client
    sample = Path(__file__).resolve().parents[2] / "samples" / "sample_land_record_demo.pdf"
    uploaded = client.post(
        "/api/v1/documents/upload",
        files={"file": (sample.name, sample.read_bytes(), "application/pdf")},
    ).json()
    assert client.post(f"/api/v1/documents/{uploaded['id']}/process").status_code == 202
    assert client.get(f"/api/v1/documents/{uploaded['id']}").status_code == 404
    detail = client.get(f"/api/v1/documents/{uploaded['id']}", params={"dataset": "sample"}).json()
    assert detail["status"] == "completed", detail.get("error")
    assert detail["provider"] == "pdf-embedded-text"
    assert detail["extraction"]["ownerName"] == "Ravi Kumar"
    assert detail["extraction"]["surveyNumber"] == "123/4A"
    assert detail["extraction"]["khasraNumber"] == "123/4A"
    assert detail["extraction"]["area"] == 2.5
    assert detail["extraction"]["areaUnit"] == "acre"
    assert detail["extraction"]["mandalOrTehsil"] == "Sample Mandal"
    assert detail["extraction"]["state"] is None  # Not present in this source.
    assert detail["isSynthetic"] is True
    assert detail["extraction"]["sourceDocument"]["isSynthetic"] is True
    assert detail["scoreBreakdown"]["qualityScore"] > 27
    assert detail["extraction"]["extractionConfidence"]["overall"] is None
    survey = next(field for field in detail["fields"] if field["field"] == "surveyNumber")
    assert survey["value"] == "123/4A"
    assert survey["confidence"] is None
    assert survey["extractionMethod"] == "aligned-table-cell-rule"
    assert survey["source"]["text"] == "Survey / Khasra No.: 123/4A"
    assert survey["source"]["page"] == 1
    assert survey["source"]["bbox"][0] > 0.35  # The value cell, not the label.
    with factory() as session:
        stored = session.get(DocumentModel, uploaded["id"])
        record = session.scalar(select(LandRecordModel).where(LandRecordModel.source_document_id == uploaded["id"]))
        assert stored is not None and stored.ocr_pages[0]["text"].find("123/4A") >= 0
        assert record is not None and record.payload["surveyNumber"] == "123/4A"
        assert record.payload["provenance"]["surveyNumber"]["extractedText"] == "Survey / Khasra No.: 123/4A"


def test_raster_upload_uses_actual_local_ocr_when_available(live_client) -> None:
    client, settings, _ = live_client
    try:
        LocalOCRProvider(settings)
    except OCRUnavailableError:
        pytest.skip("Local Tesseract is unavailable on this host")
    uploaded = client.post("/api/v1/documents/upload", files={"file": ("scan.png", _png_bytes(), "image/png")}).json()
    document_id = uploaded["id"]
    assert client.post(f"/api/v1/documents/{document_id}/process").status_code == 202
    detail = client.get(f"/api/v1/documents/{document_id}").json()
    assert detail["status"] == "completed", detail.get("error")
    assert detail["provider"] == "tesseract-local"
    assert "Owner Name" in detail["ocrPages"][0]["text"]
    assert detail["extraction"]["surveyNumber"] == "142/3A"


def test_scanned_pdf_uses_actual_tesseract_when_available(live_client) -> None:
    client, settings, _ = live_client
    if not local_ocr_capabilities(settings)["available"]:
        pytest.skip("Configured Tesseract language models are unavailable")
    upload_response = client.post(
        "/api/v1/documents/upload",
        files={"file": ("scan.pdf", _scanned_pdf_bytes(), "application/pdf")},
    )
    assert upload_response.status_code == 201, upload_response.text
    uploaded = upload_response.json()
    assert client.post(f"/api/v1/documents/{uploaded['id']}/process").status_code == 202
    detail = client.get(f"/api/v1/documents/{uploaded['id']}").json()
    assert detail["status"] == "completed", detail.get("error")
    assert detail["provider"] == "tesseract-local"
    assert detail["extraction"]["surveyNumber"] == "142/3A"
    assert detail["extraction"]["area"] == 2.47
    assert next(field for field in detail["fields"] if field["field"] == "surveyNumber")["confidence"] is not None


def test_multiple_real_documents_keep_processing_failure_and_evidence_isolated(live_client) -> None:
    client, settings, factory = live_client
    if not local_ocr_capabilities(settings)["available"]:
        pytest.skip("Configured Tesseract language models are unavailable")

    pdf_a = _pdf_bytes(2, survey="501/1A", owner="Anita Rao", record_number="LR-2026-501")
    pdf_b = _pdf_bytes(survey="502/1B", owner="Meera Rao", record_number="LR-2026-502")
    image_c = _png_bytes()
    inputs = (
        ("a.pdf", pdf_a, "application/pdf"),
        ("b.pdf", pdf_b, "application/pdf"),
        ("c.png", image_c, "image/png"),
        ("retry.png", image_c, "image/png"),
    )
    auditor_login = client.post("/api/v1/auth/login", json={
        "email": "auditor@example.test", "password": "test-auditor-password",
    })
    assert auditor_login.status_code == 200
    auditor_headers = {"Authorization": f"Bearer {auditor_login.json()['accessToken']}"}
    assert client.post("/api/v1/documents/upload", headers=auditor_headers,
                       files={"file": inputs[0]}).status_code == 403

    uploads: dict[str, dict] = {}
    for filename, content, mime in inputs:
        response = client.post("/api/v1/documents/upload", files={"file": (filename, content, mime)})
        assert response.status_code == 201, response.text
        item = response.json()
        assert item["status"] == "uploaded" and item["fileName"] == filename
        assert item["datasetScope"] == "operational"
        uploads[filename] = item
    ids = {item["id"] for item in uploads.values()}
    assert len(ids) == len(inputs)
    listed = client.get("/api/v1/documents").json()
    assert listed["total"] == len(inputs)
    assert {item["id"] for item in listed["items"]} == ids

    completed: dict[str, dict] = {}
    for filename, expected_survey in (("a.pdf", "501/1A"), ("b.pdf", "502/1B"), ("c.png", "142/3A")):
        document_id = uploads[filename]["id"]
        started = client.post(f"/api/v1/documents/{document_id}/process")
        assert started.status_code == 202, started.text
        assert started.json()["status"] == "processing"
        detail = client.get(f"/api/v1/documents/{document_id}").json()
        assert detail["status"] == "completed", detail.get("error")
        assert detail["extraction"]["surveyNumber"] == expected_survey
        assert detail["extraction"]["sourceDocument"]["documentId"] == document_id
        assert detail["validation"] is not None and detail["scoreBreakdown"] is not None
        assert all(stage["status"] == "completed" for stage in detail["stages"])
        completed[filename] = detail
    assert completed["a.pdf"]["provider"] == completed["b.pdf"]["provider"] == "pdf-embedded-text"
    assert completed["c.png"]["provider"] == "tesseract-local"
    assert completed["a.pdf"]["pageCount"] == 2
    assert len({detail["extraction"]["recordId"] for detail in completed.values()}) == 3

    failed_id = uploads["retry.png"]["id"]
    settings.ocr_provider = "pdf_text"
    failed_start = client.post(f"/api/v1/documents/{failed_id}/process")
    assert failed_start.status_code == 202
    failed = client.get(f"/api/v1/documents/{failed_id}").json()
    assert failed["status"] == "failed" and failed["attempts"] == 1
    assert failed["error"]["code"] == "ocr_unavailable"
    assert failed["validation"] is None and failed["extraction"] is None
    for filename, snapshot in completed.items():
        current = client.get(f"/api/v1/documents/{uploads[filename]['id']}").json()
        assert current["status"] == "completed"
        assert current["extraction"] == snapshot["extraction"]
        assert current["validation"] == snapshot["validation"]
    assert client.post(f"/api/v1/documents/{uploads['a.pdf']['id']}/process",
                       headers=auditor_headers).status_code == 403
    assert client.get(f"/api/v1/documents/{failed_id}", headers=auditor_headers).status_code == 200

    settings.ocr_provider = "auto"
    retried = client.post(f"/api/v1/documents/{failed_id}/process")
    assert retried.status_code == 202
    recovered = client.get(f"/api/v1/documents/{failed_id}").json()
    assert recovered["status"] == "completed" and recovered["attempts"] == 2
    assert recovered["provider"] == "tesseract-local"
    assert recovered["extraction"]["surveyNumber"] == "142/3A"
    assert recovered["validation"] is not None

    all_details = {**completed, "retry.png": recovered}
    for filename, content, _ in inputs:
        detail = all_details[filename]
        document_id = uploads[filename]["id"]
        page = client.get(detail["pages"][0]["imageUrl"])
        assert page.status_code == 200 and page.content.startswith(b"\x89PNG")
        events = client.get("/api/v1/audit/events", params={
            "recordId": detail["extraction"]["recordId"],
        }).json()["items"]
        assert events and all(event["documentId"] == document_id for event in events)
        assert any(event["eventType"] == "DOCUMENT_UPLOADED" for event in events)
        assert any(event["eventType"] == "OCR_COMPLETED" for event in events)
        if filename == "retry.png":
            assert any(event["eventType"] == "PROCESSING_FAILED" for event in events)
        with factory() as session:
            stored = session.get(DocumentModel, document_id)
            assert stored is not None and stored.sha256 == sha256(content).hexdigest()
            assert (document_dir(settings, stored.storage_key) / "original.bin").read_bytes() == content
    with factory() as session:
        keys = [session.get(DocumentModel, document_id).storage_key for document_id in ids]
        assert len(set(keys)) == len(keys)
    assert client.get(f"/api/v1/documents/{uploads['a.pdf']['id']}").json()["extraction"]["surveyNumber"] == "501/1A"
    assert client.get(f"/api/v1/documents/{uploads['c.png']['id']}").json()["extraction"]["surveyNumber"] == "142/3A"
    assert client.get(f"/api/v1/documents/{uploads['b.pdf']['id']}").json()["extraction"]["surveyNumber"] == "502/1B"


def test_unmatched_labels_do_not_become_values() -> None:
    record, fields, _ = extract_document(
        [{"page_number": 1, "width": 600, "height": 800,
          "text": "Owner Name\nSurvey No.\nLand Area\nRegistration Status", "regions": []}],
        SourceDocument(document_id="labels-only", file_name="labels.pdf"),
    )
    assert record.owner_name is None
    assert record.survey_number is None
    assert record.area is None
    assert fields == []


def test_unavailable_ocr_language_is_reported_before_processing(live_client) -> None:
    _, settings, _ = live_client
    settings.ocr_language = "unsupported_test_language"
    capabilities = local_ocr_capabilities(settings)
    assert capabilities["available"] is False
    assert capabilities["unsupported_languages"] == ["unsupported_test_language"]
    with pytest.raises(OCRUnavailableError, match="not installed"):
        LocalOCRProvider(settings)


def test_high_scoring_upload_still_waits_for_an_officer(live_client) -> None:
    client, _, factory = live_client
    reference = LandRecord(
        record_id=uuid4(), owner_name="Ramesh Kumar", survey_number="142/3A",
        record_number="EXTERNAL-REFERENCE-1", area=2.47, area_unit=AreaUnit.ACRE,
        village="Rampur", district="Sangareddy", state="Telangana",
        validation_status=ValidationStatus.APPROVED,
        source_document=SourceDocument(document_id="trusted-external-1", file_name="reference.pdf"),
        extensions={"trustedReference": True},
    )
    with factory() as session:
        session.add(LandRecordModel(
            id=str(reference.record_id), record_number=reference.record_number,
            owner_name=reference.owner_name, survey_number=reference.survey_number,
            area=reference.area, area_unit=reference.area_unit.value,
            district=reference.district, state=reference.state,
            validation_status="approved", source_document_id="trusted-external-1",
            payload=reference.model_dump(mode="json", by_alias=True),
        ))
        session.commit()

    uploaded = client.post("/api/v1/documents/upload", files={
        "file": ("high-score.pdf", _pdf_bytes(), "application/pdf"),
    }).json()
    assert client.post(f"/api/v1/documents/{uploaded['id']}/process").status_code == 202
    detail = client.get(f"/api/v1/documents/{uploaded['id']}").json()
    record_id = detail["extraction"]["recordId"]
    assert detail["validation"]["routing"] == "approved"
    assert detail["extraction"]["validationStatus"] == "human_review"
    case = client.get(f"/api/v1/reviews/{record_id}")
    assert case.status_code == 200, case.text
    assert case.json()["status"] == "queued"
    assert case.json()["validationStatus"] == "human_review"
    assert case.json()["validation"]["routing"] == "approved"
    assert client.post(f"/api/v1/reviews/{record_id}/decision", json={"decision": "approve"}).status_code == 409
    with factory() as session:
        stored = session.get(LandRecordModel, record_id)
        assert stored.validation_status == "human_review"
        assert stored.payload["validationStatus"] == "human_review"
        assert not session.scalars(select(AuditEventModel).where(
            AuditEventModel.record_id == record_id,
            AuditEventModel.event_type == "RECORD_APPROVED",
        )).all()


def test_cross_record_comparison_requires_officer_approval(live_client) -> None:
    client, _, factory = live_client

    def process(survey: str) -> dict:
        uploaded = client.post(
            "/api/v1/documents/upload",
            files={"file": ("record.pdf", _pdf_bytes(survey=survey), "application/pdf")},
        ).json()
        assert client.post(f"/api/v1/documents/{uploaded['id']}/process").status_code == 202
        return client.get(f"/api/v1/documents/{uploaded['id']}").json()

    first = process("142/3A")
    unapproved = process("142/3B")
    assert "survey_number_mismatch" not in {item["code"] for item in unapproved["validation"]["issues"]}
    with factory() as session:
        verified = session.scalar(select(LandRecordModel).where(LandRecordModel.source_document_id == first["id"]))
        assert verified is not None
        verified.validation_status = "approved"
        verified.payload = {**verified.payload, "validationStatus": "approved"}
        session.commit()
    without_decision = process("142/3B")
    assert "survey_number_mismatch" not in {item["code"] for item in without_decision["validation"]["issues"]}
    record_id = first["extraction"]["recordId"]
    with factory() as session:
        case = session.scalar(select(ReviewCaseModel).where(ReviewCaseModel.record_id == record_id))
        assert case is not None and case.decided_by is None
        case.status = "approved"
        session.commit()
    without_officer = process("142/3B")
    assert "survey_number_mismatch" not in {item["code"] for item in without_officer["validation"]["issues"]}
    with factory() as session:
        case = session.scalar(select(ReviewCaseModel).where(ReviewCaseModel.record_id == record_id))
        case.status = "queued"
        session.commit()
    base = f"/api/v1/reviews/{record_id}"
    assert client.post(f"{base}/accept-clear-fields").status_code == 200
    assert client.post(f"{base}/issues/reference_unavailable/resolve", json={
        "resolution": "confirmed", "reason": "Source reviewed; no comparison record was available.",
    }).status_code == 200
    approved = client.post(f"{base}/decision", json={"decision": "approve"})
    assert approved.status_code == 200, approved.text
    compared = process("142/3B")
    assert "survey_number_mismatch" in {item["code"] for item in compared["validation"]["issues"]}


def test_historical_synthetic_notice_cannot_become_an_operational_reference(live_client) -> None:
    client, _, factory = live_client
    sample = Path(__file__).resolve().parents[2] / "samples" / "sample_land_record_demo.pdf"
    uploaded = client.post(
        "/api/v1/documents/upload",
        files={"file": (sample.name, sample.read_bytes(), "application/pdf")},
    ).json()
    assert client.post(f"/api/v1/documents/{uploaded['id']}/process").status_code == 202
    with factory() as session:
        stored = session.get(DocumentModel, uploaded["id"])
        record = session.scalar(select(LandRecordModel).where(LandRecordModel.source_document_id == uploaded["id"]))
        case = session.scalar(select(ReviewCaseModel).where(ReviewCaseModel.document_id == uploaded["id"]))
        assert stored is not None and record is not None and case is not None
        # Reproduce older persisted metadata from before content-based labeling.
        stored.processing_metadata = {**stored.processing_metadata, "syntheticSourceDetected": False}
        record.validation_status = "approved"
        record.payload = {
            **record.payload,
            "validationStatus": "approved",
            "sourceDocument": {**record.payload["sourceDocument"], "isSynthetic": False},
        }
        case.status = "approved"
        session.commit()
    assert client.get(f"/api/v1/documents/{uploaded['id']}").status_code == 404
    assert client.get(f"/api/v1/documents/{uploaded['id']}",
                      params={"dataset": "sample"}).json()["isSynthetic"] is True

    source = fitz.open()
    page = source.new_page(width=600, height=800)
    page.insert_text(
        (70, 100),
        "Land Record\nOwner Name: Ravi Kumar\nSurvey No: 123/4B\n"
        "Record No: LR-DEMO-00017\nArea: 2.50 acres\nVillage: Example Village\n"
        "District: Demo District\nState: Telangana",
        fontsize=15,
    )
    candidate_pdf = source.tobytes()
    source.close()
    candidate = client.post("/api/v1/documents/upload",
                            files={"file": ("candidate.pdf", candidate_pdf, "application/pdf")}).json()
    assert client.post(f"/api/v1/documents/{candidate['id']}/process").status_code == 202
    detail = client.get(f"/api/v1/documents/{candidate['id']}").json()
    assert detail["status"] == "completed"
    assert "survey_number_mismatch" not in {issue["code"] for issue in detail["validation"]["issues"]}


def test_ocr_failure_is_visible_and_retryable(live_client) -> None:
    client, settings, _ = live_client
    settings.ocr_provider = "pdf_text"
    uploaded = client.post("/api/v1/documents/upload", files={"file": ("scan.png", _png_bytes(), "image/png")}).json()
    document_id = uploaded["id"]
    assert client.post(f"/api/v1/documents/{document_id}/process").status_code == 202
    failed = client.get(f"/api/v1/documents/{document_id}/processing-status").json()
    assert failed["status"] == "failed"
    assert failed["error"]["code"] == "ocr_unavailable"
    assert failed["stages"][2]["status"] == "failed"
    notifications = client.get("/api/v1/notifications").json()["items"]
    processing_alert = next(item for item in notifications if item["eventType"] == "PROCESSING_FAILED")
    assert processing_alert["href"] == f"#/documents?id={document_id}"
    settings.ocr_provider = "auto"
    assert client.post(f"/api/v1/documents/{document_id}/process").status_code == 202
    retried = client.get(f"/api/v1/documents/{document_id}/processing-status").json()
    assert retried["attempts"] == 2
    assert retried["status"] in {"completed", "failed"}
    assert retried["status"] != "processing"


def test_three_documents_keep_distinct_processing_review_and_audit_state(live_client) -> None:
    client, settings, factory = live_client
    uploads = [
        ("north.pdf", _pdf_bytes(survey="142/3A"), "application/pdf"),
        ("south.pdf", _pdf_bytes(survey="225/7B"), "application/pdf"),
        ("scan.png", _png_bytes(), "image/png"),
    ]
    documents = []
    for filename, content, mime_type in uploads:
        response = client.post("/api/v1/documents/upload", files={
            "file": (filename, content, mime_type),
        })
        assert response.status_code == 201, response.text
        documents.append(response.json())
    first, second, third = documents
    ids = {item["id"] for item in documents}
    assert len(ids) == 3
    listing = client.get("/api/v1/documents").json()
    assert listing["total"] == 3
    assert {item["id"] for item in listing["items"]} == ids
    assert {item["fileName"] for item in listing["items"]} == {name for name, _, _ in uploads}
    assert all(item["reviewStatus"] is None for item in listing["items"])

    for document in (first, second):
        response = client.post(f"/api/v1/documents/{document['id']}/process")
        assert response.status_code == 202, response.text
    first_detail = client.get(f"/api/v1/documents/{first['id']}").json()
    second_detail = client.get(f"/api/v1/documents/{second['id']}").json()
    assert first_detail["status"] == second_detail["status"] == "completed"
    assert first_detail["extraction"]["surveyNumber"] == "142/3A"
    assert second_detail["extraction"]["surveyNumber"] == "225/7B"
    assert first_detail["extraction"]["recordId"] != second_detail["extraction"]["recordId"]
    assert first_detail["reviewStatus"] == second_detail["reviewStatus"] == "queued"

    first_record_id = first_detail["extraction"]["recordId"]
    assert client.post(f"/api/v1/reviews/{first_record_id}/start").status_code == 200
    assert client.get(f"/api/v1/documents/{first['id']}").json()["reviewStatus"] == "in_progress"
    listing = client.get("/api/v1/documents").json()
    listed = {item["id"]: item for item in listing["items"]}
    assert listed[first["id"]]["reviewStatus"] == "in_progress"
    assert listed[second["id"]]["reviewStatus"] == "queued"
    assert listed[third["id"]]["reviewStatus"] is None

    # An OCR failure on the image has no effect on either completed PDF.
    settings.ocr_provider = "pdf_text"
    assert client.post(f"/api/v1/documents/{third['id']}/process").status_code == 202
    failed = client.get(f"/api/v1/documents/{third['id']}/processing-status").json()
    assert failed["status"] == "failed" and failed["error"]["code"] == "ocr_unavailable"
    assert client.get(f"/api/v1/documents/{first['id']}").json()["status"] == "completed"
    assert client.get(f"/api/v1/documents/{second['id']}").json()["status"] == "completed"
    assert client.post(f"/api/v1/documents/{third['id']}/process").status_code == 202
    assert client.get(f"/api/v1/documents/{third['id']}/processing-status").json()["attempts"] == 2
    with factory() as session:
        for document_id in ids:
            events = session.scalars(select(AuditEventModel).where(
                AuditEventModel.document_id == document_id,
            )).all()
            assert events and all(event.document_id == document_id for event in events)
            assert any(event.event_type == "DOCUMENT_UPLOADED" for event in events)
        assert session.get(DocumentModel, first["id"]).status == "completed"
        assert session.get(DocumentModel, second["id"]).status == "completed"
        assert session.get(DocumentModel, third["id"]).status == "failed"


def test_upload_and_processing_authorization_is_enforced_for_each_role(live_client) -> None:
    client, _, factory = live_client
    with factory() as session:
        create_user(session, email="admin@example.test", name="Test Administrator",
                    password="test-admin-password", role=Role.ADMIN)
        create_user(session, email="verifier@example.test", name="Test Verifier",
                    password="test-verifier-password", role=Role.VERIFIER)
        session.commit()

    def headers_for(email: str, password: str) -> dict[str, str]:
        response = client.post("/api/v1/auth/login", json={"email": email, "password": password})
        assert response.status_code == 200
        return {"Authorization": f"Bearer {response.json()['accessToken']}"}

    admin_headers = headers_for("admin@example.test", "test-admin-password")
    verifier_headers = headers_for("verifier@example.test", "test-verifier-password")
    auditor_headers = headers_for("auditor@example.test", "test-auditor-password")
    upload = lambda headers: client.post(  # noqa: E731 - identical multipart for every role
        "/api/v1/documents/upload", headers=headers,
        files={"file": ("role-check.pdf", _pdf_bytes(), "application/pdf")},
    )
    assert upload(verifier_headers).status_code == 403
    assert upload(auditor_headers).status_code == 403
    assert client.get("/api/v1/documents").json()["total"] == 0
    uploaded = upload(admin_headers)
    assert uploaded.status_code == 201
    document_id = uploaded.json()["id"]
    for headers in (verifier_headers, auditor_headers):
        assert client.get(f"/api/v1/documents/{document_id}", headers=headers).status_code == 200
        assert client.post(f"/api/v1/documents/{document_id}/process", headers=headers).status_code == 403
    assert client.post(f"/api/v1/documents/{document_id}/process", headers=admin_headers).status_code == 202
    assert client.get(f"/api/v1/documents/{document_id}/processing-status", headers=auditor_headers).status_code == 200
