"""Existing quality routes must not become officer decisions on upgrade."""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4

from alembic import command
from alembic.config import Config
import pytest
import sqlalchemy as sa

from app.config import get_settings
from app.db.session import build_engine


def test_backfill_queues_completed_record_without_changing_source_evidence(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    backend = Path(__file__).resolve().parents[1]
    url = f"sqlite:///{(tmp_path / 'officer-review.db').as_posix()}"
    monkeypatch.setenv("BHUDRISHTI_DATABASE_URL", url)
    get_settings.cache_clear()
    config = Config(str(backend / "alembic.ini"))
    config.set_main_option("script_location", str(backend / "migrations"))
    command.upgrade(config, "0008_accounts")
    engine = build_engine(url)
    metadata = sa.MetaData()
    documents = sa.Table("documents", metadata, autoload_with=engine)
    records = sa.Table("land_records", metadata, autoload_with=engine)
    parcels = sa.Table("parcel_index", metadata, autoload_with=engine)
    audit = sa.Table("audit_events", metadata, autoload_with=engine)
    record_id, document_id = str(uuid4()), str(uuid4())
    synthetic_record_id, synthetic_document_id = str(uuid4()), str(uuid4())
    now = datetime.now(timezone.utc)

    def document_values(doc_id: str, rec_id: str, *, synthetic: bool) -> dict:
        extraction = {
            "recordId": rec_id, "ownerName": "Source owner",
            "validationStatus": "approved",
            "sourceDocument": {"documentId": doc_id, "fileName": "record.pdf"},
        }
        return {
            "id": doc_id, "file_name": "record.pdf", "mime_type": "application/pdf",
            "file_size": 100, "sha256": "a" * 64, "storage_key": str(uuid4()),
            "page_count": 1, "status": "completed", "stage": "final_routing",
            "attempts": 1, "pages": [], "stages": [],
            "processing_metadata": {"syntheticSourceDetected": synthetic},
            "ocr_pages": [], "extraction": extraction, "fields": [],
            "validation": {"routing": "approved", "qualityScore": 96.0, "issues": []},
            "score_breakdown": {"qualityScore": 96.0}, "warnings": [],
            "uploaded_at": now, "processed_at": now,
        }

    with engine.begin() as connection:
        connection.execute(documents.insert(), [
            document_values(document_id, record_id, synthetic=False),
            document_values(synthetic_document_id, synthetic_record_id, synthetic=True),
        ])
        connection.execute(records.insert(), [
            {
                "id": rec_id, "validation_status": "approved",
                "source_document_id": doc_id, "document_id": doc_id,
                "payload": {
                    "recordId": rec_id, "validationStatus": "approved",
                    "sourceDocument": {"documentId": doc_id, "fileName": "record.pdf"},
                },
            }
            for rec_id, doc_id in (
                (record_id, document_id), (synthetic_record_id, synthetic_document_id),
            )
        ])
        connection.execute(parcels.insert().values(
            record_id=record_id, document_id=document_id,
            status="review", validation_status="approved",
            polygon=[[0.0, 0.0]], geometry_source="local_prototype",
        ))
        connection.execute(audit.insert().values(
            id=str(uuid4()), record_id=record_id, document_id=document_id,
            actor_id="system", actor_role="SYSTEM", event_type="VALIDATION_COMPLETED",
            timestamp=now, description="Existing validation event.", event_metadata={},
        ))
    engine.dispose()

    command.upgrade(config, "head")
    command.check(config)
    engine = build_engine(url)
    metadata = sa.MetaData()
    documents = sa.Table("documents", metadata, autoload_with=engine)
    records = sa.Table("land_records", metadata, autoload_with=engine)
    reviews = sa.Table("review_cases", metadata, autoload_with=engine)
    parcels = sa.Table("parcel_index", metadata, autoload_with=engine)
    audit = sa.Table("audit_events", metadata, autoload_with=engine)
    with engine.connect() as connection:
        record = connection.execute(sa.select(records).where(records.c.id == record_id)).mappings().one()
        document = connection.execute(sa.select(documents).where(documents.c.id == document_id)).mappings().one()
        case = connection.execute(sa.select(reviews).where(reviews.c.record_id == record_id)).mappings().one()
        parcel = connection.execute(sa.select(parcels).where(parcels.c.record_id == record_id)).mappings().one()
        events = connection.execute(sa.select(audit.c.event_type).where(audit.c.record_id == record_id)).scalars().all()
        assert record["validation_status"] == "human_review"
        assert record["payload"]["validationStatus"] == "human_review"
        assert document["validation"]["routing"] == "approved"
        assert document["extraction"]["validationStatus"] == "human_review"
        assert case["original_record"]["validationStatus"] == "approved"
        assert case["reviewed_record"]["validationStatus"] == "human_review"
        assert case["status"] == "queued" and case["quality_score"] == 96.0
        assert parcel["validation_status"] == "human_review"
        assert set(events) == {"VALIDATION_COMPLETED", "REVIEW_CREATED", "GEOMETRY_WITHDRAWN"}
        assert connection.scalar(sa.select(sa.func.count()).select_from(reviews).where(
            reviews.c.record_id == synthetic_record_id,
        )) == 0
        synthetic = connection.execute(sa.select(records).where(
            records.c.id == synthetic_record_id,
        )).mappings().one()
        assert synthetic["validation_status"] == "approved"
    engine.dispose()
    get_settings.cache_clear()
