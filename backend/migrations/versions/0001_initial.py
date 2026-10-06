"""Create canonical land record storage and searchable columns.

Revision ID: 0001_initial
Revises:
"""

from alembic import op
import sqlalchemy as sa


revision = "0001_initial"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "land_records",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("record_number", sa.String(length=128), nullable=True),
        sa.Column("owner_name", sa.String(length=256), nullable=True),
        sa.Column("survey_number", sa.String(length=128), nullable=True),
        sa.Column("area", sa.Float(), nullable=True),
        sa.Column("area_unit", sa.String(length=32), nullable=True),
        sa.Column("district", sa.String(length=128), nullable=True),
        sa.Column("state", sa.String(length=128), nullable=True),
        sa.Column("validation_status", sa.String(length=32), nullable=False),
        sa.Column("source_document_id", sa.String(length=256), nullable=True),
        sa.Column("payload", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    for name in (
        "record_number",
        "owner_name",
        "survey_number",
        "district",
        "state",
        "validation_status",
        "source_document_id",
    ):
        op.create_index(f"ix_land_records_{name}", "land_records", [name])


def downgrade() -> None:
    op.drop_table("land_records")
