"""Withdraw prototype polygons and add provenance for sourced parcel geometry.

Revision ID: 0010_sourced_geometry
Revises: 0009_officer_review

Existing record/review/audit history is retained. Legacy virtual grid shapes
are cleared, with a withdrawal event so prior GIS_INDEXED events cannot be
mistaken for current sourced boundaries.
"""

from __future__ import annotations

from datetime import datetime, timezone
from uuid import uuid4

from alembic import op
import sqlalchemy as sa


revision = "0010_sourced_geometry"
down_revision = "0009_officer_review"
branch_labels = None
depends_on = None


def upgrade() -> None:
    connection = op.get_bind()
    metadata = sa.MetaData()
    old_parcels = sa.Table("parcel_index", metadata, autoload_with=connection)
    withdrawn = connection.execute(
        sa.select(
            old_parcels.c.record_id, old_parcels.c.document_id,
            old_parcels.c.polygon, old_parcels.c.indexed_at,
        ).where(old_parcels.c.geometry_source == "local_prototype")
    ).mappings().all()

    with op.batch_alter_table("parcel_index") as batch:
        batch.alter_column("polygon", existing_type=sa.JSON(), nullable=True)
        batch.add_column(sa.Column("geometry_status", sa.String(length=16), nullable=False,
                                   server_default="unavailable"))
        batch.add_column(sa.Column("geometry_reference", sa.String(length=256), nullable=True))
        batch.add_column(sa.Column("geometry_file_name", sa.String(length=180), nullable=True))
        batch.add_column(sa.Column("geometry_sha256", sa.String(length=64), nullable=True))
        batch.add_column(sa.Column("geometry_recorded_at", sa.DateTime(timezone=True), nullable=True))
        batch.add_column(sa.Column("geometry_recorded_by", sa.String(length=64), nullable=True))
        batch.add_column(sa.Column("geometry_storage_key", sa.String(length=36), nullable=True))

    metadata = sa.MetaData()
    parcels = sa.Table("parcel_index", metadata, autoload_with=connection)
    audit = sa.Table("audit_events", metadata, autoload_with=connection)
    connection.execute(
        parcels.update().where(parcels.c.geometry_source == "local_prototype").values(
            polygon=None, geometry_source="unavailable", geometry_status="unavailable",
            indexed_at=None,
        )
    )
    now = datetime.now(timezone.utc)
    for parcel in withdrawn:
        connection.execute(audit.insert().values(
            id=str(uuid4()), record_id=parcel["record_id"],
            document_id=parcel["document_id"], actor_id="system",
            actor_role="SYSTEM", event_type="GEOMETRY_WITHDRAWN", timestamp=now,
            description="Legacy prototype parcel geometry withdrawn from operational GIS.",
            event_metadata={
                "migration": revision, "previousGeometrySource": "local_prototype",
                "hadPolygon": parcel["polygon"] is not None,
                "previousIndexedAt": parcel["indexed_at"].isoformat()
                if parcel["indexed_at"] else None,
            },
        ))


def downgrade() -> None:
    raise RuntimeError(
        "Sourced geometry migration cannot be reversed without restoring "
        "unverified prototype polygons; restore a pre-migration backup instead."
    )
