"""Account mail uses real TLS-capable SMTP and an injectable test transport."""

from __future__ import annotations

from email.message import EmailMessage
import smtplib
import ssl

import pytest

from app.config import Settings
from app.services.email import (
    EmailConfigurationError,
    EmailDeliveryError,
    SmtpMailTransport,
    send_password_reset_email,
    send_verification_email,
)


class RecordingTransport:
    def __init__(self) -> None:
        self.messages: list[EmailMessage] = []

    def send(self, message: EmailMessage) -> None:
        self.messages.append(message)


def _settings(**overrides) -> Settings:
    return Settings(
        _env_file=None,
        environment="test",
        smtp_host="smtp.example.test",
        smtp_from="BhuDrishti AI <noreply@example.test>",
        **overrides,
    )


def test_plain_smtp_environment_variable_names_are_supported(monkeypatch) -> None:
    monkeypatch.setenv("SMTP_HOST", "smtp.example.test")
    monkeypatch.setenv("SMTP_PORT", "465")
    monkeypatch.setenv("SMTP_SECURE", "true")
    monkeypatch.setenv("SMTP_USER", "mailer@example.test")
    monkeypatch.setenv("SMTP_PASS", "test-only-secret")
    monkeypatch.setenv("SMTP_FROM", "BhuDrishti AI <noreply@example.test>")
    settings = Settings(_env_file=None)
    assert settings.smtp_host == "smtp.example.test"
    assert settings.smtp_port == 465
    assert settings.smtp_secure is True
    assert settings.smtp_user == "mailer@example.test"
    assert settings.smtp_from == "BhuDrishti AI <noreply@example.test>"
    assert "test-only-secret" not in repr(settings)


def test_verification_and_reset_messages_are_multipart_and_distinct() -> None:
    transport = RecordingTransport()
    settings = _settings()
    send_verification_email(
        recipient_email="person@example.test",
        verification_url="https://app.example.test/#/verify-email?token=example-token",
        settings=settings,
        transport=transport,
        expires_minutes=45,
    )
    send_password_reset_email(
        recipient_email="person@example.test",
        reset_url="https://app.example.test/#/reset-password?token=another-token",
        settings=settings,
        transport=transport,
        expires_minutes=20,
    )
    assert len(transport.messages) == 2
    verification, reset = transport.messages
    assert verification["Subject"] == "Verify your BhuDrishti AI email"
    assert reset["Subject"] == "Reset your BhuDrishti AI password"
    assert verification["To"] == reset["To"] == "person@example.test"
    assert "45 minutes" in verification.get_body(preferencelist=("plain",)).get_content()
    assert "20 minutes" in reset.get_body(preferencelist=("html",)).get_content()
    assert "Verify email address" in verification.get_body(preferencelist=("html",)).get_content()
    assert "Reset password" in reset.get_body(preferencelist=("plain",)).get_content()


def test_missing_smtp_configuration_fails_without_faking_delivery() -> None:
    settings = Settings(_env_file=None, smtp_host=None, smtp_from=None)
    with pytest.raises(EmailConfigurationError, match="SMTP_HOST"):
        SmtpMailTransport(settings)
    with pytest.raises(EmailConfigurationError, match="SMTP_FROM"):
        send_verification_email(
            recipient_email="person@example.test",
            verification_url="https://app.example.test/#/verify-email?token=example-token",
            settings=settings,
        )
    with pytest.raises(EmailConfigurationError, match="SMTP_USER and SMTP_PASS"):
        SmtpMailTransport(_settings(smtp_user="mailer@example.test"))


@pytest.mark.parametrize("url", [
    "not-a-url", "ftp://app.example.test", "https://app.example.test/?mode=reset",
    "https://app.example.test/#/login", "https://user@app.example.test", "https://app.example.test:bad",
])
def test_public_app_url_rejects_broken_account_links(url: str) -> None:
    with pytest.raises(ValueError, match="VITE_APP_URL"):
        _settings(public_app_url=url)


