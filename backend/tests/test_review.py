"""Officer review, persisted authorization, immutable extraction, and audit history."""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from uuid import UUID, uuid4

import pymupdf as fitz
from fastapi.testclient import TestClient
import pytest
from sqlalchemy import select
from sqlalchemy.orm import sessionmaker

from app.config import Settings, get_settings
from app.contracts.land_record import ValidationStatus
from app.contracts.processing import ValidationIssue, ValidationLevel, ValidationReport
from app.db.base import Base
from app.db.models import AuditEventModel, DocumentModel, LandRecordModel, ParcelIndexModel, ReviewCaseModel, UserModel
from app.db.session import build_engine, get_db
from app.main import app
from app.services.documents import pipeline
from tests.fixtures_intelligence import analyze_demo_case
from app.services.review import create_review_case
from app.services.review.service import requires_review
from app.services.auth.service import hash_password


@pytest.fixture
def review_client(tmp_path: Path):
    settings = Settings(
        _env_file=None,
        environment="development",
        database_url=f"sqlite:///{(tmp_path / 'review.db').as_posix()}",
        document_storage_dir=str(tmp_path / "uploads"),
    )
    engine = build_engine(settings.database_url)
    Base.metadata.create_all(bind=engine)
    factory = sessionmaker(bind=engine, autoflush=False, autocommit=False, expire_on_commit=False)
    with factory() as session:
        for user_id, name, role in (
            ("admin", "Test Admin", "ADMIN"),
            ("officer", "Test Officer", "REVENUE_OFFICER"),
            ("verifier", "Test Verifier", "VERIFIER"),
            ("auditor", "Test Auditor", "AUDITOR"),
        ):
            session.add(UserModel(
                id=user_id, email=f"{user_id}@example.test", name=name, role=role,
                password_hash=hash_password("TestingPassword123!"), is_active=True,
                status="ACTIVE", email_verified_at=datetime.now(timezone.utc),
                failed_login_count=0,
            ))
        session.commit()

    def override_db():
        with factory() as session:
            yield session

    app.dependency_overrides[get_db] = override_db
    app.dependency_overrides[get_settings] = lambda: settings
    with TestClient(app) as client:
        yield client, factory
    app.dependency_overrides.clear()
    engine.dispose()


def _auth(client: TestClient, user_id: str = "officer") -> dict[str, str]:
    response = client.post("/api/v1/auth/login", json={
        "email": f"{user_id}@example.test", "password": "TestingPassword123!",
    })
    assert response.status_code == 200, response.text
    return {"Authorization": f"Bearer {response.json()['accessToken']}"}


def _seed(factory, case_id: str = "survey-conflict") -> str:
    result = analyze_demo_case(case_id)
    record = result.record.model_copy(update={"record_id": uuid4()})
    record_id = str(record.record_id)
    document_id = str(uuid4())
    with factory() as session:
        document = DocumentModel(
            id=document_id, file_name=f"{case_id}.synthetic.pdf", mime_type="application/pdf",
            file_size=42, sha256="a" * 64, storage_key=str(uuid4()), page_count=1,
            status="completed", stage="final_routing", attempts=1, pages=[], stages=[],
            processing_metadata={}, ocr_pages=[], extraction=record.model_dump(mode="json", by_alias=True),
            fields=[field.model_dump(mode="json", by_alias=True) for field in result.fields],
            validation=result.validation.model_dump(mode="json", by_alias=True),
            score_breakdown=result.score_breakdown.model_dump(mode="json", by_alias=True),
            warnings=result.warnings,
        )
        session.add(document)
        session.add(LandRecordModel(
            id=record_id, record_number=record.record_number, owner_name=record.owner_name,
            survey_number=record.survey_number, area=record.area,
            area_unit=record.area_unit.value if record.area_unit else None,
            district=record.district, state=record.state,
            validation_status=result.validation.routing.value, source_document_id=document_id,
            document_id=document_id,
            payload=record.model_dump(mode="json", by_alias=True),
        ))
        create_review_case(session, document, record, result.validation, result.score_breakdown)
        session.commit()
    return record_id


