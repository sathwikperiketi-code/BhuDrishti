"""HTTP/database integration coverage for email-verified account workflows."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from email.message import EmailMessage
from hashlib import sha256
from html.parser import HTMLParser
from urllib.parse import parse_qs, urlsplit

from fastapi.testclient import TestClient
import pytest
from sqlalchemy import select
from sqlalchemy.orm import sessionmaker

from app.api.routes.auth import _mail_transport
from app.config import Settings, get_settings
from app.contracts.auth import Role
from app.db.base import Base
from app.db.models import AuthActionTokenModel, UserModel
from app.db.session import build_engine, get_db
from app.main import app
from app.services.auth.service import create_user, verify_password
from app.services.email import EmailDeliveryError


NEW_PASSWORD = "SecureAccountPassword123!"
RESET_PASSWORD = "NewSecurePassword456!"
ADDRESS = "reader@example.test"


class CapturingTransport:
    def __init__(self) -> None:
        self.messages: list[EmailMessage] = []
        self.connection_checks = 0

    def verify_connection(self) -> None:
        self.connection_checks += 1

    def send(self, message: EmailMessage) -> None:
        self.messages.append(message)


@pytest.fixture
def account_client(tmp_path):
    settings = Settings(
        _env_file=None, environment="test",
        database_url=f"sqlite:///{(tmp_path / 'accounts.db').as_posix()}",
        document_storage_dir=str(tmp_path / "uploads"),
        smtp_from="BhuDrishti AI <noreply@example.test>",
        smtp_host="smtp.example.test",
    )
    engine = build_engine(settings.database_url)
    Base.metadata.create_all(bind=engine)
    factory = sessionmaker(bind=engine, autoflush=False, autocommit=False, expire_on_commit=False)
    transport = CapturingTransport()

    def override_db():
        with factory() as session:
            yield session

    app.dependency_overrides[get_db] = override_db
    app.dependency_overrides[get_settings] = lambda: settings
    app.dependency_overrides[_mail_transport] = lambda: transport
    with TestClient(app) as client:
        yield client, factory, transport
    app.dependency_overrides.clear()
    engine.dispose()


def _signup(
    client: TestClient, *, email: str = ADDRESS, username: str = "Reader.One",
    requested_role: str = "AUDITOR",
):
    return client.post("/api/v1/auth/signup", json={
        "fullName": "Example Reader", "username": username, "email": email,
        "password": NEW_PASSWORD, "confirmPassword": NEW_PASSWORD,
        "requestedRole": requested_role,
    })


def _mail_token(message: EmailMessage, route: str) -> str:
    plain = message.get_body(preferencelist=("plain",))
    assert plain is not None
    action_line = next(line for line in plain.get_content().splitlines() if f"/#/{route}?token=" in line)
    url = action_line.split(": ", 1)[1]
    fragment = urlsplit(url).fragment
    assert fragment.startswith(f"/{route}?token=")
    return parse_qs(fragment.split("?", 1)[1])["token"][0]


def _verify(client: TestClient, transport: CapturingTransport) -> str:
    token = _mail_token(transport.messages[-1], "verify-email")
    response = client.post("/api/v1/auth/verify-email", json={"token": token})
    assert response.status_code == 200
    return token


def _login(client: TestClient, password: str = NEW_PASSWORD):
    return client.post("/api/v1/auth/login", json={"email": ADDRESS, "password": password})


def test_signup_persists_unverified_account_and_hash_only_token(account_client):
    client, factory, transport = account_client
    response = _signup(client, email="  Reader@Example.Test ")
    assert response.status_code == 202
    assert response.json()["message"] == "Check your email to verify your BhuDrishti account."
    assert len(transport.messages) == 1
    raw_token = _mail_token(transport.messages[0], "verify-email")
    with factory() as session:
        user = session.scalar(select(UserModel).where(UserModel.email == ADDRESS))
        assert user is not None
        assert user.username == "reader.one"
        assert user.name == "Example Reader"
        assert user.role == "AUDITOR"
        assert user.status == "UNVERIFIED"
        assert not user.is_active and user.email_verified_at is None
        assert user.password_hash != NEW_PASSWORD
        assert verify_password(NEW_PASSWORD, user.password_hash)
        token = session.scalar(select(AuthActionTokenModel).where(AuthActionTokenModel.user_id == user.id))
        assert token.purpose == "EMAIL_VERIFICATION"
        assert token.token_hash != raw_token and len(token.token_hash) == 64
        assert token.expires_at > datetime.now(timezone.utc).replace(tzinfo=None)
    assert _login(client).status_code == 401
    assert client.get("/api/v1/documents").status_code == 401


def test_signup_emails_exact_persisted_token_without_consuming_it(account_client):
    client, factory, _transport = account_client

    class EmailLinks(HTMLParser):
        def __init__(self):
            super().__init__()
            self.links = []

        def handle_starttag(self, tag, attrs):
            if tag == "a":
                self.links.extend(value for name, value in attrs if name == "href")

    def assert_pending_token(message):
        raw_token = _mail_token(message, "verify-email")
        with factory() as session:
            user = session.scalar(select(UserModel).where(UserModel.email == ADDRESS))
            assert user is not None and user.status == "UNVERIFIED"
            assert user.email_verified_at is None and not user.is_active
            tokens = session.scalars(select(AuthActionTokenModel).where(
                AuthActionTokenModel.user_id == user.id,
            )).all()
            assert len(tokens) == 1
            token = tokens[0]
            assert token.purpose == "EMAIL_VERIFICATION"
            assert token.token_hash == sha256(raw_token.encode("utf-8")).hexdigest()
            assert token.used_at is None
            assert token.expires_at - token.created_at == timedelta(hours=24)
            now = datetime.now(timezone.utc).replace(tzinfo=None)
            assert token.created_at <= now < token.expires_at

    class InspectingTransport(CapturingTransport):
        def send(self, message):
            # A separate session must see the committed, unused token before mail is sent.
            assert_pending_token(message)
            super().send(message)

    transport = InspectingTransport()
    app.dependency_overrides[_mail_transport] = lambda: transport
    # This test deliberately stops after signup and never calls verification.
    response = _signup(client)
    assert response.status_code == 202
    assert len(transport.messages) == 1
    message = transport.messages[0]
    plain = message.get_body(preferencelist=("plain",)).get_content()
    plain_url = next(line.split(": ", 1)[1] for line in plain.splitlines()
                     if line.startswith("Verify email address: "))
    html_links = EmailLinks()
    html_links.feed(message.get_body(preferencelist=("html",)).get_content())
    assert html_links.links == [plain_url]
    assert_pending_token(message)


def test_registration_validation_and_uniqueness(account_client):
    client, _factory, transport = account_client
    assert _signup(client).status_code == 202
    assert _signup(client, email=ADDRESS, username="second.reader").status_code == 409
    assert _signup(client, email="another@example.test", username="READER.ONE").status_code == 409
    assert _signup(client, email="not-an-email", username="valid.reader").status_code == 422
    assert _signup(client, email="another@example.test", username="---").status_code == 422
    weak = client.post("/api/v1/auth/signup", json={
        "fullName": "Weak Reader", "username": "weak.reader", "email": "weak@example.test",
        "password": "weakpasswordonly", "confirmPassword": "weakpasswordonly",
        "requestedRole": "AUDITOR",
    })
    assert weak.status_code == 422
    assert "weakpasswordonly" not in weak.text
    mismatch = client.post("/api/v1/auth/signup", json={
        "fullName": "Mismatch Reader", "username": "mismatch.reader", "email": "mismatch@example.test",
        "password": NEW_PASSWORD, "confirmPassword": RESET_PASSWORD,
        "requestedRole": "AUDITOR",
    })
    assert mismatch.status_code == 422
    assert NEW_PASSWORD not in mismatch.text
    assert RESET_PASSWORD not in mismatch.text
    assert len(transport.messages) == 1


def test_verification_login_rbac_and_logout(account_client, caplog):
    client, factory, transport = account_client
    assert _signup(client).status_code == 202
    token = _verify(client, transport)
    reused = client.post("/api/v1/auth/verify-email", json={"token": token})
    invalid = client.post("/api/v1/auth/verify-email", json={"token": "x" * 40})
    assert reused.status_code == invalid.status_code == 400
    assert reused.json() == invalid.json()
    assert "already used" in reused.json()["detail"]
    assert token not in caplog.text and NEW_PASSWORD not in caplog.text
    with factory() as session:
        user = session.scalar(select(UserModel).where(UserModel.email == ADDRESS))
        assert user.status == "ACTIVE" and user.is_active and user.email_verified_at is not None
        stored_token = session.scalar(select(AuthActionTokenModel).where(AuthActionTokenModel.user_id == user.id))
        assert stored_token.used_at is not None
    assert _login(client, "wrong-password").status_code == 401
    login = _login(client)
    assert login.status_code == 200
    payload = login.json()
    assert payload["user"]["username"] == "reader.one"
    assert payload["user"]["role"] == "AUDITOR"
    headers = {"Authorization": f"Bearer {payload['accessToken']}"}
    assert client.get("/api/v1/auth/me", headers=headers).status_code == 200
    assert client.get("/api/v1/documents", headers=headers).status_code == 200
    assert client.get("/api/v1/auth/users", headers=headers).status_code == 403
    assert client.post("/api/v1/auth/logout", headers=headers).status_code == 204
    assert client.get("/api/v1/auth/me", headers=headers).status_code == 401


def test_expired_verification_token_and_resend(account_client):
    client, factory, transport = account_client
    assert _signup(client).status_code == 202
    old_token = _mail_token(transport.messages[0], "verify-email")
    with factory() as session:
        token = session.scalar(select(AuthActionTokenModel))
        token.created_at = datetime.now(timezone.utc) - timedelta(hours=25)
        token.expires_at = datetime.now(timezone.utc) - timedelta(hours=1)
        session.commit()
    assert client.post("/api/v1/auth/verify-email", json={"token": old_token}).status_code == 400
    assert _login(client).status_code == 401
    with factory() as session:
        user = session.scalar(select(UserModel).where(UserModel.email == ADDRESS))
        assert user.status == "UNVERIFIED" and user.email_verified_at is None
    unknown = client.post("/api/v1/auth/resend-verification", json={"email": "nobody@example.test"})
    resend = client.post("/api/v1/auth/resend-verification", json={"email": ADDRESS})
    assert unknown.status_code == resend.status_code == 202
    assert unknown.json() == resend.json()
    assert len(transport.messages) == 2
    _verify(client, transport)


def test_signup_resend_and_reset_use_canonical_frontend_url(account_client, monkeypatch):
    client, factory, transport = account_client
    monkeypatch.setenv("VITE_APP_URL", "http://localhost:5173")
    monkeypatch.setenv("BHUDRISHTI_PUBLIC_APP_URL", "http://legacy.example.test")
    settings = app.dependency_overrides[get_settings]()
    settings.public_app_url = Settings(_env_file=None).public_app_url

    assert _signup(client).status_code == 202
    with factory() as session:
        token = session.scalar(select(AuthActionTokenModel))
        token.created_at = datetime.now(timezone.utc) - timedelta(minutes=2)
        session.commit()
    assert client.post("/api/v1/auth/resend-verification", json={"email": ADDRESS}).status_code == 202
    assert len(transport.messages) == 2
    _verify(client, transport)
    assert client.post("/api/v1/auth/forgot-password", json={"email": ADDRESS}).status_code == 202
    assert len(transport.messages) == 3
    for message, route in zip(transport.messages, ("verify-email", "verify-email", "reset-password")):
        body = message.get_body(preferencelist=("plain",)).get_content()
        assert f"http://localhost:5173/#/{route}?token=" in body
        assert "legacy.example.test" not in body
        assert _mail_token(message, route)


def test_forgot_reset_revokes_sessions_and_rejects_reuse(account_client):
    client, factory, transport = account_client
    assert _signup(client).status_code == 202
    _verify(client, transport)
    login = _login(client)
    assert login.status_code == 200
    headers = {"Authorization": f"Bearer {login.json()['accessToken']}"}
    unknown = client.post("/api/v1/auth/forgot-password", json={"email": "missing@example.test"})
    known = client.post("/api/v1/auth/forgot-password", json={"email": ADDRESS})
    assert known.status_code == unknown.status_code == 202
    assert known.json() == unknown.json()
    assert len(transport.messages) == 2
    raw_token = _mail_token(transport.messages[-1], "reset-password")
    with factory() as session:
        stored = session.scalar(select(AuthActionTokenModel).where(AuthActionTokenModel.purpose == "PASSWORD_RESET"))
        assert stored.token_hash != raw_token and len(stored.token_hash) == 64
    reset = client.post("/api/v1/auth/reset-password", json={
        "token": raw_token, "password": RESET_PASSWORD, "confirmPassword": RESET_PASSWORD,
    })
    assert reset.status_code == 200
    assert client.get("/api/v1/auth/me", headers=headers).status_code == 401
    assert _login(client).status_code == 401
    assert _login(client, RESET_PASSWORD).status_code == 200
    assert client.post("/api/v1/auth/reset-password", json={
        "token": raw_token, "password": NEW_PASSWORD, "confirmPassword": NEW_PASSWORD,
    }).status_code == 400
    assert client.post("/api/v1/auth/reset-password", json={
        "token": "x" * 40, "password": NEW_PASSWORD, "confirmPassword": NEW_PASSWORD,
    }).status_code == 400


def test_expired_reset_token_and_password_policy(account_client):
    client, factory, transport = account_client
    assert _signup(client).status_code == 202
    _verify(client, transport)
    assert client.post("/api/v1/auth/forgot-password", json={"email": ADDRESS}).status_code == 202
    raw_token = _mail_token(transport.messages[-1], "reset-password")
    with factory() as session:
        token = session.scalar(select(AuthActionTokenModel).where(AuthActionTokenModel.purpose == "PASSWORD_RESET"))
        token.expires_at = datetime.now(timezone.utc) - timedelta(seconds=1)
        session.commit()
    assert client.post("/api/v1/auth/reset-password", json={
        "token": raw_token, "password": RESET_PASSWORD, "confirmPassword": RESET_PASSWORD,
    }).status_code == 400
    assert client.post("/api/v1/auth/reset-password", json={
        "token": raw_token, "password": "weakpasswordonly", "confirmPassword": "weakpasswordonly",
    }).status_code == 422
    assert client.post("/api/v1/auth/reset-password", json={
        "token": raw_token, "password": RESET_PASSWORD, "confirmPassword": NEW_PASSWORD,
    }).status_code == 422
    assert _login(client).status_code == 200


def test_missing_smtp_configuration_and_delivery_failure_are_reported(account_client):
    client, factory, transport = account_client
    app.dependency_overrides.pop(_mail_transport)
    app.dependency_overrides[get_settings] = lambda: Settings(
        _env_file=None, environment="test",
        smtp_from="BhuDrishti AI <noreply@example.test>",
    )
    response = _signup(client)
    assert response.status_code == 503
    with factory() as session:
        assert session.scalar(select(UserModel).where(UserModel.email == ADDRESS)) is None

    class FailingTransport:
        def send(self, _message: EmailMessage) -> None:
            raise EmailDeliveryError("Test delivery failed")

    app.dependency_overrides[_mail_transport] = lambda: FailingTransport()
    response = _signup(client)
    assert response.status_code == 503
    with factory() as session:
        user = session.scalar(select(UserModel).where(UserModel.email == ADDRESS))
        assert user is not None and user.status == "UNVERIFIED"
        token = session.scalar(select(AuthActionTokenModel).where(AuthActionTokenModel.user_id == user.id))
        assert token.used_at is not None
    app.dependency_overrides[_mail_transport] = lambda: transport
    resend = client.post("/api/v1/auth/resend-verification", json={"email": ADDRESS})
    assert resend.status_code == 202
    assert len(transport.messages) == 1


def test_bad_email_link_configuration_returns_503_and_allows_resend(account_client):
    client, factory, transport = account_client
    settings = app.dependency_overrides[get_settings]()
    settings.public_app_url = "not-a-url"
    response = _signup(client)
    assert response.status_code == 503
    assert response.json()["detail"] == "Email delivery is not configured."
    assert not transport.messages
    with factory() as session:
        user = session.scalar(select(UserModel).where(UserModel.email == ADDRESS))
        assert user is not None and user.status == "UNVERIFIED"
        token = session.scalar(select(AuthActionTokenModel).where(AuthActionTokenModel.user_id == user.id))
        assert token.used_at is not None
    settings.public_app_url = "http://localhost:5173"
    resend = client.post("/api/v1/auth/resend-verification", json={"email": ADDRESS})
    assert resend.status_code == 202
    assert len(transport.messages) == 1


@pytest.mark.parametrize("code,detail", [
    ("SMTP_AUTHENTICATION_FAILED", "Email service authentication failed. Please contact the administrator."),
    ("SMTP_CONNECTION_FAILED", "The email service is temporarily unreachable. Please try again later."),
    ("SMTP_TLS_FAILED", "A secure email connection could not be established. Please contact the administrator."),
    ("EMAIL_DELIVERY_FAILED", "Email delivery failed. Please try again later."),
])
def test_signup_mail_error_response_and_logs_are_safe(account_client, caplog, code, detail):
    client, factory, _transport = account_client
    captured_tokens = []

    class FailingTransport:
        def send(self, message: EmailMessage) -> None:
            token = _mail_token(message, "verify-email")
            captured_tokens.append(token)
            raise EmailDeliveryError(
                f"private-smtp-response {ADDRESS} private-password {token}",
                code=code, stage="deliver", error_type="SMTPDataError", smtp_code=554,
            )

    app.dependency_overrides[_mail_transport] = lambda: FailingTransport()
    response = _signup(client)
    assert response.status_code == 503
    assert response.json() == {"detail": detail}
    assert response.headers["X-BhuDrishti-Error-Code"] == code
    assert f"code={code}" in caplog.text
    for private_value in ("private-smtp-response", ADDRESS, "private-password", captured_tokens[0]):
        assert private_value not in caplog.text
        assert private_value not in response.text
    assert all(record.exc_info is None for record in caplog.records)
    with factory() as session:
        user = session.scalar(select(UserModel).where(UserModel.email == ADDRESS))
        assert user.status == "UNVERIFIED" and not user.is_active
        token = session.scalar(select(AuthActionTokenModel).where(AuthActionTokenModel.user_id == user.id))
        assert token.used_at is not None


@pytest.mark.parametrize("code", [
    "SMTP_AUTHENTICATION_FAILED", "SMTP_CONNECTION_FAILED",
    "SMTP_TLS_FAILED", "EMAIL_DELIVERY_FAILED",
])
def test_password_recovery_connection_failure_does_not_reveal_account_existence(
    account_client, caplog, code,
):
    client, factory, transport = account_client
    assert _signup(client).status_code == 202
    _verify(client, transport)

    class FailingTransport:
        def verify_connection(self) -> None:
            raise EmailDeliveryError("transport-private-marker", code=code, stage="authenticate")

        def send(self, _message: EmailMessage) -> None:
            pytest.fail("Recovery must not issue mail after connection verification fails")

    app.dependency_overrides[_mail_transport] = lambda: FailingTransport()
    unknown = client.post("/api/v1/auth/forgot-password", json={"email": "missing@example.test"})
    known = client.post("/api/v1/auth/forgot-password", json={"email": ADDRESS})
    assert unknown.status_code == known.status_code == 503
    assert unknown.json() == known.json()
    assert unknown.headers["X-BhuDrishti-Error-Code"] == known.headers["X-BhuDrishti-Error-Code"] == code
    with factory() as session:
        user = session.scalar(select(UserModel).where(UserModel.email == ADDRESS))
        token = session.scalar(select(AuthActionTokenModel).where(
            AuthActionTokenModel.user_id == user.id,
            AuthActionTokenModel.purpose == "PASSWORD_RESET",
        ))
        assert token is None
    assert "transport-private-marker" not in caplog.text
    assert ADDRESS not in caplog.text
    assert ADDRESS not in known.text and "missing@example.test" not in unknown.text


@pytest.mark.parametrize("code", [
    "SMTP_AUTHENTICATION_FAILED", "SMTP_CONNECTION_FAILED",
    "SMTP_TLS_FAILED", "EMAIL_DELIVERY_FAILED",
])
def test_password_recovery_send_failure_is_reported_and_allows_retry(
    account_client, caplog, code,
):
    client, factory, transport = account_client
    caplog.set_level("INFO", logger="app.api.routes.auth")
    assert _signup(client).status_code == 202
    _verify(client, transport)
    caplog.clear()
    captured_tokens = []

    class FailingTransport:
        def verify_connection(self) -> None:
            pass

        def send(self, message: EmailMessage) -> None:
            token = _mail_token(message, "reset-password")
            captured_tokens.append(token)
            raise EmailDeliveryError(
                f"transport-private-marker {ADDRESS} private-password {token}",
                code=code, stage="deliver", error_type="SMTPDataError", smtp_code=554,
            )

    app.dependency_overrides[_mail_transport] = lambda: FailingTransport()
    response = client.post("/api/v1/auth/forgot-password", json={"email": ADDRESS})
    assert response.status_code == 503
    assert response.headers["X-BhuDrishti-Error-Code"] == code
    assert set(response.json()) == {"detail"}
    assert "outcome=transport_accepted" not in caplog.text
    for private_value in ("transport-private-marker", ADDRESS, "private-password", captured_tokens[0]):
        assert private_value not in response.text
        assert private_value not in caplog.text
    assert all(record.exc_info is None for record in caplog.records)
    with factory() as session:
        user = session.scalar(select(UserModel).where(UserModel.email == ADDRESS))
        assert user.status == "ACTIVE" and user.email_verified_at is not None
        token = session.scalar(select(AuthActionTokenModel).where(
            AuthActionTokenModel.user_id == user.id,
            AuthActionTokenModel.purpose == "PASSWORD_RESET",
        ))
        assert token.used_at is not None
    assert client.post("/api/v1/auth/reset-password", json={
        "token": captured_tokens[0], "password": RESET_PASSWORD, "confirmPassword": RESET_PASSWORD,
    }).status_code == 400
    assert _login(client).status_code == 200

    app.dependency_overrides[_mail_transport] = lambda: transport
    retry = client.post("/api/v1/auth/forgot-password", json={"email": ADDRESS})
    assert retry.status_code == 202
    assert transport.connection_checks == 1
    assert "Password recovery email submitted: outcome=transport_accepted" in caplog.text
    assert len(transport.messages) == 2
    retry_token = _mail_token(transport.messages[-1], "reset-password")
    assert retry_token != captured_tokens[0]
    with factory() as session:
        stored = session.scalar(select(AuthActionTokenModel).where(
            AuthActionTokenModel.token_hash == sha256(retry_token.encode("utf-8")).hexdigest(),
        ))
        assert stored.used_at is None


def test_password_recovery_ineligible_and_cooldown_requests_have_generic_response(
    account_client, caplog,
):
    client, factory, transport = account_client
    caplog.set_level("INFO", logger="app.api.routes.auth")
    assert _signup(client).status_code == 202
    unknown = client.post("/api/v1/auth/forgot-password", json={"email": "missing@example.test"})
    unverified = client.post("/api/v1/auth/forgot-password", json={"email": ADDRESS})
    assert len(transport.messages) == 1
    with factory() as session:
        assert not session.scalars(select(AuthActionTokenModel).where(
            AuthActionTokenModel.purpose == "PASSWORD_RESET",
        )).all()
    _verify(client, transport)
    eligible = client.post("/api/v1/auth/forgot-password", json={"email": ADDRESS})
    cooldown = client.post("/api/v1/auth/forgot-password", json={"email": ADDRESS})
    with factory() as session:
        user = session.scalar(select(UserModel).where(UserModel.email == ADDRESS))
        user.status = "SUSPENDED"
        user.is_active = False
        session.commit()
    suspended = client.post("/api/v1/auth/forgot-password", json={"email": ADDRESS})
    responses = (unknown, unverified, eligible, cooldown, suspended)
    assert all(response.status_code == 202 for response in responses)
    assert all(response.json() == unknown.json() for response in responses)
    assert len(transport.messages) == 2
    assert transport.connection_checks == len(responses)
    assert "Password recovery email skipped: reason=account_not_eligible" in caplog.text
    assert "Password recovery email skipped: reason=request_cooldown" in caplog.text
    assert ADDRESS not in caplog.text and "missing@example.test" not in caplog.text


def test_password_recovery_missing_configuration_is_uniform_and_creates_no_reset_token(account_client):
    client, factory, transport = account_client
    assert _signup(client).status_code == 202
    _verify(client, transport)
    app.dependency_overrides.pop(_mail_transport)
    app.dependency_overrides[get_settings] = lambda: Settings(
        _env_file=None, environment="test",
        smtp_from="BhuDrishti AI <noreply@example.test>",
    )
    unknown = client.post("/api/v1/auth/forgot-password", json={"email": "missing@example.test"})
    known = client.post("/api/v1/auth/forgot-password", json={"email": ADDRESS})
    assert known.status_code == unknown.status_code == 503
    assert known.json() == unknown.json() == {"detail": "Email delivery is not configured."}
    assert known.headers["X-BhuDrishti-Error-Code"] == "EMAIL_NOT_CONFIGURED"
    with factory() as session:
        assert not session.scalars(select(AuthActionTokenModel).where(
            AuthActionTokenModel.purpose == "PASSWORD_RESET",
        )).all()


@pytest.mark.parametrize("code", [
    "SMTP_AUTHENTICATION_FAILED", "SMTP_CONNECTION_FAILED",
    "SMTP_TLS_FAILED", "EMAIL_DELIVERY_FAILED",
])
def test_resend_mail_failure_is_reported_and_retry_keeps_account_unverified(
    account_client, caplog, code,
):
    client, factory, transport = account_client
    caplog.set_level("INFO", logger="app.api.routes.auth")
    assert _signup(client).status_code == 202
    with factory() as session:
        original_token = session.scalar(select(AuthActionTokenModel))
        original_token.created_at = datetime.now(timezone.utc) - timedelta(minutes=2)
        original_token_id = original_token.id
        session.commit()

    caplog.clear()
    captured_tokens = []

    class FailingTransport:
        def send(self, message: EmailMessage) -> None:
            token = _mail_token(message, "verify-email")
            captured_tokens.append(token)
            raise EmailDeliveryError(
                f"transport-private-marker {ADDRESS} private-password {token}",
                code=code, stage="deliver", error_type="SMTPDataError", smtp_code=554,
            )

    app.dependency_overrides[_mail_transport] = lambda: FailingTransport()
    response = client.post("/api/v1/auth/resend-verification", json={"email": ADDRESS})
    assert response.status_code == 503
    assert response.headers["X-BhuDrishti-Error-Code"] == code
    assert set(response.json()) == {"detail"}
    assert len(captured_tokens) == 1
    assert "outcome=transport_accepted" not in caplog.text
    for private_value in ("transport-private-marker", ADDRESS, "private-password", captured_tokens[0]):
        assert private_value not in response.text
        assert private_value not in caplog.text
    assert all(record.exc_info is None for record in caplog.records)
    with factory() as session:
        user = session.scalar(select(UserModel).where(UserModel.email == ADDRESS))
        assert user.status == "UNVERIFIED" and not user.is_active
        assert user.email_verified_at is None
        tokens = session.scalars(select(AuthActionTokenModel).where(
            AuthActionTokenModel.user_id == user.id,
        )).all()
        assert len(tokens) == 2
        failed_token = next(token for token in tokens if token.id != original_token_id)
        assert failed_token.token_hash == sha256(captured_tokens[0].encode("utf-8")).hexdigest()
        assert failed_token.used_at is not None
        assert session.get(AuthActionTokenModel, original_token_id).used_at is None
    assert _login(client).status_code == 401
    assert client.post("/api/v1/auth/verify-email", json={"token": captured_tokens[0]}).status_code == 400

    # A failed send does not impose the resend cooldown or activate the account.
    app.dependency_overrides[_mail_transport] = lambda: transport
    retry = client.post("/api/v1/auth/resend-verification", json={"email": ADDRESS})
    assert retry.status_code == 202
    assert "Verification email resend submitted: outcome=transport_accepted" in caplog.text
    assert len(transport.messages) == 2
    retry_token = _mail_token(transport.messages[-1], "verify-email")
    assert retry_token != captured_tokens[0]
    with factory() as session:
        user = session.scalar(select(UserModel).where(UserModel.email == ADDRESS))
        assert user.status == "UNVERIFIED" and not user.is_active
        assert user.email_verified_at is None
        token = session.scalar(select(AuthActionTokenModel).where(
            AuthActionTokenModel.token_hash == sha256(retry_token.encode("utf-8")).hexdigest(),
        ))
        assert token.used_at is None


def test_resend_ineligible_accounts_keep_generic_response_without_sending(account_client, caplog):
    client, _factory, transport = account_client
    caplog.set_level("INFO", logger="app.api.routes.auth")
    assert _signup(client).status_code == 202
    caplog.clear()

    class UnexpectedTransport:
        def send(self, _message: EmailMessage) -> None:
            pytest.fail("Resend must not send to an ineligible account")

    app.dependency_overrides[_mail_transport] = lambda: UnexpectedTransport()
    unknown = client.post("/api/v1/auth/resend-verification", json={"email": "missing@example.test"})
    throttled = client.post("/api/v1/auth/resend-verification", json={"email": ADDRESS})
    _verify(client, transport)
    verified = client.post("/api/v1/auth/resend-verification", json={"email": ADDRESS})
    assert unknown.status_code == throttled.status_code == verified.status_code == 202
    assert unknown.json() == throttled.json() == verified.json()
    reasons = [record.getMessage() for record in caplog.records if record.name == "app.api.routes.auth"]
    assert reasons == [
        "Verification email resend skipped: reason=account_not_eligible",
        "Verification email resend skipped: reason=request_cooldown",
        "Verification email resend skipped: reason=account_not_eligible",
    ]
    assert ADDRESS not in caplog.text and "missing@example.test" not in caplog.text


@pytest.mark.parametrize("role,can_process,can_review,can_decide,can_recommend", [
    ("REVENUE_OFFICER", True, True, True, False),
    ("VERIFIER", False, True, False, True),
    ("AUDITOR", False, False, False, False),
])
def test_selected_role_is_stored_and_enforced_after_email_verification(
    account_client, role, can_process, can_review, can_decide, can_recommend,
):
    client, factory, transport = account_client
    signup = _signup(client, requested_role=role)
    assert signup.status_code == 202
    assert signup.json()["role"] == role
    assert signup.json()["requestedRole"] == role
    assert signup.json()["roleApprovalStatus"] is None
    with factory() as session:
        user = session.scalar(select(UserModel).where(UserModel.email == ADDRESS))
        assert user.role == role and user.requested_role == role
        assert user.role_approval_status is None
        assert user.status == "UNVERIFIED"
    assert _login(client).status_code == 401
    _verify(client, transport)
    login = _login(client)
    assert login.status_code == 200
    assert login.json()["user"]["role"] == role
    headers = {"Authorization": f"Bearer {login.json()['accessToken']}"}
    assert client.get("/api/v1/auth/me", headers=headers).json()["role"] == role
    assert client.get("/api/v1/documents", headers=headers).status_code == 200
    assert client.post("/api/v1/documents/missing/process", headers=headers).status_code == (
        404 if can_process else 403
    )
    assert client.post("/api/v1/reviews/missing/start", headers=headers).status_code == (
        404 if can_review else 403
    )
    assert client.post(
        "/api/v1/reviews/missing/decision", headers=headers, json={"decision": "approve"},
    ).status_code == (404 if can_decide else 403)
    assert client.post(
        "/api/v1/reviews/missing/recommendation", headers=headers,
        json={"recommendation": "approve", "reason": "Test recommendation"},
    ).status_code == (404 if can_recommend else 403)
    assert client.get("/api/v1/auth/admin-requests", headers=headers).status_code == 403


def test_admin_request_stays_restricted_until_verified_and_approved(account_client):
    client, factory, transport = account_client
    with factory() as session:
        admin = create_user(
            session, email="existing.admin@example.test", name="Existing Administrator",
            password=NEW_PASSWORD, role=Role.ADMIN,
        )
        admin_id = admin.id
        session.commit()
    admin_login = client.post("/api/v1/auth/login", json={
        "email": "existing.admin@example.test", "password": NEW_PASSWORD,
    })
    assert admin_login.status_code == 200
    admin_headers = {"Authorization": f"Bearer {admin_login.json()['accessToken']}"}

    signup = _signup(client, requested_role="ADMIN")
    assert signup.status_code == 202
    assert signup.json()["role"] == "AUDITOR"
    assert signup.json()["requestedRole"] == "ADMIN"
    assert signup.json()["roleApprovalStatus"] == "PENDING"
    with factory() as session:
        requested_user = session.scalar(select(UserModel).where(UserModel.email == ADDRESS))
        request_id = requested_user.id
        assert requested_user.role == "AUDITOR"
        assert requested_user.role_approval_status == "PENDING"
        assert requested_user.status == "UNVERIFIED"
    requests = client.get("/api/v1/auth/admin-requests", headers=admin_headers)
    assert requests.status_code == 200
    assert requests.json()[0]["user"]["id"] == request_id
    assert requests.json()[0]["emailVerified"] is False
    assert client.post(
        f"/api/v1/auth/admin-requests/{request_id}/approve", headers=admin_headers,
    ).status_code == 409
    assert _login(client).status_code == 401

    _verify(client, transport)
    pending_login = _login(client)
    assert pending_login.status_code == 200
    assert pending_login.json()["user"]["role"] == "AUDITOR"
    assert pending_login.json()["user"]["roleApprovalStatus"] == "PENDING"
    pending_headers = {"Authorization": f"Bearer {pending_login.json()['accessToken']}"}
    assert client.get("/api/v1/auth/users", headers=pending_headers).status_code == 403
    assert client.post(
        f"/api/v1/auth/admin-requests/{request_id}/approve", headers=pending_headers,
    ).status_code == 403
    assert client.post("/api/v1/documents/missing/process", headers=pending_headers).status_code == 403

    approved = client.post(
        f"/api/v1/auth/admin-requests/{request_id}/approve", headers=admin_headers,
    )
    assert approved.status_code == 200
    assert approved.json()["role"] == "ADMIN"
    assert approved.json()["roleApprovalStatus"] == "APPROVED"
    with factory() as session:
        requested_user = session.get(UserModel, request_id)
        assert requested_user.role == "ADMIN"
        assert requested_user.role_reviewed_by == admin_id
        assert requested_user.role_reviewed_at is not None
    # Existing bearer sessions resolve the current database role every request.
    assert client.get("/api/v1/auth/me", headers=pending_headers).json()["role"] == "ADMIN"
    assert client.get("/api/v1/auth/users", headers=pending_headers).status_code == 200
    assert client.post(
        f"/api/v1/auth/admin-requests/{request_id}/approve", headers=admin_headers,
    ).status_code == 404


def test_admin_request_rejection_retains_auditor_role(account_client):
    client, factory, transport = account_client
    with factory() as session:
        create_user(
            session, email="existing.admin@example.test", name="Existing Administrator",
            password=NEW_PASSWORD, role=Role.ADMIN,
        )
        session.commit()
    admin_login = client.post("/api/v1/auth/login", json={
        "email": "existing.admin@example.test", "password": NEW_PASSWORD,
    })
    admin_headers = {"Authorization": f"Bearer {admin_login.json()['accessToken']}"}
    assert _signup(client, requested_role="ADMIN").status_code == 202
    _verify(client, transport)
    pending_login = _login(client)
    pending_headers = {"Authorization": f"Bearer {pending_login.json()['accessToken']}"}
    with factory() as session:
        request_id = session.scalar(select(UserModel.id).where(UserModel.email == ADDRESS))
    rejected = client.post(
        f"/api/v1/auth/admin-requests/{request_id}/reject", headers=admin_headers,
    )
    assert rejected.status_code == 200
    assert rejected.json()["role"] == "AUDITOR"
    assert rejected.json()["roleApprovalStatus"] == "REJECTED"
    assert client.get("/api/v1/auth/me", headers=pending_headers).json()["role"] == "AUDITOR"
    assert client.get("/api/v1/auth/users", headers=pending_headers).status_code == 403
    assert client.post(
        f"/api/v1/auth/admin-requests/{request_id}/approve", headers=admin_headers,
    ).status_code == 404


def test_signup_rejects_role_tampering_and_unsupported_roles(account_client):
    client, factory, transport = account_client
    signup_body = {
        "fullName": "Example Reader", "username": "reader.one", "email": ADDRESS,
        "password": NEW_PASSWORD, "confirmPassword": NEW_PASSWORD,
    }
    for changes in (
        {},
        {"requestedRole": "SUPERUSER"},
        {"requestedRole": "AUDITOR", "role": "ADMIN"},
        {"requestedRole": "ADMIN", "roleApprovalStatus": "APPROVED"},
    ):
        response = client.post("/api/v1/auth/signup", json={**signup_body, **changes})
        assert response.status_code == 422
    with factory() as session:
        assert session.scalar(select(UserModel).where(UserModel.email == ADDRESS)) is None
    assert not transport.messages
