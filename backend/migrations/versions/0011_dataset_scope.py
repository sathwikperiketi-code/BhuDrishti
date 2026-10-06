"""Persist operational and sample dataset separation without deleting history.

Revision ID: 0011_dataset_scope
Revises: 0010_sourced_geometry
"""

from __future__ import annotations

import json
import re

from alembic import op
import sqlalchemy as sa


revision = "0011_dataset_scope"
down_revision = "0010_sourced_geometry"
branch_labels = None
depends_on = None


def _json(value, fallback):
    if isinstance(value, str):
        try:
            value = json.loads(value)
        except (TypeError, ValueError):
            return fallback
    return value if isinstance(value, type(fallback)) else fallback


def _source_notice(pages) -> bool:
    text = "\n".join(str(page.get("text") or "") for page in _json(pages, []) if isinstance(page, dict)).casefold()
    return bool(re.search(r"\bsynthetic\b", text)) or any(notice in text for notice in (
        "fictional data", "demo document", "not an official land record",
        "not a government record", "not for legal or official use",
    ))


def upgrade() -> None:
    op.add_column("documents", sa.Column(
        "dataset_scope", sa.String(length=16), nullable=False, server_default="operational",
    ))
    op.add_column("documents", sa.Column("dataset_reason", sa.String(length=64), nullable=True))
    op.create_index("ix_documents_dataset_scope", "documents", ["dataset_scope"])

    connection = op.get_bind()
    metadata = sa.MetaData()
    documents = sa.Table("documents", metadata, autoload_with=connection)
    runs = sa.Table("demo_runs", metadata, autoload_with=connection)
    records = sa.Table("land_records", metadata, autoload_with=connection)
    demo_ids = set(connection.scalars(sa.select(runs.c.document_id)).all())
    record_source_ids: set[str] = set()
    for row in connection.execute(sa.select(records.c.document_id, records.c.source_document_id, records.c.payload)).mappings():
        payload = _json(row["payload"], {})
        source = payload.get("sourceDocument") or {}
        if isinstance(source, dict) and source.get("isSynthetic") is True:
            if row["document_id"]:
                record_source_ids.add(row["document_id"])
            elif row["source_document_id"]:
                record_source_ids.add(row["source_document_id"])

    rows = connection.execute(sa.select(
        documents.c.id, documents.c.demo_scenario,
        documents.c.processing_metadata, documents.c.ocr_pages,
    )).mappings().all()
    for row in rows:
        metadata_value = _json(row["processing_metadata"], {})
        reason = None
        if row["demo_scenario"] or row["id"] in demo_ids:
            reason = "legacy_demo"
        elif metadata_value.get("syntheticSourceDetected") is True:
            reason = "synthetic_metadata"
        elif _source_notice(row["ocr_pages"]):
            reason = "source_notice"
        elif row["id"] in record_source_ids:
            reason = "record_source"
        if reason:
            connection.execute(documents.update().where(documents.c.id == row["id"]).values(
                dataset_scope="sample", dataset_reason=reason,
            ))


def downgrade() -> None:
    # The source evidence and audit history remain unchanged by this migration.
    op.drop_index("ix_documents_dataset_scope", table_name="documents")
    op.drop_column("documents", "dataset_reason")
    op.drop_column("documents", "dataset_scope")