def test_signed_session_and_server_role_control_mutations(review_client) -> None:
    client, factory = review_client
    record_id = _seed(factory)
    officer = _auth(client, "officer")
    auditor = _auth(client, "auditor")
    verifier = _auth(client, "verifier")
    assert client.get("/api/v1/auth/me", headers=officer).json()["role"] == "REVENUE_OFFICER"
    assert client.get("/api/v1/reviews").status_code == 401
    assert client.get("/api/v1/reviews", headers={"X-Role": "ADMIN"}).status_code == 401
    token = officer["Authorization"].split(" ", 1)[1]
    tampered = token[:-1] + ("A" if token[-1] != "A" else "B")
    assert client.get("/api/v1/reviews", headers={"Authorization": f"Bearer {tampered}"}).status_code == 401
    assert client.get(f"/api/v1/reviews/{record_id}", headers=auditor).status_code == 200
    assert client.post(f"/api/v1/reviews/{record_id}/fields/surveyNumber", headers=auditor,
                       json={"action": "accept"}).status_code == 403
    assert client.post(f"/api/v1/reviews/{record_id}/decision", headers=verifier,
                       json={"decision": "approve"}).status_code == 403
    recommended = client.post(f"/api/v1/reviews/{record_id}/recommendation", headers=verifier,
                              json={"recommendation": "approve", "reason": "Source inspected."})
    assert recommended.status_code == 200, recommended.text
    assert recommended.json()["recommendation"]["reviewerId"] == "verifier"


def test_review_queue_creation_filter_and_priority_explanations(review_client) -> None:
    client, factory = review_client
    record_id = _seed(factory)
    officer = _auth(client)
    queue = client.get("/api/v1/reviews", headers=officer)
    assert queue.status_code == 200, queue.text
    assert queue.json()["total"] == 1
    item = queue.json()["items"][0]
    assert item["recordId"] == record_id
    assert item["priority"] == "high"
    assert any("survey" in reason.lower() for reason in item["priorityReasons"])
    assert client.get("/api/v1/reviews", headers=officer, params={"filter": "conflicts"}).json()["total"] == 1
    assert client.get("/api/v1/reviews", headers=officer, params={"filter": "missing_fields"}).json()["total"] == 0
    assert client.get("/api/v1/reviews", headers=officer, params={"search": "no-match"}).json()["total"] == 0
    with factory() as session:
        case = session.scalar(select(ReviewCaseModel).where(ReviewCaseModel.record_id == record_id))
        assert case is not None and case.original_record["surveyNumber"] == "142/3A"
        assert any(event.event_type == "REVIEW_CREATED" for event in session.scalars(
            select(AuditEventModel).where(AuditEventModel.record_id == record_id)))


def test_rejected_low_confidence_result_still_requires_officer_review() -> None:
    report = ValidationReport(
        field_score=20, record_score=90, cross_system_score=50,
        quality_score=47, routing=ValidationStatus.REJECTED,
        issues=[ValidationIssue(
            level=ValidationLevel.FIELD, code="low_extraction_confidence",
            message="OCR signal is low.", field_name="area", severity="warning",
        )],
    )
    assert requires_review(report) is True


def test_approval_rechecks_current_reviewed_area_after_issue_resolution(review_client) -> None:
    client, factory = review_client
    record_id = _seed(factory)
    officer = _auth(client)
    base = f"/api/v1/reviews/{record_id}"
    assert client.post(f"{base}/accept-clear-fields", headers=officer).status_code == 200
    assert client.post(f"{base}/fields/surveyNumber", headers=officer, json={
        "action": "edit", "reviewedValue": "142/3B", "reason": "Compared with the stored reference.",
    }).status_code == 200
    assert client.post(f"{base}/issues/survey_number_mismatch/resolve", headers=officer, json={
        "fieldName": "surveyNumber", "resolution": "corrected", "reason": "Matches reference.",
    }).status_code == 200
    invalid = client.post(f"{base}/fields/area", headers=officer, json={
        "action": "edit", "reviewedValue": 0, "reason": "Testing an invalid area.",
    })
    assert invalid.status_code == 200, invalid.text
    assert invalid.json()["summary"]["canApprove"] is False
    assert any("area_out_of_range" in reason for reason in invalid.json()["summary"]["blockingReasons"])
    blocked = client.post(f"{base}/decision", headers=officer, json={"decision": "approve"})
    assert blocked.status_code == 409
    with factory() as session:
        stored = session.get(LandRecordModel, record_id)
        assert stored.validation_status != "approved"
        assert not any(event.event_type == "RECORD_APPROVED" for event in session.scalars(
            select(AuditEventModel).where(AuditEventModel.record_id == record_id)))


