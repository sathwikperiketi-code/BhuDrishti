"""Dataset backfill separates old samples while retaining their stored evidence."""

from __future__ import annotations

from pathlib import Path
from uuid import uuid4

from alembic import command
from alembic.config import Config
import pytest
from sqlalchemy import MetaData, Table, select, text

from app.config import get_settings
from app.db.session import build_engine


def test_dataset_migration_classifies_existing_evidence_without_deleting_it(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    backend = Path(__file__).resolve().parents[1]
    database_url = f"sqlite:///{(tmp_path / 'dataset-migration.db').as_posix()}"
    monkeypatch.setenv("BHUDRISHTI_DATABASE_URL", database_url)
    get_settings.cache_clear()
    config = Config(str(backend / "alembic.ini"))
    config.set_main_option("script_location", str(backend / "migrations"))
    command.upgrade(config, "0010_sourced_geometry")

    engine = build_engine(database_url)
    metadata = MetaData()
    documents = Table("documents", metadata, autoload_with=engine)
    records = Table("land_records", metadata, autoload_with=engine)
    audit = Table("audit_events", metadata, autoload_with=engine)
    ids = {name: str(uuid4()) for name in ("operational", "notice", "metadata", "record_source", "legacy_demo")}
    notices = {"operational": "Owner Name: Ravi Kumar", "notice": "Synthetic test record. Not an official land record."}
    event_id = str(uuid4())
    with engine.begin() as connection:
        for name, document_id in ids.items():
            connection.execute(documents.insert().values(
                id=document_id, file_name=f"{name}.pdf", mime_type="application/pdf",
                file_size=10, sha256=(str(len(name)) * 64)[:64], storage_key=str(uuid4()),
                page_count=1, status="completed", stage="final_routing", attempts=1,
                pages=[], stages=[],
                processing_metadata={"syntheticSourceDetected": True} if name == "metadata" else {},
                ocr_pages=[{"page_number": 1, "text": notices.get(name, "Owner Name: Meera Rao")}],
                fields=[], warnings=[],
                demo_scenario="historical_demo" if name == "legacy_demo" else None,
            ))
        record_id = str(uuid4())
        connection.execute(records.insert().values(
            id=record_id, document_id=ids["record_source"], source_document_id=ids["record_source"],
            validation_status="human_review",
            payload={"recordId": record_id, "sourceDocument": {"isSynthetic": True}},
        ))
        connection.execute(audit.insert().values(
            id=event_id, record_id=str(uuid4()), document_id=ids["notice"],
            actor_id="migration-test", actor_role="SYSTEM", event_type="DOCUMENT_UPLOADED",
            description="Source uploaded before dataset migration.", event_metadata={"fileName": "notice.pdf"},
        ))
    engine.dispose()

    command.upgrade(config, "head")
    engine = build_engine(database_url)
    migrated = Table("documents", MetaData(), autoload_with=engine)
    with engine.connect() as connection:
        rows = {row["id"]: row for row in connection.execute(select(migrated)).mappings()}
        assert len(rows) == len(ids)
        assert rows[ids["operational"]]["dataset_scope"] == "operational"
        assert rows[ids["operational"]]["dataset_reason"] is None
        assert {rows[ids[name]]["dataset_scope"] for name in ids if name != "operational"} == {"sample"}
        assert rows[ids["notice"]]["dataset_reason"] == "source_notice"
        assert rows[ids["metadata"]]["dataset_reason"] == "synthetic_metadata"
        assert rows[ids["record_source"]]["dataset_reason"] == "record_source"
        assert rows[ids["legacy_demo"]]["dataset_reason"] == "legacy_demo"
        assert rows[ids["notice"]]["ocr_pages"][0]["text"] == notices["notice"]
        assert connection.scalar(text("SELECT document_id FROM audit_events WHERE id = :event_id"),
                                 {"event_id": event_id}) == ids["notice"]
        assert connection.scalar(text("SELECT id FROM land_records WHERE id = :record_id"),
                                 {"record_id": record_id}) == record_id
        assert connection.execute(text("PRAGMA foreign_key_check")).all() == []
    engine.dispose()
    get_settings.cache_clear()
