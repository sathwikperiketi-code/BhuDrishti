"""The email-verification migration preserves provisioned accounts and sessions."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from pathlib import Path

from alembic import command
from alembic.config import Config
import pytest
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.config import get_settings
from app.db.models import UserModel
from app.db.session import build_engine
from app.services.auth.service import LocalPasswordProvider, hash_password


def _config(backend: Path) -> Config:
    config = Config(str(backend / "alembic.ini"))
    config.set_main_option("script_location", str(backend / "migrations"))
    return config


def test_migration_keeps_existing_accounts_and_sessions(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    backend = Path(__file__).resolve().parents[1]
    database_url = f"sqlite:///{(tmp_path / 'accounts.db').as_posix()}"
    monkeypatch.setenv("BHUDRISHTI_DATABASE_URL", database_url)
    get_settings.cache_clear()
    config = _config(backend)
    command.upgrade(config, "0007_relationships")

    engine = build_engine(database_url)
    now = datetime.now(timezone.utc)
    admin_password = "MigrationTestPassword123!"
    before = (
        ("admin-1", "admin@example.test", hash_password(admin_password), 1),
        ("admin-2", "Admin@other.test", "second-hash", 1),
        ("inactive", "officer@example.test", "third-hash", 0),
    )
    with engine.begin() as connection:
        for user_id, email, password_hash, is_active in before:
            connection.execute(text(
                "INSERT INTO users (id, email, name, role, password_hash, is_active, "
                "failed_login_count, created_at) VALUES (:id, :email, :name, :role, "
                ":password_hash, :is_active, 0, :created_at)"
            ), {
                "id": user_id,
                "email": email,
                "name": user_id,
                "role": "ADMIN" if user_id.startswith("admin") else "AUDITOR",
                "password_hash": password_hash,
                "is_active": is_active,
                "created_at": now,
            })
        connection.execute(text(
            "INSERT INTO auth_sessions (id, user_id, created_at, expires_at) "
            "VALUES (:id, :user_id, :created_at, :expires_at)"
        ), {
            "id": "session-before-migration", "user_id": "admin-1",
            "created_at": now, "expires_at": now + timedelta(hours=1),
        })
    engine.dispose()

    command.upgrade(config, "head")
    command.check(config)
    engine = build_engine(database_url)
    with engine.connect() as connection:
        migrated = connection.execute(text(
            "SELECT id, username, password_hash, is_active, status, email_verified_at, "
            "updated_at FROM users ORDER BY id"
        )).mappings().all()
        assert len(migrated) == 3
        assert len({row["username"] for row in migrated}) == 3
        assert all(3 <= len(row["username"]) <= 32 for row in migrated)
        assert {row["id"]: row["password_hash"] for row in migrated} == {
            user_id: password_hash for user_id, _, password_hash, _ in before
        }
        assert {row["id"]: row["status"] for row in migrated} == {
            "admin-1": "ACTIVE", "admin-2": "ACTIVE", "inactive": "SUSPENDED",
        }
        assert all(row["email_verified_at"] and row["updated_at"] for row in migrated)
        assert connection.scalar(text(
            "SELECT user_id FROM auth_sessions WHERE id = 'session-before-migration'"
        )) == "admin-1"
        assert connection.execute(text("PRAGMA foreign_key_check")).all() == []

    with Session(engine) as session:
        admin = LocalPasswordProvider().authenticate(
            session, "admin@example.test", admin_password,
        )
        assert isinstance(admin, UserModel)
        assert admin.id == "admin-1"

    with pytest.raises(IntegrityError), engine.begin() as connection:
        connection.execute(text(
            "UPDATE users SET username = :username WHERE id = 'admin-2'"
        ), {"username": migrated[0]["username"]})
    engine.dispose()
    get_settings.cache_clear()