def test_correction_requires_issue_resolution_and_keeps_synthetic_gis_hidden(review_client) -> None:
    client, factory = review_client
    record_id = _seed(factory)
    officer = _auth(client)
    base = f"/api/v1/reviews/{record_id}"
    assert client.post(f"{base}/decision", headers=officer, json={"decision": "approve"}).status_code == 409
    bulk = client.post(f"{base}/accept-clear-fields", headers=officer)
    assert bulk.status_code == 200, bulk.text
    assert bulk.json()["summary"]["fieldsReviewed"] == bulk.json()["summary"]["fieldsTotal"] - 1
    edited = client.post(f"{base}/fields/surveyNumber", headers=officer, json={
        "action": "edit", "reviewedValue": "142/3B", "reason": "Matched the scanned reference entry.",
    })
    assert edited.status_code == 200, edited.text
    detail = edited.json()
    assert detail["originalRecord"]["surveyNumber"] == "142/3A"
    assert detail["reviewedRecord"]["surveyNumber"] == "142/3B"
    assert detail["summary"]["canApprove"] is False
    resolved = client.post(f"{base}/issues/survey_number_mismatch/resolve", headers=officer, json={
        "fieldName": "surveyNumber", "resolution": "corrected",
        "reason": "Corrected against the reference and source evidence.",
    })
    assert resolved.status_code == 200, resolved.text
    assert resolved.json()["summary"]["canApprove"] is True
    changed_again = client.post(f"{base}/fields/surveyNumber", headers=officer, json={
        "action": "edit", "reviewedValue": "142/3A", "reason": "Checking the source again.",
    })
    assert changed_again.status_code == 200
    assert changed_again.json()["summary"]["canApprove"] is False
    assert changed_again.json()["issueResolutions"] == []
    assert client.post(f"{base}/fields/surveyNumber", headers=officer, json={
        "action": "edit", "reviewedValue": "142/3B", "reason": "Final corrected value.",
    }).status_code == 200
    assert client.post(f"{base}/issues/survey_number_mismatch/resolve", headers=officer, json={
        "fieldName": "surveyNumber", "resolution": "corrected", "reason": "Confirmed correction after final inspection.",
    }).status_code == 200
    approved = client.post(f"{base}/decision", headers=officer, json={"decision": "approve"})
    assert approved.status_code == 200, approved.text
    assert approved.json()["status"] == "approved"
    assert approved.json()["gisIndexed"] is False
    assert approved.json()["gisParcelId"] is None
    parcel = client.get(f"/api/v1/gis/parcels/{record_id}", headers=officer)
    assert parcel.status_code == 404
    assert client.get("/api/v1/gis/parcels", headers=officer,
                      params={"recordStatus": "verified"}).json()["total"] == 0
    assert client.get(f"/api/v1/records/{record_id}", headers=officer).json()["record"]["surveyNumber"] == "142/3B"
    assert client.get("/api/v1/records", headers=officer).json()["total"] == 1
    audit = client.get("/api/v1/audit/events", headers=officer, params={"recordId": record_id})
    assert audit.status_code == 200 and audit.json()["total"] >= 5
    assert client.get(f"/api/v1/gis/parcels/{record_id}", headers=_auth(client, "verifier")).status_code == 403
    assert client.get(f"/api/v1/gis/parcels/{record_id}", headers=_auth(client, "auditor")).status_code == 404
    with factory() as session:
        case = session.scalar(select(ReviewCaseModel).where(ReviewCaseModel.record_id == record_id))
        document = session.get(DocumentModel, case.document_id)
        stored = session.get(LandRecordModel, record_id)
        retained_parcel = session.get(ParcelIndexModel, record_id)
        assert case.original_record["surveyNumber"] == "142/3A"
        assert document.extraction["surveyNumber"] == "142/3A"
        assert stored.payload["surveyNumber"] == "142/3B"
        assert retained_parcel is not None and retained_parcel.status == "verified"
        assert retained_parcel.polygon is None and retained_parcel.indexed_at is None
        events = session.scalars(select(AuditEventModel).where(AuditEventModel.record_id == record_id)).all()
        types = [event.event_type for event in events]
        assert "FIELD_EDITED" in types
        assert "FIELD_ACCEPTED" in types
        assert "ISSUE_RESOLVED" in types
        assert "RECORD_APPROVED" in types
        assert "GIS_INDEXED" not in types
        edit = next(event for event in events if event.event_type == "FIELD_EDITED")
        assert edit.event_metadata["previousValue"] == "142/3A"
        assert edit.event_metadata["newValue"] == "142/3B"