def test_frontend_url_uses_canonical_environment_and_legacy_fallback(monkeypatch) -> None:
    monkeypatch.delenv("VITE_APP_URL", raising=False)
    monkeypatch.delenv("BHUDRISHTI_PUBLIC_APP_URL", raising=False)
    assert Settings(_env_file=None).public_app_url == "http://localhost:5173"
    monkeypatch.setenv("BHUDRISHTI_PUBLIC_APP_URL", "http://localhost:5174")
    assert Settings(_env_file=None).public_app_url == "http://localhost:5174"
    monkeypatch.setenv("VITE_APP_URL", "https://app.example.test/")
    assert Settings(_env_file=None).public_app_url == "https://app.example.test"
    assert Settings(_env_file=None, public_app_url="https://explicit.example.test").public_app_url == "https://explicit.example.test"


@pytest.mark.parametrize("variable", ["VITE_APP_URL", "BHUDRISHTI_PUBLIC_APP_URL"])
def test_process_url_override_wins_over_shared_dotenv(monkeypatch, tmp_path, variable) -> None:
    dotenv = tmp_path / ".env"
    dotenv.write_text("VITE_APP_URL=http://localhost:5173\n", encoding="utf-8")
    monkeypatch.delenv("VITE_APP_URL", raising=False)
    monkeypatch.delenv("BHUDRISHTI_PUBLIC_APP_URL", raising=False)
    monkeypatch.setenv(variable, "http://localhost:5174")
    assert Settings(_env_file=dotenv).public_app_url == "http://localhost:5174"


def test_shared_url_is_read_independently_of_working_directory(monkeypatch, tmp_path) -> None:
    monkeypatch.delenv("VITE_APP_URL", raising=False)
    monkeypatch.delenv("BHUDRISHTI_PUBLIC_APP_URL", raising=False)
    backend_env = tmp_path / "backend.env"
    shared_env = tmp_path / "shared.env"
    backend_env.write_text("BHUDRISHTI_PUBLIC_APP_URL=http://old.example.test\n", encoding="utf-8")
    shared_env.write_text("VITE_APP_URL=http://localhost:5173\n", encoding="utf-8")
    monkeypatch.setitem(Settings.model_config, "env_file", (backend_env, shared_env))
    unrelated = tmp_path / "unrelated-shell-directory"
    unrelated.mkdir()
    monkeypatch.chdir(unrelated)
    assert Settings().public_app_url == "http://localhost:5173"


def test_invalid_action_url_reports_email_configuration_error() -> None:
    with pytest.raises(EmailConfigurationError, match="Account email link"):
        send_verification_email(
            recipient_email="person@example.test",
            verification_url="not-a-url/#/verify-email?token=test-only",
            settings=_settings(),
            transport=RecordingTransport(),
        )


@pytest.mark.parametrize("recipient", [
    "foo<bar@example.test>", "(alias)bar@example.test", "bar@example.test,",
    "bar@example.test,other@example.test", "bar@example.test\r\nBcc:other@example.test",
])
def test_mail_service_rejects_recipient_headers_before_transport_submission(recipient) -> None:
    transport = RecordingTransport()
    with pytest.raises(EmailConfigurationError, match="Recipient email"):
        send_verification_email(
            recipient_email=recipient,
            verification_url="https://app.example.test/#/verify-email?token=test-only",
            settings=_settings(), transport=transport,
        )
    assert transport.messages == []


@pytest.mark.parametrize("sender", [
    "bad-address", "noreply@example.test,other@example.test", "noreply@example.test,",
    "noreply@example.test\r\nBcc:other@example.test", "Brand <noreply@example.test",
])
def test_smtp_sender_requires_one_unambiguous_mailbox(sender) -> None:
    with pytest.raises(EmailConfigurationError, match="SMTP_FROM"):
        SmtpMailTransport(Settings(_env_file=None, smtp_host="smtp.example.test", smtp_from=sender))


def test_mail_service_uses_normalized_exact_recipient_and_branded_sender() -> None:
    transport = RecordingTransport()
    send_verification_email(
        recipient_email=" Person+QA@Example.TEST ",
        verification_url="https://app.example.test/#/verify-email?token=test-only",
        settings=_settings(), transport=transport,
    )
    message = transport.messages[0]
    assert message["To"].addresses[0].addr_spec == "person+qa@example.test"
    assert len(message["To"].addresses) == 1
    assert message["From"].addresses[0].display_name == "BhuDrishti AI"


@pytest.mark.parametrize("url", [
    "http://localhost:5173", "https://localhost", "https://qa.localhost",
    "https://127.0.0.1:5173", "https://[::1]:5173", "http://app.example.test",
])
def test_deployed_email_links_fail_closed_for_local_or_insecure_frontend_urls(url) -> None:
    with pytest.raises(ValueError, match="deployed HTTPS frontend URL"):
        Settings(_env_file=None, environment="production", auth_secret="test-only-auth-secret-of-sufficient-length", public_app_url=url)


