"""SMTP health probes never expose provider details or delay health requests."""

from __future__ import annotations

from threading import Event
from time import sleep

from fastapi.testclient import TestClient

from app.api.routes.health import SmtpHealthMonitor
from app.config import Settings
from app.main import create_app
from app.services.email import SmtpMailTransport


def _settings(**overrides) -> Settings:
    return Settings(
        _env_file=None,
        environment="test",
        smtp_host="smtp.example.test",
        smtp_from="BhuDrishti AI <noreply@example.test>",
        **overrides,
    )


def test_unconfigured_smtp_health_has_no_connection_attempt(monkeypatch) -> None:
    def forbidden_probe(_self):
        raise AssertionError("Unconfigured SMTP must not be probed")

    monkeypatch.setattr(SmtpMailTransport, "verify_connection", forbidden_probe)
    monitor = SmtpHealthMonitor(Settings(_env_file=None, smtp_host=None, smtp_from=None))
    assert monitor.snapshot().model_dump() == {
        "configured": False,
        "connection_verified": None,
        "checking": False,
    }


def test_smtp_health_is_cached_and_health_request_never_waits_for_smtp(monkeypatch) -> None:
    entered = Event()
    release = Event()
    calls: list[None] = []

    def slow_probe(_self):
        calls.append(None)
        entered.set()
        assert release.wait(2)

    monkeypatch.setattr(SmtpMailTransport, "verify_connection", slow_probe)
    monitor = SmtpHealthMonitor(_settings(), refresh_seconds=3600)
    app = create_app()
    app.state.smtp_health = monitor
    client = TestClient(app)
    try:
        first = client.get("/api/v1/health")
        assert first.status_code == 200
        assert entered.wait(1)
        assert first.json()["smtp"] == {
            "configured": True,
            "connectionVerified": None,
            "checking": True,
        }
        assert "smtp.example.test" not in first.text
        assert "noreply@example.test" not in first.text
        assert client.get("/api/v1/health").status_code == 200
    finally:
        release.set()

    for _ in range(100):
        if monitor.snapshot().connection_verified is True:
            break
        sleep(0.01)
    assert monitor.snapshot().connection_verified is True
    assert len(calls) == 1


def test_failed_smtp_probe_reports_unavailable_without_error_details(monkeypatch) -> None:
    def failed_probe(_self):
        raise RuntimeError("account password appeared in SMTP response")

    monkeypatch.setattr(SmtpMailTransport, "verify_connection", failed_probe)
    monitor = SmtpHealthMonitor(_settings())
    monitor._check()
    status = monitor.snapshot().model_dump()
    assert status == {
        "configured": True,
        "connection_verified": False,
        "checking": False,
    }
    assert "password" not in str(status)
