"""Constrain uploaded document, review, audit, notification, and GIS links.

Revision ID: 0007_relationships
Revises: 0006_auth

Legacy reference records may have a source_document_id that is not an uploaded
document. Preserve that value and backfill the new nullable document_id only
for records with a real parent document.
"""

from alembic import op
import sqlalchemy as sa


revision = "0007_relationships"
down_revision = "0006_auth"
branch_labels = None
depends_on = None


def _require_no_orphans(connection) -> None:
    links = (
        ("review_cases", "record_id", "land_records"),
        ("review_cases", "document_id", "documents"),
        ("parcel_index", "record_id", "land_records"),
        ("parcel_index", "document_id", "documents"),
        ("audit_events", "document_id", "documents"),
        ("notification_reads", "event_id", "audit_events"),
    )
    for child, key, parent in links:
        count = connection.scalar(sa.text(
            f"SELECT COUNT(*) FROM {child} AS child "
            f"WHERE child.{key} IS NOT NULL AND NOT EXISTS "
            f"(SELECT 1 FROM {parent} AS parent WHERE parent.id = child.{key})"
        ))
        if count:
            raise RuntimeError(
                f"Cannot add {child}.{key} relationship: {count} existing rows lack a {parent} parent."
            )


def upgrade() -> None:
    connection = op.get_bind()
    _require_no_orphans(connection)

    with op.batch_alter_table("land_records") as batch:
        batch.add_column(sa.Column("document_id", sa.String(length=36), nullable=True))
        batch.create_index("ix_land_records_document_id", ["document_id"])
        batch.create_foreign_key(
            "fk_land_records_document_id_documents", "documents", ["document_id"], ["id"],
        )
    connection.execute(sa.text(
        "UPDATE land_records SET document_id = source_document_id "
        "WHERE source_document_id IN (SELECT id FROM documents)"
    ))
    with op.batch_alter_table("review_cases") as batch:
        batch.create_foreign_key(
            "fk_review_cases_record_id_land_records", "land_records", ["record_id"], ["id"],
        )
        batch.create_foreign_key(
            "fk_review_cases_document_id_documents", "documents", ["document_id"], ["id"],
        )
    with op.batch_alter_table("parcel_index") as batch:
        batch.create_foreign_key(
            "fk_parcel_index_record_id_land_records", "land_records", ["record_id"], ["id"],
        )
        batch.create_foreign_key(
            "fk_parcel_index_document_id_documents", "documents", ["document_id"], ["id"],
        )
    with op.batch_alter_table("audit_events") as batch:
        batch.create_foreign_key(
            "fk_audit_events_document_id_documents", "documents", ["document_id"], ["id"],
        )
    with op.batch_alter_table("notification_reads") as batch:
        batch.create_foreign_key(
            "fk_notification_reads_event_id_audit_events", "audit_events", ["event_id"], ["id"],
        )


def downgrade() -> None:
    with op.batch_alter_table("notification_reads") as batch:
        batch.drop_constraint("fk_notification_reads_event_id_audit_events", type_="foreignkey")
    with op.batch_alter_table("audit_events") as batch:
        batch.drop_constraint("fk_audit_events_document_id_documents", type_="foreignkey")
    with op.batch_alter_table("parcel_index") as batch:
        batch.drop_constraint("fk_parcel_index_document_id_documents", type_="foreignkey")
        batch.drop_constraint("fk_parcel_index_record_id_land_records", type_="foreignkey")
    with op.batch_alter_table("review_cases") as batch:
        batch.drop_constraint("fk_review_cases_document_id_documents", type_="foreignkey")
        batch.drop_constraint("fk_review_cases_record_id_land_records", type_="foreignkey")
    with op.batch_alter_table("land_records") as batch:
        batch.drop_constraint("fk_land_records_document_id_documents", type_="foreignkey")
        batch.drop_index("ix_land_records_document_id")
        batch.drop_column("document_id")