@pytest.mark.parametrize("decision,event_type,status", [
    ("reject", "RECORD_REJECTED", "rejected"),
    ("send_back", "RECORD_SENT_BACK", "sent_back"),
])
def test_rejection_and_send_back_require_reason_and_append_audit(review_client, decision, event_type, status) -> None:
    client, factory = review_client
    record_id = _seed(factory)
    officer = _auth(client)
    endpoint = f"/api/v1/reviews/{record_id}/decision"
    assert client.post(endpoint, headers=officer, json={"decision": decision}).status_code == 422
    response = client.post(endpoint, headers=officer, json={"decision": decision, "reason": "Insufficient source evidence."})
    assert response.status_code == 200, response.text
    assert response.json()["status"] == status
    assert response.json()["decisionReason"] == "Insufficient source evidence."
    with factory() as session:
        assert any(event.event_type == event_type for event in session.scalars(
            select(AuditEventModel).where(AuditEventModel.record_id == record_id)))
    assert client.get("/api/v1/reviews", headers=officer).json()["total"] == 0


def test_audit_events_cannot_be_modified_via_orm(review_client) -> None:
    _, factory = review_client
    _seed(factory)
    with factory() as session:
        event = session.scalar(select(AuditEventModel))
        event.description = "tampered"
        with pytest.raises(ValueError, match="append-only"):
            session.commit()


def test_ai_original_snapshot_cannot_be_replaced_via_orm(review_client) -> None:
    _, factory = review_client
    record_id = _seed(factory)
    with factory() as session:
        case = session.scalar(select(ReviewCaseModel).where(ReviewCaseModel.record_id == record_id))
        case.original_record = {**case.original_record, "surveyNumber": "tampered"}
        with pytest.raises(ValueError, match="cannot be changed"):
            session.commit()


def test_send_back_creates_a_new_immutable_review_attempt_on_reprocessing(review_client) -> None:
    client, factory = review_client
    record_id = _seed(factory)
    officer = _auth(client)
    sent = client.post(f"/api/v1/reviews/{record_id}/decision", headers=officer, json={
        "decision": "send_back", "reason": "Rescan the source before verification.",
    })
    assert sent.status_code == 200, sent.text
    old_case_id = None
    with factory() as session:
        previous = session.scalar(select(ReviewCaseModel).where(ReviewCaseModel.record_id == record_id))
        old_case_id = previous.id
        document = session.get(DocumentModel, previous.document_id)
        result = analyze_demo_case("survey-conflict")
        updated = result.record.model_copy(update={"record_id": UUID(previous.original_record["recordId"])})
        updated.survey_number = "142/3B"
        create_review_case(session, document, updated, result.validation, result.score_breakdown)
        session.commit()
    detail = client.get(f"/api/v1/reviews/{record_id}", headers=officer)
    assert detail.status_code == 200, detail.text
    assert detail.json()["originalRecord"]["surveyNumber"] == "142/3B"
    with factory() as session:
        attempts = session.scalars(select(ReviewCaseModel).where(ReviewCaseModel.record_id == record_id)).all()
        assert len(attempts) == 2
        old = next(attempt for attempt in attempts if attempt.id == old_case_id)
        assert old.original_record["surveyNumber"] == "142/3A"
        assert old.status == "sent_back"


def test_real_upload_processing_creates_a_review_item_and_audit_history(review_client, monkeypatch) -> None:
    client, factory = review_client
    monkeypatch.setattr(pipeline, "SessionLocal", factory)
    pdf = fitz.open()
    page = pdf.new_page(width=600, height=800)
    page.insert_text((50, 90), "Owner Name: Ramesh Kumar\nSurvey No: 142/3A\nArea: 2.47 acres\nVillage: Rampur\nDistrict: Sangareddy\nState: Telangana", fontsize=14)
    raw = pdf.tobytes()
    pdf.close()
    officer = _auth(client)
    upload = client.post("/api/v1/documents/upload", headers=officer,
                         files={"file": ("historical.pdf", raw, "application/pdf")})
    assert upload.status_code == 201, upload.text
    document_id = upload.json()["id"]
    started = client.post(f"/api/v1/documents/{document_id}/process", headers=officer)
    assert started.status_code == 202, started.text
    detail = client.get(f"/api/v1/documents/{document_id}", headers=officer).json()
    assert detail["status"] == "completed", detail.get("error")
    assert detail["extraction"]["sourceDocument"]["isSynthetic"] is False
    record_id = detail["extraction"]["recordId"]
    review = client.get(f"/api/v1/reviews/{record_id}", headers=officer)
    assert review.status_code == 200, review.text
    assert review.json()["documentId"] == document_id
    with factory() as session:
        types = [event.event_type for event in session.scalars(
            select(AuditEventModel).where(AuditEventModel.record_id == record_id))]
        assert "DOCUMENT_UPLOADED" in types
        assert "OCR_COMPLETED" in types
        assert "VALIDATION_COMPLETED" in types
        assert "REVIEW_CREATED" in types