def test_deployed_email_links_accept_explicit_https_public_frontend_url() -> None:
    settings = Settings(
        _env_file=None, environment="production", auth_secret="test-only-auth-secret-of-sufficient-length",
        public_app_url="https://app.example.test/portal/",
    )
    assert settings.public_app_url == "https://app.example.test/portal"


def test_settings_startup_validation_does_not_print_private_configuration() -> None:
    with pytest.raises(ValueError) as caught:
        Settings(
            _env_file=None, environment="production", auth_secret="private-auth-secret-that-is-long-enough",
            public_app_url="http://localhost:5173", smtp_user="private-mailer@example.test",
            smtp_pass="private-smtp-password", smtp_from="private-mailer@example.test",
        )
    assert "deployed HTTPS frontend URL" in str(caught.value)
    for private_value in (
        "private-smtp-password", "private-mailer@example.test", "private-auth-secret-that-is-long-enough",
    ):
        assert private_value not in str(caught.value)


def test_smtp_requires_starttls_before_login_or_delivery(monkeypatch, caplog) -> None:
    events: list[str] = []
    caplog.set_level("INFO", logger="app.services.email.service")

    class FakeSMTP:
        def __init__(self, *_args, **_kwargs):
            events.append("connect")

        def __enter__(self):
            return self

        def __exit__(self, *_args):
            return None

        def ehlo(self):
            events.append("ehlo")

        def starttls(self, **_kwargs):
            events.append("starttls")

        def login(self, _user, _password):
            events.append("login")

        def send_message(self, _message):
            events.append("send")
            return {}

    monkeypatch.setattr(smtplib, "SMTP", FakeSMTP)
    send_password_reset_email(
        recipient_email="person@example.test",
        reset_url="https://app.example.test/#/reset-password?token=example-token",
        settings=_settings(smtp_user="mailer@example.test", smtp_pass="test-only-secret"),
    )
    assert events == ["connect", "ehlo", "starttls", "ehlo", "login", "send"]
    assert "code=SMTP_CONNECTION_VERIFIED stage=authenticate" in caplog.text
    assert "code=EMAIL_SUBMITTED stage=deliver" in caplog.text
    for private_value in ("mailer@example.test", "person@example.test", "test-only-secret", "example-token"):
        assert private_value not in caplog.text


def test_smtp_secure_uses_implicit_tls(monkeypatch, caplog) -> None:
    events: list[str] = []
    caplog.set_level("INFO", logger="app.services.email.service")

    class FakeSMTPSSL:
        def __init__(self, *_args, **_kwargs):
            events.append("ssl-connect")

        def __enter__(self):
            return self

        def __exit__(self, *_args):
            return None

        def send_message(self, _message):
            events.append("send")
            return {}

    monkeypatch.setattr(smtplib, "SMTP_SSL", FakeSMTPSSL)
    send_verification_email(
        recipient_email="person@example.test",
        verification_url="https://app.example.test/#/verify-email?token=example-token",
        settings=_settings(smtp_secure=True),
    )
    assert events == ["ssl-connect", "send"]
    assert "code=SMTP_CONNECTION_VERIFIED stage=authenticate" in caplog.text
    assert "code=EMAIL_SUBMITTED stage=deliver" in caplog.text


def test_smtp_tls_failure_is_a_delivery_error(monkeypatch) -> None:
    class NoTLS:
        def __init__(self, *_args, **_kwargs):
            pass

        def __enter__(self):
            return self

        def __exit__(self, *_args):
            return None

        def ehlo(self):
            pass

        def starttls(self, **_kwargs):
            raise smtplib.SMTPNotSupportedError("not available")

        def send_message(self, _message):
            pytest.fail("The message must not be sent without TLS")

    monkeypatch.setattr(smtplib, "SMTP", NoTLS)
    with pytest.raises(EmailDeliveryError, match="STARTTLS"):
        send_verification_email(
            recipient_email="person@example.test",
            verification_url="https://app.example.test/#/verify-email?token=example-token",
            settings=_settings(),
        )


