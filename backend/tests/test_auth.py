"""Persisted identity, revocable sessions, and server-derived role checks."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from pathlib import Path

from fastapi.testclient import TestClient
from pydantic import ValidationError
import pytest
from sqlalchemy import select
from sqlalchemy.engine import make_url
from sqlalchemy.orm import sessionmaker

from app.config import Settings, get_settings
from app.contracts.auth import Role
from app.db.base import Base
from app.db.models import AuthSessionModel, UserModel
from app.db.session import build_engine, get_db
from app.main import app
from app.services.auth.service import create_user


@pytest.fixture
def auth_client(tmp_path: Path):
    settings = Settings(
        _env_file=None, environment="test",
        database_url=f"sqlite:///{(tmp_path / 'auth.db').as_posix()}",
        document_storage_dir=str(tmp_path / "uploads"),
    )
    engine = build_engine(settings.database_url)
    Base.metadata.create_all(bind=engine)
    factory = sessionmaker(bind=engine, autoflush=False, autocommit=False, expire_on_commit=False)

    def override_db():
        with factory() as session:
            yield session

    app.dependency_overrides[get_db] = override_db
    app.dependency_overrides[get_settings] = lambda: settings
    with TestClient(app) as client:
        yield client, factory
    app.dependency_overrides.clear()
    engine.dispose()


def _login(client: TestClient, email: str, password: str = "StrongTestPassword123!") -> dict:
    response = client.post("/api/v1/auth/login", json={"email": email, "password": password})
    assert response.status_code == 200, response.text
    return response.json()


def test_no_default_account_and_sessions_are_revocable(auth_client) -> None:
    client, factory = auth_client
    assert client.post("/api/v1/auth/demo/session", json={"userId": "admin"}).status_code == 404
    assert client.post("/api/v1/auth/login", json={
        "email": "admin@example.test", "password": "StrongTestPassword123!",
    }).status_code == 401
    with factory() as session:
        create_user(
            session, email="admin@example.test", name="Test Administrator",
            password="StrongTestPassword123!", role=Role.ADMIN,
        )
        session.commit()
    assert client.post("/api/v1/auth/login", json={
        "email": "admin@example.test", "password": "incorrect",
    }).status_code == 401
    login = _login(client, "admin@example.test")
    token = login["accessToken"]
    headers = {"Authorization": f"Bearer {token}"}
    assert login["user"]["email"] == "admin@example.test"
    assert login["user"]["role"] == "ADMIN"
    assert "password" not in str(login).lower()
    assert client.get("/api/v1/auth/me", headers=headers).json()["id"] == login["user"]["id"]
    tampered = token[:-1] + ("A" if token[-1] != "A" else "B")
    assert client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {tampered}"}).status_code == 401
    assert client.post("/api/v1/auth/logout", headers=headers).status_code == 204
    assert client.get("/api/v1/auth/me", headers=headers).status_code == 401


def test_role_is_loaded_from_database_and_admin_provisions_accounts(auth_client) -> None:
    client, factory = auth_client
    with factory() as session:
        create_user(
            session, email="admin@example.test", name="Test Administrator",
            password="StrongTestPassword123!", role=Role.ADMIN,
        )
        officer = create_user(
            session, email="officer@example.test", name="Test Officer",
            password="StrongTestPassword123!", role=Role.REVENUE_OFFICER,
        )
        officer_id = officer.id
        session.commit()
    admin = _login(client, "admin@example.test")
    admin_headers = {"Authorization": f"Bearer {admin['accessToken']}"}
    officer = _login(client, "officer@example.test")
    officer_headers = {"Authorization": f"Bearer {officer['accessToken']}"}
    assert client.get("/api/v1/auth/users", headers=officer_headers).status_code == 403
    assert client.post("/api/v1/auth/users", headers=officer_headers, json={
        "email": "verifier@example.test", "name": "Test Verifier",
        "password": "StrongTestPassword123!", "role": "VERIFIER",
    }).status_code == 403
    created = client.post("/api/v1/auth/users", headers=admin_headers, json={
        "email": "Verifier@Example.Test", "name": "Test Verifier",
        "password": "StrongTestPassword123!", "role": "VERIFIER",
    })
    assert created.status_code == 201, created.text
    assert created.json()["email"] == "verifier@example.test"
    assert created.json()["role"] == "VERIFIER"
    assert len(client.get("/api/v1/auth/users", headers=admin_headers).json()) == 3
    assert client.post("/api/v1/auth/users", headers=admin_headers, json={
        "email": "verifier@example.test", "name": "Another Verifier",
        "password": "StrongTestPassword123!", "role": "VERIFIER",
    }).status_code == 409
    with factory() as session:
        stored = session.get(UserModel, officer_id)
        stored.role = Role.AUDITOR.value
        session.commit()
    assert client.get("/api/v1/auth/me", headers=officer_headers).json()["role"] == "AUDITOR"
    assert client.post("/api/v1/documents/upload", headers={
        **officer_headers, "X-Role": "ADMIN",
    }).status_code == 403
    with factory() as session:
        stored = session.get(UserModel, officer_id)
        stored.is_active = False
        session.commit()
    assert client.get("/api/v1/auth/me", headers=officer_headers).status_code == 401


def test_signing_key_survives_client_restart_and_lockout_is_persisted(auth_client) -> None:
    client, factory = auth_client
    with factory() as session:
        user = create_user(
            session, email="officer@example.test", name="Test Officer",
            password="StrongTestPassword123!", role=Role.REVENUE_OFFICER,
        )
        user_id = user.id
        session.commit()
    token = _login(client, "officer@example.test")["accessToken"]
    with TestClient(app) as second_client:
        assert second_client.get("/api/v1/auth/me", headers={
            "Authorization": f"Bearer {token}",
        }).status_code == 200
    for _ in range(5):
        assert client.post("/api/v1/auth/login", json={
            "email": "officer@example.test", "password": "wrong",
        }).status_code == 401
    assert client.post("/api/v1/auth/login", json={
        "email": "officer@example.test", "password": "StrongTestPassword123!",
    }).status_code == 401
    with factory() as session:
        stored = session.get(UserModel, user_id)
        assert stored.locked_until is not None
        stored.locked_until = datetime.now(timezone.utc) - timedelta(seconds=1)
        session.commit()
    assert client.post("/api/v1/auth/login", json={
        "email": "officer@example.test", "password": "StrongTestPassword123!",
    }).status_code == 200


def test_login_normalization_generic_failures_and_persisted_session(auth_client) -> None:
    client, factory = auth_client
    with factory() as session:
        user = create_user(
            session, email="  Admin@Example.Test  ", name="Test Administrator",
            password="StrongTestPassword123!", role=Role.ADMIN,
        )
        user_id = user.id
        session.commit()

    wrong_password = client.post("/api/v1/auth/login", json={
        "email": "admin@example.test", "password": "wrong",
    })
    unknown_email = client.post("/api/v1/auth/login", json={
        "email": "unknown@example.test", "password": "wrong",
    })
    assert wrong_password.status_code == unknown_email.status_code == 401
    assert wrong_password.json() == unknown_email.json()

    login = _login(client, "  ADMIN@EXAMPLE.TEST  ")
    assert login["user"]["id"] == user_id
    assert login["user"]["email"] == "admin@example.test"
    headers = {"Authorization": f"Bearer {login['accessToken']}"}
    assert client.get("/api/v1/auth/me", headers=headers).json()["role"] == "ADMIN"
    assert client.get("/api/v1/documents", headers=headers).status_code == 200
    with factory() as session:
        sessions = session.scalars(select(AuthSessionModel).where(AuthSessionModel.user_id == user_id)).all()
        assert len(sessions) == 1
        assert sessions[0].revoked_at is None

    with factory() as session:
        stored = session.get(UserModel, user_id)
        stored.is_active = False
        session.commit()
    inactive = client.post("/api/v1/auth/login", json={
        "email": "admin@example.test", "password": "StrongTestPassword123!",
    })
    assert inactive.status_code == 401
    assert inactive.json() == wrong_password.json()
    assert client.get("/api/v1/auth/me", headers=headers).status_code == 401


def test_protected_endpoints_reject_missing_and_invalid_bearers(auth_client) -> None:
    client, _factory = auth_client
    assert client.get("/api/v1/auth/me").status_code == 401
    assert client.get("/api/v1/documents").status_code == 401
    assert client.get("/api/v1/auth/users").status_code == 401
    assert client.get("/api/v1/documents", headers={
        "Authorization": "Bearer invalid",
    }).status_code == 401


def test_auth_configuration_rejects_missing_production_secret_and_wildcard_cors() -> None:
    with pytest.raises(ValidationError, match="BHUDRISHTI_AUTH_SECRET"):
        Settings(_env_file=None, environment="production", auth_secret=None)
    with pytest.raises(ValidationError, match="CORS origins"):
        Settings(_env_file=None, cors_origins=["*"])


def test_default_local_database_path_is_independent_of_working_directory(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.delenv("BHUDRISHTI_DATABASE_URL", raising=False)
    monkeypatch.chdir(tmp_path)
    settings = Settings(_env_file=None)
    assert Path(make_url(settings.database_url).database).resolve() == (
        Path(__file__).resolve().parents[1] / "bhudrishti.db"
    )
    configured = tmp_path / "explicit.db"
    monkeypatch.setenv("BHUDRISHTI_DATABASE_URL", f"sqlite:///{configured.as_posix()}")
    assert Path(make_url(Settings(_env_file=None).database_url).database).resolve() == configured
