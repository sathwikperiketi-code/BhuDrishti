"""Keep self-selected administrator access pending until an existing admin approves.

Revision ID: 0012_role_approval
Revises: 0011_dataset_scope

All new fields are nullable so existing users, administrator roles, passwords,
and sessions remain unchanged.
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "0012_role_approval"
down_revision = "0011_dataset_scope"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("users") as batch:
        batch.add_column(sa.Column("requested_role", sa.String(length=32), nullable=True))
        batch.add_column(sa.Column("role_approval_status", sa.String(length=16), nullable=True))
        batch.add_column(sa.Column(
            "role_reviewed_by", sa.String(length=36),
            sa.ForeignKey("users.id", name="fk_users_role_reviewed_by"), nullable=True,
        ))
        batch.add_column(sa.Column("role_reviewed_at", sa.DateTime(timezone=True), nullable=True))
        batch.create_check_constraint(
            "ck_users_requested_role",
            "requested_role IS NULL OR requested_role IN ('ADMIN', 'REVENUE_OFFICER', 'VERIFIER', 'AUDITOR')",
        )
        batch.create_check_constraint(
            "ck_users_role_approval_status",
            "role_approval_status IS NULL OR role_approval_status IN ('PENDING', 'APPROVED', 'REJECTED')",
        )
        batch.create_index("ix_users_role_approval_status", ["role_approval_status"])


def downgrade() -> None:
    with op.batch_alter_table("users") as batch:
        batch.drop_index("ix_users_role_approval_status")
        batch.drop_constraint("ck_users_role_approval_status", type_="check")
        batch.drop_constraint("ck_users_requested_role", type_="check")
        batch.drop_column("role_reviewed_at")
        batch.drop_column("role_reviewed_by")
        batch.drop_column("role_approval_status")
        batch.drop_column("requested_role")
