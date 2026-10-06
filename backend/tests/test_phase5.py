"""Real upload-to-GIS acceptance test with persisted evidence and audit."""

from __future__ import annotations

from datetime import datetime, timezone
from hashlib import sha256
import json
from pathlib import Path
from uuid import uuid4

import pymupdf as fitz
from fastapi.testclient import TestClient
import pytest
from sqlalchemy import select
from sqlalchemy.orm import sessionmaker

from app.config import Settings, get_settings
from app.contracts.auth import Role
from app.contracts.land_record import LandRecord, ValidationStatus
from app.db.base import Base
from app.db.models import AuditEventModel, DocumentModel, LandRecordModel, ParcelIndexModel, ReviewCaseModel, UserModel
from app.db.session import build_engine, get_db
from app.main import app
from app.services.auth.service import create_user
from app.services.documents import pipeline
from app.services.documents.storage import document_dir


@pytest.fixture
def product_client(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    settings = Settings(
        _env_file=None, environment="development",
        database_url=f"sqlite:///{(tmp_path / 'product.db').as_posix()}",
        document_storage_dir=str(tmp_path / "uploads"),
    )
    engine = build_engine(settings.database_url)
    Base.metadata.create_all(bind=engine)
    factory = sessionmaker(bind=engine, autoflush=False, autocommit=False, expire_on_commit=False)
    with factory() as session:
        create_user(session, email="officer@example.test", name="Test Officer",
                    password="test-officer-password", role=Role.REVENUE_OFFICER)
        create_user(session, email="auditor@example.test", name="Test Auditor",
                    password="test-auditor-password", role=Role.AUDITOR)
        session.commit()

    def override_db():
        with factory() as session:
            yield session

    app.dependency_overrides[get_db] = override_db
    app.dependency_overrides[get_settings] = lambda: settings
    monkeypatch.setattr(pipeline, "SessionLocal", factory)
    with TestClient(app) as client:
        yield client, factory, settings
    app.dependency_overrides.clear()
    engine.dispose()


def _auth(client: TestClient, role: str = "officer") -> dict[str, str]:
    response = client.post("/api/v1/auth/login", json={
        "email": f"{role}@example.test", "password": f"test-{role}-password",
    })
    assert response.status_code == 200, response.text
    return {"Authorization": f"Bearer {response.json()['accessToken']}"}


def _source_pdf(
    *, owner: str = "Ravi Kumar", survey: str = "123/4A",
    record_number: str = "LR-2026-017", synthetic_notice: bool = False,
) -> bytes:
    document = fitz.open()
    page = document.new_page(width=600, height=800)
    notice = "\nSynthetic test record. Not an official land record." if synthetic_notice else ""
    page.insert_text(
        (70, 100),
        f"Land Record\nOwner Name: {owner}\nSurvey No: {survey}\n"
        f"Record No: {record_number}\nArea: 2.50 acre\nVillage: Kothur\n"
        f"Mandal: Sangareddy\nDistrict: Sangareddy{notice}",
        fontsize=15,
    )
    result = document.tobytes()
    document.close()
    return result


def _geometry_file(ring: list[list[float]]) -> bytes:
    return json.dumps({"type": "Polygon", "coordinates": [ring]}).encode("utf-8")


_BOUNDARY = [
    [78.5071, 17.6241], [78.5082, 17.6241],
    [78.5082, 17.6250], [78.5071, 17.6250], [78.5071, 17.6241],
]


def _seed_record(factory, *, approved: bool) -> str:
    """Provide the API an existing reviewed record without bypassing its guards."""
    record = LandRecord(
        owner_name="Ravi Kumar", survey_number="123/4A", record_number="LR-2026-017",
        area=2.5, village="Kothur", district="Sangareddy", state="Telangana",
        validation_status=ValidationStatus.APPROVED if approved else ValidationStatus.HUMAN_REVIEW,
    )
    record_id, document_id = str(record.record_id), str(uuid4())
    payload = record.model_dump(mode="json", by_alias=True)
    with factory() as session:
        officer = session.scalar(select(UserModel).where(UserModel.email == "officer@example.test"))
        assert officer is not None
        document = DocumentModel(
            id=document_id, file_name="record.pdf", mime_type="application/pdf",
            file_size=10, sha256="a" * 64, storage_key=str(uuid4()), page_count=1,
            status="completed", stage="final_routing", attempts=1,
            pages=[], stages=[], processing_metadata={}, ocr_pages=[], fields=[], warnings=[],
        )
        stored = LandRecordModel(
            id=record_id, document=document, source_document_id=document_id,
            record_number=record.record_number, owner_name=record.owner_name,
            survey_number=record.survey_number, area=record.area,
            district=record.district, state=record.state,
            validation_status=record.validation_status.value, payload=payload,
        )
        review = ReviewCaseModel(
            id=str(uuid4()), record=stored, document=document,
            status="approved" if approved else "queued", priority="medium", priority_reasons=[],
            original_record=payload, reviewed_record=payload,
            field_reviews={}, issue_resolutions=[], validation={}, quality_score=75,
            decided_by=officer.id if approved else None,
            decided_at=datetime.now(timezone.utc) if approved else None,
            version=1,
        )
        parcel = ParcelIndexModel(
            record=stored, document=document, status="verified" if approved else "review",
            validation_status=record.validation_status.value,
            quality_score=75, polygon=None, geometry_source="unavailable",
        )
        session.add_all([document, stored, review, parcel])
        session.commit()
    return record_id


def test_actual_pdf_processing_review_approval_and_gis(product_client) -> None:
    client, factory, settings = product_client
    officer, auditor = _auth(client), _auth(client, "auditor")
    source_pdf = _source_pdf()

    assert client.post("/api/v1/auth/demo/session", json={"userId": "admin"}).status_code == 404
    assert client.get("/api/v1/demo/phase5/scenarios", headers=officer).status_code == 404
    assert client.get("/api/v1/documents").status_code == 401

    response = client.post("/api/v1/documents/upload", headers=officer,
                           files={"file": ("record.pdf", source_pdf, "application/pdf")})
    assert response.status_code == 201, response.text
    uploaded = response.json()
    document_id = uploaded["id"]
    assert uploaded["status"] == "uploaded"
    assert client.get(uploaded["pages"][0]["imageUrl"], headers=officer).content.startswith(b"\x89PNG")
    with factory() as session:
        stored = session.get(DocumentModel, document_id)
        assert stored and stored.sha256 == sha256(source_pdf).hexdigest()
        assert (document_dir(settings, stored.storage_key) / "original.bin").read_bytes() == source_pdf

    assert client.post(f"/api/v1/documents/{document_id}/process", headers=officer).status_code == 202
    detail_response = client.get(f"/api/v1/documents/{document_id}", headers=officer)
    assert detail_response.status_code == 200, detail_response.text
    detail = detail_response.json()
    assert detail["status"] == "completed", detail.get("error")
    assert detail["provider"] == "pdf-embedded-text"
    assert all(stage["status"] == "completed" for stage in detail["stages"])
    assert "123/4A" in detail["ocrPages"][0]["text"]
    extracted = detail["extraction"]
    assert detail["isSynthetic"] is False
    assert extracted["sourceDocument"]["isSynthetic"] is False
    assert extracted["ownerName"] == "Ravi Kumar"
    assert extracted["surveyNumber"] == "123/4A"
    assert extracted["area"] == 2.5 and extracted["areaUnit"] == "acre"
    assert extracted["state"] is None  # Missing in the actual PDF.
    assert extracted["extractionConfidence"]["overall"] is None
    survey = next(field for field in detail["fields"] if field["field"] == "surveyNumber")
    assert survey["value"] == "123/4A" and survey["source"]["page"] == 1
    assert survey["source"]["bbox"] and survey["extractionMethod"] == "labeled-region-rule"
    score = detail["scoreBreakdown"]
    assert score["qualityScore"] == detail["validation"]["qualityScore"] > 27
    assert (score["fieldWeight"], score["recordWeight"], score["crossSystemWeight"]) == (0.5, 0.3, 0.2)
    assert any(item["code"] == "required_field_missing" and item["fieldName"] == "state"
               for item in detail["validation"]["issues"])

    record_id = extracted["recordId"]
    queue = client.get("/api/v1/reviews", headers=officer).json()
    assert queue["total"] == 1 and queue["items"][0]["recordId"] == record_id
    case = client.get(f"/api/v1/reviews/{record_id}", headers=officer).json()
    assert case["originalRecord"]["state"] is None and case["summary"]["canApprove"] is False
    assert client.post(f"/api/v1/reviews/{record_id}/decision", headers=officer,
                       json={"decision": "approve"}).status_code == 409
    assert client.post(f"/api/v1/reviews/{record_id}/fields/state", headers=auditor,
                       json={"action": "edit", "reviewedValue": "Telangana",
                             "reason": "Verified against source register."}).status_code == 403
    edited = client.post(f"/api/v1/reviews/{record_id}/fields/state", headers=officer,
                         json={"action": "edit", "reviewedValue": "Telangana",
                               "reason": "Verified against source register."})
    assert edited.status_code == 200, edited.text
    assert edited.json()["originalRecord"]["state"] is None
    assert edited.json()["reviewedRecord"]["state"] == "Telangana"
    accepted = client.post(f"/api/v1/reviews/{record_id}/accept-clear-fields", headers=officer)
    assert accepted.status_code == 200, accepted.text
    for issue in detail["validation"]["issues"]:
        correction = issue["code"] == "required_field_missing" and issue.get("fieldName") == "state"
        resolved = client.post(
            f"/api/v1/reviews/{record_id}/issues/{issue['code']}/resolve", headers=officer,
            json={"fieldName": issue.get("fieldName"),
                  "resolution": "corrected" if correction else "confirmed",
                  "reason": "State supplied from source register." if correction
                            else "Officer inspected source and accepted this limitation."},
        )
        assert resolved.status_code == 200, (issue, resolved.text)
    ready = client.get(f"/api/v1/reviews/{record_id}", headers=officer).json()
    assert ready["summary"]["canApprove"] is True, ready["summary"]
    approved = client.post(f"/api/v1/reviews/{record_id}/decision", headers=officer,
                           json={"decision": "approve", "reason": "Verified with source register."})
    assert approved.status_code == 200, approved.text
    assert approved.json()["status"] == "approved" and approved.json()["gisIndexed"] is False

    record = client.get(f"/api/v1/records/{record_id}", headers=officer).json()
    assert record["record"]["state"] == "Telangana"
    assert record["record"]["surveyNumber"] == "123/4A"
    assert record["review"]["originalRecord"]["state"] is None
    parcel_response = client.get(f"/api/v1/gis/parcels/{record_id}", headers=auditor)
    assert parcel_response.status_code == 200, parcel_response.text
    parcel = parcel_response.json()["parcel"]
    assert parcel["status"] == "verified" and parcel["state"] == "Telangana"
    assert parcel["geometrySource"] == "unavailable"
    assert parcel["geometryStatus"] == "unavailable"
    assert parcel["polygon"] is None and parcel["indexedAt"] is None
    assert "GIS_INDEXED" not in {
        event["eventType"] for event in client.get(
            "/api/v1/audit/events", headers=officer, params={"recordId": record_id}
        ).json()["items"]
    }

    geometry = _geometry_file(_BOUNDARY)
    imported = client.post(
        f"/api/v1/gis/parcels/{record_id}/geometry", headers=officer,
        files={"file": ("boundary.geojson", geometry, "application/geo+json")},
        data={"sourceReference": "Survey office boundary file SR-2026-017"},
    )
    assert imported.status_code == 200, imported.text
    assert imported.json()["synthetic"] is False
    sourced = imported.json()["parcel"]
    assert sourced["polygon"] == _BOUNDARY
    assert sourced["geometrySource"] == "officer_geojson"
    assert sourced["geometryStatus"] == "sourced"
    assert sourced["geometryReference"] == "Survey office boundary file SR-2026-017"
    assert sourced["geometryFileName"] == "boundary.geojson"
    assert sourced["geometrySha256"] == sha256(geometry).hexdigest()
    assert sourced["geometryRecordedAt"] is not None
    assert sourced["geometryRecordedBy"] is not None
    assert sourced["indexedAt"] is not None
    assert client.get(f"/api/v1/gis/parcels/{record_id}", headers=auditor).json()["parcel"]["polygon"] == _BOUNDARY
    assert client.get(f"/api/v1/reviews/{record_id}", headers=officer).json()["gisIndexed"] is True
    search = client.get("/api/v1/search", headers=officer, params={"q": "123/4A"}).json()
    assert any(item["id"] == record_id for item in search["records"])
    metrics = client.get("/api/v1/analytics/summary", headers=officer).json()["metrics"]
    assert metrics["documentsTotal"] == metrics["documentsProcessed"] == metrics["recordsTotal"] == 1
    assert metrics["approvedRecords"] == 1
    assert metrics["averageQualityScore"] == score["qualityScore"]

    with factory() as session:
        stored = session.get(DocumentModel, document_id)
        verified = session.get(LandRecordModel, record_id)
        review = session.scalar(select(ReviewCaseModel).where(ReviewCaseModel.record_id == record_id))
        indexed = session.get(ParcelIndexModel, record_id)
        events = session.scalars(select(AuditEventModel)).all()
        assert stored and stored.ocr_pages and stored.fields and stored.validation and stored.score_breakdown
        assert verified and verified.payload["state"] == "Telangana" and verified.validation_status == "approved"
        assert review and review.original_record["state"] is None and review.reviewed_record["state"] == "Telangana"
        assert indexed and indexed.status == "verified" and indexed.document_id == document_id
        assert indexed.polygon == _BOUNDARY
        assert indexed.geometry_storage_key is not None
        assert (document_dir(settings, stored.storage_key) / "geometry" /
                f"{indexed.geometry_storage_key}.geojson").read_bytes() == geometry
        officer_user = session.scalar(select(UserModel).where(UserModel.email == "officer@example.test"))
        assert officer_user is not None
        assert indexed.geometry_recorded_by == officer_user.id
        edit = next(event for event in events if event.event_type == "FIELD_EDITED")
        assert edit.actor_id and edit.event_metadata["originalValue"] is None
        assert edit.event_metadata["newValue"] == "Telangana"
        assert {"DOCUMENT_UPLOADED", "PROCESSING_STARTED", "OCR_COMPLETED", "EXTRACTION_COMPLETED",
                "VALIDATION_COMPLETED", "FIELD_EDITED", "RECORD_APPROVED", "GEOMETRY_IMPORTED", "GIS_INDEXED"} <= {
            event.event_type for event in events
        }
        assert next(event for event in events if event.event_type == "GEOMETRY_IMPORTED").actor_id == officer_user.id


def test_geometry_import_requires_approved_record_and_officer_role(product_client) -> None:
    client, factory, _ = product_client
    officer, auditor = _auth(client), _auth(client, "auditor")
    geometry = _geometry_file(_BOUNDARY)
    options = {
        "files": {"file": ("boundary.geojson", geometry, "application/geo+json")},
        "data": {"sourceReference": "Survey office boundary file SR-2026-017"},
    }
    unapproved_id = _seed_record(factory, approved=False)
    assert client.post(f"/api/v1/gis/parcels/{unapproved_id}/geometry", headers=officer, **options).status_code == 409

    approved_id = _seed_record(factory, approved=True)
    endpoint = f"/api/v1/gis/parcels/{approved_id}/geometry"
    assert client.post(endpoint, **options).status_code == 401
    assert client.post(endpoint, headers=auditor, **options).status_code == 403
    with factory() as session:
        parcel = session.get(ParcelIndexModel, approved_id)
        assert parcel is not None and parcel.polygon is None
        assert not list(session.scalars(select(AuditEventModel).where(AuditEventModel.record_id == approved_id)))


@pytest.mark.parametrize("geojson", [
    b"{not json}",
    _geometry_file(_BOUNDARY[:-1]),  # An exterior ring must close exactly.
    _geometry_file([[181.0, 17.6241], *_BOUNDARY[1:]]),  # Longitude outside WGS84.
    json.dumps({"type": "FeatureCollection", "features": []}).encode("utf-8"),
    json.dumps({"type": "Polygon", "coordinates": [_BOUNDARY, _BOUNDARY]}).encode("utf-8"),
])
def test_geometry_import_rejects_invalid_geojson_without_indexing(product_client, geojson: bytes) -> None:
    client, factory, _ = product_client
    record_id = _seed_record(factory, approved=True)
    response = client.post(
        f"/api/v1/gis/parcels/{record_id}/geometry", headers=_auth(client),
        files={"file": ("boundary.geojson", geojson, "application/geo+json")},
        data={"sourceReference": "Survey office boundary file SR-2026-017"},
    )
    assert response.status_code == 422, response.text
    with factory() as session:
        parcel = session.get(ParcelIndexModel, record_id)
        assert parcel is not None and parcel.polygon is None and parcel.indexed_at is None
        assert not list(session.scalars(select(AuditEventModel).where(AuditEventModel.record_id == record_id)))


def test_replacing_sourced_geometry_preserves_audit_history(product_client) -> None:
    client, factory, _ = product_client
    record_id = _seed_record(factory, approved=True)
    officer = _auth(client)
    endpoint = f"/api/v1/gis/parcels/{record_id}/geometry"
    first = client.post(endpoint, headers=officer,
                        files={"file": ("first.geojson", _geometry_file(_BOUNDARY), "application/geo+json")},
                        data={"sourceReference": "Survey office boundary file SR-2026-017"})
    assert first.status_code == 200, first.text
    replacement = [
        [78.5091, 17.6261], [78.5102, 17.6261],
        [78.5102, 17.6270], [78.5091, 17.6270], [78.5091, 17.6261],
    ]
    second = client.post(endpoint, headers=officer,
                         files={"file": ("corrected.geojson", _geometry_file(replacement), "application/geo+json")},
                         data={"sourceReference": "Survey office corrected boundary SR-2026-017A"})
    assert second.status_code == 200, second.text
    assert second.json()["parcel"]["polygon"] == replacement
    assert second.json()["parcel"]["geometryReference"] == "Survey office corrected boundary SR-2026-017A"
    with factory() as session:
        types = [event.event_type for event in session.scalars(
            select(AuditEventModel).where(AuditEventModel.record_id == record_id)
        )]
        assert types.count("GEOMETRY_IMPORTED") == 1
        assert types.count("GEOMETRY_REPLACED") == 1
        assert types.count("GIS_INDEXED") == 1


def test_operational_gis_hides_legacy_and_uploaded_synthetic_parcels_without_erasing_history(product_client) -> None:
    client, factory, _ = product_client
    officer, auditor = _auth(client), _auth(client, "auditor")
    operational_id = _seed_record(factory, approved=True)

    legacy_id, legacy_event_id = str(uuid4()), str(uuid4())
    with factory() as session:
        legacy_record = LandRecordModel(
            id=legacy_id, source_document_id="legacy-demo-reference", document_id=None,
            survey_number="DEMO-001", validation_status="approved",
            payload={"recordId": legacy_id, "surveyNumber": "DEMO-001"},
        )
        legacy_parcel = ParcelIndexModel(
            record=legacy_record, document_id=None, status="verified",
            validation_status="approved", polygon=_BOUNDARY,
            geometry_source="synthetic_demo", survey_number="DEMO-001",
        )
        legacy_event = AuditEventModel(
            id=legacy_event_id, record_id=legacy_id, document_id=None,
            actor_id="legacy-gis", actor_role="SYSTEM", event_type="GIS_INDEXED",
            description="Historical synthetic parcel was indexed.", event_metadata={"geometrySource": "synthetic_demo"},
        )
        session.add_all([legacy_record, legacy_parcel, legacy_event])
        session.commit()

    sample = Path(__file__).resolve().parents[2] / "samples" / "sample_land_record_demo.pdf"
    uploaded = client.post(
        "/api/v1/documents/upload", headers=officer,
        files={"file": (sample.name, sample.read_bytes(), "application/pdf")},
    )
    assert uploaded.status_code == 201, uploaded.text
    document_id = uploaded.json()["id"]
    assert client.post(f"/api/v1/documents/{document_id}/process", headers=officer).status_code == 202
    assert client.get(f"/api/v1/documents/{document_id}", headers=officer).status_code == 404
    detail = client.get(f"/api/v1/documents/{document_id}", headers=officer,
                        params={"dataset": "sample"}).json()
    assert detail["status"] == "completed", detail.get("error")
    assert detail["isSynthetic"] is True
    synthetic_id = detail["extraction"]["recordId"]

    listed = client.get("/api/v1/gis/parcels", headers=auditor)
    assert listed.status_code == 200, listed.text
    assert listed.json()["total"] == 1
    assert [parcel["recordId"] for parcel in listed.json()["items"]] == [operational_id]
    assert client.get(f"/api/v1/gis/parcels/{operational_id}", headers=auditor).status_code == 200
    assert client.get(f"/api/v1/gis/parcels/{legacy_id}", headers=auditor).status_code == 404
    assert client.get(f"/api/v1/gis/parcels/{synthetic_id}", headers=auditor).status_code == 404

    with factory() as session:
        assert session.get(ParcelIndexModel, legacy_id) is not None
        assert session.get(ParcelIndexModel, synthetic_id) is not None
        assert session.get(DocumentModel, document_id) is not None
        assert session.get(AuditEventModel, legacy_event_id) is not None
        assert session.scalar(select(AuditEventModel).where(
            AuditEventModel.record_id == synthetic_id,
            AuditEventModel.event_type == "DOCUMENT_UPLOADED",
        )) is not None


def test_operational_and_sample_datasets_have_separate_read_paths_and_counts(product_client) -> None:
    client, factory, _ = product_client
    officer = _auth(client)

    def ingest(name: str, pdf: bytes, *, declared_sample: bool = False) -> tuple[str, str, dict]:
        upload = client.post(
            "/api/v1/documents/upload", headers=officer,
            files={"file": (name, pdf, "application/pdf")},
            data={"dataset": "sample"} if declared_sample else None,
        )
        assert upload.status_code == 201, upload.text
        document_id = upload.json()["id"]
        started = client.post(
            f"/api/v1/documents/{document_id}/process", headers=officer,
            params={"dataset": "sample"} if declared_sample else None,
        )
        assert started.status_code == 202, started.text
        detail = client.get(
            f"/api/v1/documents/{document_id}", headers=officer,
            params={"dataset": "sample"} if declared_sample or "notice" in name else None,
        )
        assert detail.status_code == 200, detail.text
        body = detail.json()
        assert body["status"] == "completed", body.get("error")
        return document_id, body["extraction"]["recordId"], body

    operational_id, operational_record, operational = ingest(
        "operational.pdf", _source_pdf(),
    )
    declared_id, declared_record, declared = ingest(
        "declared-sample.pdf",
        _source_pdf(owner="Anita Rao", survey="987/6B", record_number="LR-2026-987"),
        declared_sample=True,
    )
    noticed_id, noticed_record, noticed = ingest(
        "notice-sample.pdf",
        _source_pdf(owner="Meera Rao", survey="654/2C", record_number="LR-2026-654", synthetic_notice=True),
    )
    sample_ids = {declared_id, noticed_id}
    sample_record_ids = {declared_record, noticed_record}
    assert operational["datasetScope"] == "operational" and operational["datasetReason"] is None
    assert declared["datasetScope"] == "sample" and declared["datasetReason"] == "declared_sample"
    assert noticed["datasetScope"] == "sample" and noticed["datasetReason"] is not None

    operational_documents = client.get("/api/v1/documents", headers=officer).json()
    sample_documents = client.get("/api/v1/documents", headers=officer, params={"dataset": "sample"}).json()
    assert operational_documents["total"] == 1
    assert {item["id"] for item in operational_documents["items"]} == {operational_id}
    assert sample_documents["total"] == 2
    assert {item["id"] for item in sample_documents["items"]} == sample_ids
    for document_id, body in ((declared_id, declared), (noticed_id, noticed)):
        assert client.get(f"/api/v1/documents/{document_id}", headers=officer).status_code == 404
        assert client.get(f"/api/v1/documents/{document_id}", headers=officer,
                          params={"dataset": "sample"}).status_code == 200
        sample_page_url = body["pages"][0]["imageUrl"]
        assert "dataset=sample" in sample_page_url
        assert client.get(sample_page_url, headers=officer).content.startswith(b"\x89PNG")
        assert client.get(sample_page_url.split("?", 1)[0], headers=officer).status_code == 404
        assert client.get(f"/api/v1/documents/{document_id}/processing-status", headers=officer).status_code == 404
        assert client.get(f"/api/v1/documents/{document_id}/processing-status", headers=officer,
                          params={"dataset": "sample"}).status_code == 200

    operational_records = client.get("/api/v1/records", headers=officer).json()
    sample_records = client.get("/api/v1/records", headers=officer, params={"dataset": "sample"}).json()
    assert operational_records["total"] == 1
    assert {item["recordId"] for item in operational_records["items"]} == {operational_record}
    assert sample_records["total"] == 2
    assert {item["recordId"] for item in sample_records["items"]} == sample_record_ids
    operational_reviews = client.get("/api/v1/reviews", headers=officer).json()
    sample_reviews = client.get("/api/v1/reviews", headers=officer, params={"dataset": "sample"}).json()
    assert operational_reviews["total"] == 1
    assert {item["recordId"] for item in operational_reviews["items"]} == {operational_record}
    assert sample_reviews["total"] == 2
    assert {item["recordId"] for item in sample_reviews["items"]} == sample_record_ids
    for record_id in sample_record_ids:
        assert client.get(f"/api/v1/records/{record_id}", headers=officer).status_code == 404
        assert client.get(f"/api/v1/records/{record_id}", headers=officer,
                          params={"dataset": "sample"}).status_code == 200
        assert client.get(f"/api/v1/reviews/{record_id}", headers=officer).status_code == 404
        assert client.get(f"/api/v1/reviews/{record_id}", headers=officer,
                          params={"dataset": "sample"}).status_code == 200
        assert client.post(f"/api/v1/reviews/{record_id}/start", headers=officer).status_code == 404
        assert client.post(f"/api/v1/reviews/{record_id}/start", headers=officer,
                           params={"dataset": "sample"}).status_code == 404
        assert client.get("/api/v1/audit/events", headers=officer,
                          params={"recordId": record_id}).json()["total"] == 0
        assert client.get("/api/v1/audit/events", headers=officer,
                          params={"recordId": record_id, "dataset": "sample"}).json()["total"] > 0

    summary = client.get("/api/v1/analytics/summary", headers=officer).json()["metrics"]
    assert summary["documentsTotal"] == summary["documentsProcessed"] == summary["recordsTotal"] == 1
    assert summary["awaitingReview"] == 1
    assert client.get("/api/v1/search", headers=officer, params={"q": "987/6B"}).json()["total"] == 0
    assert client.get("/api/v1/search", headers=officer, params={"q": "123/4A"}).json()["total"] > 0
    assert all(item["documentId"] not in sample_ids for item in
               client.get("/api/v1/audit/events", headers=officer).json()["items"])
    assert all(item["documentId"] not in sample_ids for item in
               client.get("/api/v1/notifications", headers=officer).json()["items"])
    assert client.get("/api/v1/documents", headers=officer,
                      params={"dataset": "unknown"}).status_code == 422

    with factory() as session:
        assert {session.get(DocumentModel, document_id).dataset_scope for document_id in sample_ids} == {"sample"}
        assert all(session.get(LandRecordModel, record_id) is not None for record_id in sample_record_ids)
        assert all(session.scalar(select(ReviewCaseModel).where(ReviewCaseModel.record_id == record_id)) is not None
                   for record_id in sample_record_ids)
        assert all(session.scalar(select(AuditEventModel).where(AuditEventModel.record_id == record_id)) is not None
                   for record_id in sample_record_ids)

        # Older audit rows can lack document_id. Their linked record still
        # determines which dataset may see them; orphan rows fail closed.
        operational_event_id, sample_event_id, orphan_event_id = (str(uuid4()) for _ in range(3))
        for event_id, record_id in (
            (operational_event_id, operational_record),
            (sample_event_id, declared_record),
            (orphan_event_id, str(uuid4())),
        ):
            session.add(AuditEventModel(
                id=event_id, record_id=record_id, document_id=None,
                actor_id="validation-engine", actor_role="SYSTEM",
                event_type="CONFLICT_DETECTED", timestamp=datetime.now(timezone.utc),
                description="Validation conflict retained without document link.", event_metadata={},
            ))
        session.commit()

    operational_audit_ids = {item["id"] for item in client.get(
        "/api/v1/audit/events", headers=officer,
    ).json()["items"]}
    sample_audit_ids = {item["id"] for item in client.get(
        "/api/v1/audit/events", headers=officer, params={"dataset": "sample"},
    ).json()["items"]}
    notification_ids = {item["id"] for item in client.get(
        "/api/v1/notifications", headers=officer,
    ).json()["items"]}
    assert operational_event_id in operational_audit_ids and operational_event_id in notification_ids
    assert sample_event_id not in operational_audit_ids and sample_event_id not in notification_ids
    assert sample_event_id in sample_audit_ids
    assert orphan_event_id not in operational_audit_ids | sample_audit_ids | notification_ids
    assert client.post(f"/api/v1/notifications/{sample_event_id}/read", headers=officer).status_code == 404


def test_cors_configuration_rejects_credentialed_wildcard() -> None:
    with pytest.raises(ValueError, match="CORS origins must be explicit"):
        Settings(_env_file=None, cors_origins=["*"])