@pytest.mark.parametrize("secure", [False, True])
def test_smtp_connection_probe_checks_tls_and_auth_without_sending(monkeypatch, caplog, secure: bool) -> None:
    events: list[str] = []
    caplog.set_level("INFO", logger="app.services.email.service")

    class FakeSMTP:
        def __init__(self, *_args, **kwargs):
            assert kwargs["timeout"] == 3
            events.append("connect")

        def __enter__(self):
            return self

        def __exit__(self, *_args):
            return None

        def ehlo(self):
            events.append("ehlo")

        def starttls(self, **_kwargs):
            events.append("starttls")

        def login(self, _user, _password):
            events.append("login")

        def send_message(self, _message):
            pytest.fail("Connection checks must never send email")

    monkeypatch.setattr(smtplib, "SMTP_SSL" if secure else "SMTP", FakeSMTP)
    SmtpMailTransport(_settings(
        smtp_secure=secure,
        smtp_user="mailer@example.test",
        smtp_pass="test-only-secret",
    )).verify_connection(timeout=3)
    assert events == (["connect", "ehlo", "login"] if secure else
                      ["connect", "ehlo", "starttls", "ehlo", "login"])
    assert "code=SMTP_CONNECTION_VERIFIED stage=authenticate" in caplog.text
    assert "EMAIL_SUBMITTED" not in caplog.text


def test_smtp_connection_probe_sanitizes_server_rejection(monkeypatch) -> None:
    class RejectedSMTP:
        def __init__(self, *_args, **_kwargs):
            pass

        def __enter__(self):
            return self

        def __exit__(self, *_args):
            return None

        def ehlo(self):
            pass

        def starttls(self, **_kwargs):
            raise smtplib.SMTPResponseException(535, b"account and secret in server response")

    monkeypatch.setattr(smtplib, "SMTP", RejectedSMTP)
    with pytest.raises(EmailDeliveryError) as error:
        SmtpMailTransport(_settings()).verify_connection()
    assert str(error.value) == "SMTP connection check failed."


@pytest.mark.parametrize("stage,error,code,error_type,smtp_code,os_errno", [
    ("connect", PermissionError(13, "private-server-response"), "SMTP_CONNECTION_FAILED", "PermissionError", None, 13),
    ("connect", ConnectionRefusedError(111, "private-server-response"), "SMTP_CONNECTION_FAILED", "ConnectionRefusedError", None, 111),
    ("connect", TimeoutError("private-server-response"), "SMTP_CONNECTION_FAILED", "TimeoutError", None, None),
    ("tls", smtplib.SMTPNotSupportedError("private-server-response"), "SMTP_TLS_FAILED", "SMTPNotSupportedError", None, None),
    ("tls", ssl.SSLError(1, "private-server-response"), "SMTP_TLS_FAILED", "SSLError", None, 1),
    ("authenticate", smtplib.SMTPAuthenticationError(535, b"private-server-response"), "SMTP_AUTHENTICATION_FAILED", "SMTPAuthenticationError", 535, None),
    ("deliver", smtplib.SMTPDataError(554, b"private-server-response"), "EMAIL_DELIVERY_FAILED", "SMTPDataError", 554, None),
    ("deliver", smtplib.SMTPSenderRefused(553, b"private-server-response", "private-sender@example.test"), "EMAIL_DELIVERY_FAILED", "SMTPSenderRefused", 553, None),
    ("deliver", smtplib.SMTPRecipientsRefused({"secret@example.test": (550, b"private-server-response")}), "EMAIL_DELIVERY_FAILED", "SMTPRecipientsRefused", 550, None),
])
def test_smtp_failures_preserve_safe_diagnostics_without_server_text(
    monkeypatch, caplog, stage, error, code, error_type, smtp_code, os_errno,
) -> None:
    class FailingSMTP:
        def __init__(self, *_args, **_kwargs):
            if stage == "connect":
                raise error

        def __enter__(self):
            return self

        def __exit__(self, *_args):
            return None

        def ehlo(self):
            pass

        def starttls(self, **_kwargs):
            if stage == "tls":
                raise error

        def login(self, _user, _password):
            if stage == "authenticate":
                raise error

        def send_message(self, _message):
            if stage == "deliver":
                raise error

    monkeypatch.setattr(smtplib, "SMTP", FailingSMTP)
    with pytest.raises(EmailDeliveryError) as caught:
        send_verification_email(
            recipient_email="secret@example.test",
            verification_url="https://app.example.test/#/verify-email?token=private-email-token",
            settings=_settings(smtp_user="private-user@example.test", smtp_pass="private-password"),
        )
    failure = caught.value
    assert failure.code == code
    assert failure.stage == stage
    assert failure.error_type == error_type
    assert failure.smtp_code == smtp_code
    assert failure.os_errno == os_errno
    assert f"code={code} stage={stage} error_type={error_type}" in caplog.text
    assert f"smtp_code={smtp_code} os_errno={os_errno}" in caplog.text
    for secret in (
        "private-server-response", "secret@example.test", "private-user@example.test",
        "private-password", "private-email-token", "private-sender@example.test",
    ):
        assert secret not in caplog.text
        assert secret not in str(failure)
    assert all(record.exc_info is None for record in caplog.records)


