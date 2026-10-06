"""Legacy virtual parcels are withdrawn without losing review or audit history."""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4

from alembic import command
from alembic.config import Config
import pytest
from sqlalchemy import MetaData, Table, select, text

from app.config import get_settings
from app.db.session import build_engine


def test_migration_withdraws_legacy_virtual_geometry_and_preserves_history(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    backend = Path(__file__).resolve().parents[1]
    database_url = f"sqlite:///{(tmp_path / 'geometry-migration.db').as_posix()}"
    monkeypatch.setenv("BHUDRISHTI_DATABASE_URL", database_url)
    get_settings.cache_clear()
    config = Config(str(backend / "alembic.ini"))
    config.set_main_option("script_location", str(backend / "migrations"))
    command.upgrade(config, "0009_officer_review")

    engine = build_engine(database_url)
    metadata = MetaData()
    documents = Table("documents", metadata, autoload_with=engine)
    records = Table("land_records", metadata, autoload_with=engine)
    parcels = Table("parcel_index", metadata, autoload_with=engine)
    audit = Table("audit_events", metadata, autoload_with=engine)
    document_id, record_id, old_event_id = str(uuid4()), str(uuid4()), str(uuid4())
    old_polygon = [
        [17.0, 78.0], [17.0, 78.1], [17.1, 78.1],
        [17.1, 78.0], [17.0, 78.0],
    ]
    with engine.begin() as connection:
        connection.execute(documents.insert().values(
            id=document_id, file_name="record.pdf", mime_type="application/pdf",
            file_size=10, sha256="a" * 64, storage_key=str(uuid4()), page_count=1,
            status="completed", stage="final_routing", attempts=1,
            pages=[], stages=[], processing_metadata={}, ocr_pages=[], fields=[], warnings=[],
        ))
        connection.execute(records.insert().values(
            id=record_id, document_id=document_id, source_document_id=document_id,
            validation_status="approved", payload={"recordId": record_id, "surveyNumber": "123/4A"},
        ))
        connection.execute(parcels.insert().values(
            record_id=record_id, document_id=document_id, status="verified",
            validation_status="approved", polygon=old_polygon,
            geometry_source="local_prototype", indexed_at=datetime.now(timezone.utc),
            survey_number="123/4A",
        ))
        connection.execute(audit.insert().values(
            id=old_event_id, record_id=record_id, document_id=document_id,
            actor_id="gis-indexer", actor_role="SYSTEM", event_type="GIS_INDEXED",
            description="Legacy virtual parcel indexed.", event_metadata={"geometrySource": "local_prototype"},
        ))
    engine.dispose()

    command.upgrade(config, "head")
    engine = build_engine(database_url)
    with engine.connect() as connection:
        migrated_parcels = Table("parcel_index", MetaData(), autoload_with=engine)
        parcel = connection.execute(select(migrated_parcels).where(
            migrated_parcels.c.record_id == record_id
        )).mappings().one()
        assert parcel["status"] == "verified"
        assert parcel["survey_number"] == "123/4A"
        assert parcel["polygon"] is None
        assert parcel["geometry_source"] == "unavailable"
        assert parcel["geometry_status"] == "unavailable"
        assert parcel["indexed_at"] is None
        assert parcel["geometry_storage_key"] is None
        event_types = connection.execute(text(
            "SELECT event_type FROM audit_events WHERE record_id = :record_id ORDER BY timestamp, id"
        ), {"record_id": record_id}).scalars().all()
        assert "GIS_INDEXED" in event_types  # Immutable historical event remains traceable.
        assert "GEOMETRY_WITHDRAWN" in event_types
        assert connection.execute(text("PRAGMA foreign_key_check")).all() == []
    engine.dispose()
    get_settings.cache_clear()
