"""Service failures remain distinguishable without leaking submitted values."""
import logging

from fastapi.testclient import TestClient
from sqlalchemy.exc import OperationalError

import app.main as main_module
from app.config import Settings, get_settings
from app.db.session import get_db


def isolated_app(monkeypatch):
    settings = Settings(_env_file=None, environment="test", smtp_host=None, smtp_from=None)
    monkeypatch.setattr(main_module, "get_settings", lambda: settings)
    application = main_module.create_app()
    application.dependency_overrides[get_settings] = lambda: settings
    return application


def test_database_failure_returns_safe_503_and_sanitized_diagnostics(monkeypatch, caplog):
    application = isolated_app(monkeypatch)
    secret = "private-password-and-verification-token"

    def unavailable_database():
        raise OperationalError("SQL containing " + secret, {"password": secret}, OSError(secret))

    application.dependency_overrides[get_db] = unavailable_database
    with caplog.at_level(logging.ERROR), TestClient(application) as client:
        response = client.post("/api/v1/auth/signup", json={
            "fullName": "QA Database Failure", "username": "qa.database.failure",
            "email": "database.failure@example.test", "password": "QA-Safe-Password-2026!",
            "confirmPassword": "QA-Safe-Password-2026!", "requestedRole": "AUDITOR",
        })
    assert response.status_code == 503
    assert response.headers["X-BhuDrishti-Error-Code"] == "DATABASE_UNAVAILABLE"
    assert "database is unavailable" in response.json()["detail"]
    assert "driver_error_type=OSError" in caplog.text
    assert secret not in response.text and secret not in caplog.text


def test_root_health_alias_keeps_existing_versioned_health(monkeypatch):
    application = isolated_app(monkeypatch)
    with TestClient(application) as client:
        for route in ("/health", "/api/v1/health"):
            response = client.get(route)
            assert response.status_code == 200
            assert response.json()["status"] == "ok"
            assert response.json()["smtp"]["configured"] is False