@pytest.mark.parametrize("secure", [False, True])
def test_smtp_returned_recipient_refusal_never_reports_submission_success(monkeypatch, caplog, secure) -> None:
    caplog.set_level("INFO", logger="app.services.email.service")

    class RefusingSMTP:
        def __init__(self, *_args, **_kwargs):
            pass

        def __enter__(self):
            return self

        def __exit__(self, *_args):
            return None

        def ehlo(self):
            pass

        def starttls(self, **_kwargs):
            pass

        def send_message(self, _message):
            return {"private-recipient@example.test": (550, b"private-server-response")}

    monkeypatch.setattr(smtplib, "SMTP_SSL" if secure else "SMTP", RefusingSMTP)
    with pytest.raises(EmailDeliveryError) as caught:
        send_verification_email(
            recipient_email="private-recipient@example.test",
            verification_url="https://app.example.test/#/verify-email?token=private-token",
            settings=_settings(smtp_secure=secure),
        )
    assert caught.value.error_type == "SMTPRecipientsRefused"
    assert caught.value.smtp_code == 550
    assert "code=SMTP_CONNECTION_VERIFIED" in caplog.text
    assert "EMAIL_SUBMITTED" not in caplog.text
    for private_value in ("private-recipient@example.test", "private-server-response", "private-token"):
        assert private_value not in caplog.text
        assert private_value not in str(caught.value)
    assert all(record.exc_info is None for record in caplog.records)


def test_smtp_windows_connection_error_records_numeric_codes_only(monkeypatch, caplog) -> None:
    error = PermissionError(13, "private-server-response")
    error.winerror = 10013

    def denied_connection(*_args, **_kwargs):
        raise error

    monkeypatch.setattr(smtplib, "SMTP", denied_connection)
    with pytest.raises(EmailDeliveryError) as caught:
        SmtpMailTransport(_settings()).verify_connection()
    assert caught.value.code == "SMTP_CONNECTION_FAILED"
    assert caught.value.winerror == 10013
    assert "os_errno=13 winerror=10013" in caplog.text
    assert "private-server-response" not in caplog.text


def test_delivery_metadata_rejects_non_numeric_codes_and_unknown_labels() -> None:
    failure = EmailDeliveryError(
        "private-response", code="private-code", stage="private-stage", error_type="private-type",
        smtp_code="private-code", os_errno="private-errno", winerror="private-winerror",
    )
    assert failure.code == "EMAIL_DELIVERY_FAILED"
    assert failure.stage == "deliver"
    assert failure.error_type == "unknown"
    assert failure.smtp_code is failure.os_errno is failure.winerror is None


