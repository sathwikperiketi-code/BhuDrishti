"""Phase 5 presentation runs and notification read receipts.

Revision ID: 0005_phase5
Revises: 0004_review_attempts
"""

from alembic import op
import sqlalchemy as sa


revision = "0005_phase5"
down_revision = "0004_review_attempts"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("documents") as batch:
        batch.add_column(sa.Column("demo_scenario", sa.String(length=64), nullable=True))
        batch.create_index("ix_documents_demo_scenario", ["demo_scenario"])

    op.create_table(
        "demo_runs",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("scenario_id", sa.String(length=64), nullable=False),
        sa.Column("document_id", sa.String(length=36), nullable=False, unique=True),
        sa.Column("created_by", sa.String(length=64), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("archived_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("ix_demo_runs_scenario_id", "demo_runs", ["scenario_id"])
    op.create_table(
        "notification_reads",
        sa.Column("user_id", sa.String(length=64), primary_key=True),
        sa.Column("event_id", sa.String(length=36), primary_key=True),
        sa.Column("read_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )


def downgrade() -> None:
    op.drop_table("notification_reads")
    op.drop_index("ix_demo_runs_scenario_id", table_name="demo_runs")
    op.drop_table("demo_runs")
    with op.batch_alter_table("documents") as batch:
        batch.drop_index("ix_documents_demo_scenario")
        batch.drop_column("demo_scenario")
