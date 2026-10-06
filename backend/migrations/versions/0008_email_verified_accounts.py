"""Extend existing accounts for verified email and single-use action tokens.

Revision ID: 0008_accounts
Revises: 0007_relationships

Accounts provisioned before this migration were trusted administrator/officer
accounts. Their active state and password hashes are preserved. Existing
inactive accounts become suspended. New registration starts unverified.
"""

from __future__ import annotations

from datetime import datetime, timezone
import hashlib
import re

from alembic import op
import sqlalchemy as sa


revision = "0008_accounts"
down_revision = "0007_relationships"
branch_labels = None
depends_on = None


def _legacy_username(email: str, user_id: str, taken: set[str]) -> str:
    local = email.partition("@")[0].casefold()
    local = re.sub(r"[^a-z0-9_.-]", "_", local).strip("._-")[:32]
    if len(local) < 3:
        local = "user_" + hashlib.sha256(user_id.encode("utf-8")).hexdigest()[:24]
    candidate = local
    if candidate in taken:
        digest = hashlib.sha256(user_id.encode("utf-8")).hexdigest()
        for length in range(8, 25, 2):
            candidate = f"{local[:31 - length]}_{digest[:length]}"
            if candidate not in taken:
                break
        else:
            raise RuntimeError("Cannot assign a unique username during account migration.")
    taken.add(candidate)
    return candidate


def upgrade() -> None:
    op.add_column("users", sa.Column("username", sa.String(length=32), nullable=True))
    op.add_column("users", sa.Column("status", sa.String(length=16), nullable=True))
    op.add_column("users", sa.Column("email_verified_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("users", sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True))

    connection = op.get_bind()
    existing = connection.execute(sa.text(
        "SELECT id, email, is_active, created_at FROM users ORDER BY id"
    )).mappings().all()
    taken: set[str] = set()
    now = datetime.now(timezone.utc)
    for account in existing:
        created_at = account["created_at"] or now
        connection.execute(sa.text(
            "UPDATE users SET username = :username, status = :status, "
            "email_verified_at = :verified_at, updated_at = :updated_at WHERE id = :id"
        ), {
            "id": account["id"],
            "username": _legacy_username(account["email"], account["id"], taken),
            "status": "ACTIVE" if account["is_active"] else "SUSPENDED",
            "verified_at": created_at,
            "updated_at": created_at,
        })

    with op.batch_alter_table("users") as batch:
        batch.alter_column("username", existing_type=sa.String(length=32), nullable=False)
        batch.alter_column("status", existing_type=sa.String(length=16), nullable=False)
        batch.alter_column(
            "updated_at", existing_type=sa.DateTime(timezone=True), nullable=False,
            server_default=sa.func.now(),
        )
        batch.create_check_constraint(
            "ck_users_status", "status IN ('UNVERIFIED', 'ACTIVE', 'SUSPENDED')",
        )
        batch.create_index("ix_users_username", ["username"], unique=True)
        batch.create_index("ix_users_status", ["status"])

    op.create_table(
        "auth_action_tokens",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("user_id", sa.String(length=36), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("purpose", sa.String(length=24), nullable=False),
        sa.Column("token_hash", sa.String(length=64), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("used_at", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint(
            "purpose IN ('EMAIL_VERIFICATION', 'PASSWORD_RESET')",
            name="ck_auth_action_tokens_purpose",
        ),
    )
    op.create_index("ix_auth_action_tokens_user_id", "auth_action_tokens", ["user_id"])
    op.create_index("ix_auth_action_tokens_purpose", "auth_action_tokens", ["purpose"])
    op.create_index("ix_auth_action_tokens_token_hash", "auth_action_tokens", ["token_hash"], unique=True)


def downgrade() -> None:
    op.drop_index("ix_auth_action_tokens_token_hash", table_name="auth_action_tokens")
    op.drop_index("ix_auth_action_tokens_purpose", table_name="auth_action_tokens")
    op.drop_index("ix_auth_action_tokens_user_id", table_name="auth_action_tokens")
    op.drop_table("auth_action_tokens")
    with op.batch_alter_table("users") as batch:
        batch.drop_index("ix_users_status")
        batch.drop_index("ix_users_username")
        batch.drop_constraint("ck_users_status", type_="check")
        batch.drop_column("updated_at")
        batch.drop_column("email_verified_at")
        batch.drop_column("status")
        batch.drop_column("username")