@pytest.mark.parametrize("secure", [False, True])
@pytest.mark.parametrize("accepted", [False, True])
def test_smtp_cleanup_failure_preserves_only_confirmed_email_acceptance(monkeypatch, caplog, secure, accepted) -> None:
    caplog.set_level("INFO", logger="app.services.email.service")
    events = []

    class BrokenCleanupSMTP:
        def __init__(self, *_args, **_kwargs):
            pass

        def __enter__(self):
            return self

        def __exit__(self, *_args):
            events.append("quit")
            raise smtplib.SMTPResponseException(421, b"private-cleanup-server-response")

        def ehlo(self):
            pass

        def starttls(self, **_kwargs):
            pass

        def login(self, _user, _password):
            pass

        def send_message(self, _message):
            events.append("submit")
            if not accepted:
                raise smtplib.SMTPDataError(554, b"private-delivery-server-response")
            return {}

    monkeypatch.setattr(smtplib, "SMTP_SSL" if secure else "SMTP", BrokenCleanupSMTP)

    def deliver():
        send_verification_email(
            recipient_email="private-recipient@example.test",
            verification_url="https://app.example.test/#/verify-email?token=private-token",
            settings=_settings(smtp_secure=secure, smtp_user="private-smtp-user", smtp_pass="private-smtp-password"),
        )

    if accepted:
        deliver()
        assert "code=EMAIL_SUBMITTED" in caplog.text
        assert "code=EMAIL_ACCEPTED_CLEANUP_FAILED stage=disconnect error_type=SMTPResponseException smtp_code=421" in caplog.text
        assert "SMTP operation failed" not in caplog.text
        assert all(record.levelname != "ERROR" for record in caplog.records)
    else:
        with pytest.raises(EmailDeliveryError):
            deliver()
        assert "EMAIL_SUBMITTED" not in caplog.text
        assert "EMAIL_ACCEPTED_CLEANUP_FAILED" not in caplog.text
        assert "SMTP operation failed" in caplog.text
    assert events == ["submit", "quit"]
    for private_value in (
        "private-cleanup-server-response", "private-delivery-server-response", "private-recipient@example.test",
        "private-token", "private-smtp-user", "private-smtp-password",
    ):
        assert private_value not in caplog.text
    assert all(record.exc_info is None for record in caplog.records)


def test_default_account_mail_expiry_matches_existing_lifetimes() -> None:
    transport = RecordingTransport()
    settings = _settings()
    send_verification_email(
        recipient_email="person@example.test", verification_url="https://app.example.test/#/verify-email?token=test-only",
        settings=settings, transport=transport,
    )
    send_password_reset_email(
        recipient_email="person@example.test", reset_url="https://app.example.test/#/reset-password?token=test-only",
        settings=settings, transport=transport,
    )
    assert "1440 minutes" in transport.messages[0].get_body(preferencelist=("plain",)).get_content()
    assert "30 minutes" in transport.messages[1].get_body(preferencelist=("plain",)).get_content()


@pytest.mark.parametrize("secure", [False, True])
@pytest.mark.parametrize("authenticated", [False, True])
def test_smtp_probe_cleanup_failure_preserves_only_confirmed_tls_authentication(monkeypatch, caplog, secure, authenticated) -> None:
    caplog.set_level("INFO", logger="app.services.email.service")
    events = []

    class BrokenCleanupSMTP:
        def __init__(self, *_args, **kwargs):
            assert kwargs["timeout"] == 3

        def __enter__(self):
            return self

        def __exit__(self, *_args):
            events.append("quit")
            raise smtplib.SMTPResponseException(421, b"private-cleanup-server-response")

        def ehlo(self):
            pass

        def starttls(self, **_kwargs):
            events.append("tls")

        def login(self, _user, _password):
            events.append("authenticate")
            if not authenticated:
                raise smtplib.SMTPAuthenticationError(535, b"private-authentication-server-response")

        def send_message(self, _message):
            pytest.fail("Connection checks must never send email")

    monkeypatch.setattr(smtplib, "SMTP_SSL" if secure else "SMTP", BrokenCleanupSMTP)
    transport = SmtpMailTransport(_settings(
        smtp_secure=secure, smtp_user="private-smtp-user", smtp_pass="private-smtp-password",
    ))
    if authenticated:
        transport.verify_connection(timeout=3)
        assert "code=SMTP_CONNECTION_VERIFIED" in caplog.text
        assert "code=SMTP_VERIFIED_CLEANUP_FAILED stage=disconnect error_type=SMTPResponseException smtp_code=421" in caplog.text
        assert "SMTP operation failed" not in caplog.text
        assert all(record.levelname != "ERROR" for record in caplog.records)
    else:
        with pytest.raises(EmailDeliveryError) as caught:
            transport.verify_connection(timeout=3)
        assert caught.value.code == "SMTP_AUTHENTICATION_FAILED"
        assert "code=SMTP_CONNECTION_VERIFIED" not in caplog.text
        assert "SMTP_VERIFIED_CLEANUP_FAILED" not in caplog.text
        assert "SMTP operation failed" in caplog.text
    assert events == (["authenticate", "quit"] if secure else ["tls", "authenticate", "quit"])
    for private_value in (
        "private-cleanup-server-response", "private-authentication-server-response",
        "private-smtp-user", "private-smtp-password",
    ):
        assert private_value not in caplog.text
    assert all(record.exc_info is None for record in caplog.records)
