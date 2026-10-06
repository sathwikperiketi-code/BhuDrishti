"""TLS-only SMTP delivery and account email templates.

The transport is an argument to the public send functions, allowing tests to
record messages without changing production delivery behavior.
"""

from __future__ import annotations

from email.message import EmailMessage
from html import escape
import logging
import smtplib
import ssl
from typing import Protocol
from urllib.parse import urlsplit

from app.config import Settings
from app.email_address import normalize_email_address


_logger = logging.getLogger(__name__)
_FAILURE_CODES = {
    "SMTP_AUTHENTICATION_FAILED", "SMTP_CONNECTION_FAILED",
    "SMTP_TLS_FAILED", "EMAIL_DELIVERY_FAILED",
}
_STAGES = {"connect", "tls", "authenticate", "deliver"}
_ERROR_TYPES = {
    "SMTPAuthenticationError", "SMTPNotSupportedError", "SMTPConnectError",
    "SMTPServerDisconnected", "SMTPRecipientsRefused", "SMTPSenderRefused",
    "SMTPDataError", "SMTPResponseException", "SMTPException", "SSLError",
    "PermissionError", "ConnectionRefusedError", "ConnectionResetError", "TimeoutError",
    "OSError", "unknown",
}


class EmailConfigurationError(RuntimeError):
    """Required SMTP settings are missing or inconsistent."""

    def __init__(self, message: str, *, setting: str = "unknown") -> None:
        super().__init__(message)
        self.setting = setting if setting in {
            "SMTP_HOST", "SMTP_FROM", "SMTP_USER/SMTP_PASS", "Recipient email", "EMAIL_LINK",
        } else "unknown"


class EmailDeliveryError(RuntimeError):
    """The configured SMTP server did not accept the email."""

    def __init__(
        self, message: str = "SMTP delivery failed; account email was not sent.", *,
        code: str = "EMAIL_DELIVERY_FAILED", stage: str = "deliver",
        error_type: str = "unknown", smtp_code: int | None = None,
        os_errno: int | None = None, winerror: int | None = None,
    ) -> None:
        super().__init__(message)
        # Only these fixed labels and numeric codes are suitable for diagnostics.
        # SMTP response text may include addresses, credentials, or message data.
        self.code = code if code in _FAILURE_CODES else "EMAIL_DELIVERY_FAILED"
        self.stage = stage if stage in _STAGES else "deliver"
        self.error_type = error_type if error_type in _ERROR_TYPES else "unknown"
        self.smtp_code = smtp_code if type(smtp_code) is int else None
        self.os_errno = os_errno if type(os_errno) is int else None
        self.winerror = winerror if type(winerror) is int else None


def _delivery_error(
    error: Exception, stage: str, *, connection_check: bool = False, log_failure: bool = True,
) -> EmailDeliveryError:
    """Keep the diagnostic cause without retaining unsafe server response text."""
    if isinstance(error, smtplib.SMTPAuthenticationError):
        code = "SMTP_AUTHENTICATION_FAILED"
    elif isinstance(error, ssl.SSLError) or (
        isinstance(error, smtplib.SMTPNotSupportedError) and stage == "tls"
    ):
        code = "SMTP_TLS_FAILED"
    elif isinstance(error, (smtplib.SMTPConnectError, smtplib.SMTPServerDisconnected)) or (
        isinstance(error, OSError) and not isinstance(error, smtplib.SMTPException)
    ):
        code = "SMTP_CONNECTION_FAILED"
    elif stage == "authenticate":
        code = "SMTP_AUTHENTICATION_FAILED"
    elif stage == "tls":
        code = "SMTP_TLS_FAILED"
    elif stage == "connect":
        code = "SMTP_CONNECTION_FAILED"
    else:
        code = "EMAIL_DELIVERY_FAILED"

    error_type = next((kind.__name__ for kind in (
        smtplib.SMTPAuthenticationError, smtplib.SMTPNotSupportedError,
        smtplib.SMTPConnectError, smtplib.SMTPServerDisconnected,
        smtplib.SMTPRecipientsRefused, smtplib.SMTPSenderRefused,
        smtplib.SMTPDataError, smtplib.SMTPResponseException,
        smtplib.SMTPException, ssl.SSLError, PermissionError,
        ConnectionRefusedError, ConnectionResetError, TimeoutError, OSError,
    ) if isinstance(error, kind)), "unknown")
    message = (
        "SMTP connection check failed." if connection_check else
        "SMTP server did not offer STARTTLS; account email was not sent."
        if isinstance(error, smtplib.SMTPNotSupportedError) and stage == "tls" else
        "SMTP delivery failed; account email was not sent."
    )
    smtp_code = getattr(error, "smtp_code", None)
    if isinstance(error, smtplib.SMTPRecipientsRefused):
        # smtplib stores recipient errors by address; retain only a common
        # numeric status, never the addresses or server response text.
        recipient_codes = {
            result[0] for result in error.recipients.values()
            if isinstance(result, (tuple, list)) and result and type(result[0]) is int
        }
        if len(recipient_codes) == 1:
            smtp_code = recipient_codes.pop()
    failure = EmailDeliveryError(
        message, code=code, stage=stage, error_type=error_type,
        smtp_code=smtp_code, os_errno=getattr(error, "errno", None),
        winerror=getattr(error, "winerror", None),
    )
    if log_failure:
        _logger.error(
            "SMTP operation failed: code=%s stage=%s error_type=%s smtp_code=%s os_errno=%s winerror=%s",
            failure.code, failure.stage, failure.error_type, failure.smtp_code, failure.os_errno,
            failure.winerror,
        )
    return failure


class MailTransport(Protocol):
    def send(self, message: EmailMessage) -> None: ...

    def verify_connection(self, *, timeout: float = 5) -> None: ...


def _validated_address(value: str | None, setting: str) -> str:
    if not value or any(ord(char) < 32 or ord(char) == 127 for char in value):
        raise EmailConfigurationError(f"{setting} must be a valid email address.", setting=setting)
    try:
        if setting == "Recipient email":
            return normalize_email_address(value)
        # A configured branded From display name is allowed, but there must
        # be exactly one valid mailbox and no malformed header syntax.
        if value.strip().startswith(",") or value.strip().endswith(","):
            raise ValueError("Invalid sender mailbox list")
        probe = EmailMessage()
        probe["From"] = value
        sender = probe["From"]
        if sender.defects or len(sender.addresses) != 1:
            raise ValueError("Invalid sender mailbox")
        normalize_email_address(sender.addresses[0].addr_spec)
    except (ValueError, IndexError):
        raise EmailConfigurationError(f"{setting} must be a valid email address.", setting=setting)
    return value.strip()


def _validated_url(url: str) -> str:
    try:
        parts = urlsplit(url)
        valid = (
            parts.scheme in {"http", "https"}
            and bool(parts.hostname)
            and parts.username is None
            and parts.password is None
            and not any(char.isspace() for char in url)
        )
        _ = parts.port
    except ValueError:
        valid = False
    if not valid:
        raise EmailConfigurationError("Account email link must be an absolute HTTP(S) URL.", setting="EMAIL_LINK")
    return url


class SmtpMailTransport:
    """Deliver email with implicit TLS or mandatory STARTTLS.

    ``SMTP_SECURE=true`` selects SMTP_SSL. When false, STARTTLS is required
    before authentication or message delivery. A server without TLS support
    fails closed, including when no SMTP credentials are configured.
    """

    def __init__(self, settings: Settings):
        if not settings.smtp_host or not settings.smtp_host.strip():
            raise EmailConfigurationError("SMTP_HOST must be configured to send account email.", setting="SMTP_HOST")
        _validated_address(settings.smtp_from, "SMTP_FROM")
        if bool(settings.smtp_user) != bool(settings.smtp_pass):
            raise EmailConfigurationError(
                "SMTP_USER and SMTP_PASS must both be configured for authenticated SMTP.",
                setting="SMTP_USER/SMTP_PASS",
            )
        self._settings = settings

    def send(self, message: EmailMessage) -> None:
        settings = self._settings
        context = ssl.create_default_context()
        stage = "connect"
        accepted = False
        try:
            if settings.smtp_secure:
                with smtplib.SMTP_SSL(
                    settings.smtp_host, settings.smtp_port, timeout=15, context=context,
                ) as smtp:
                    stage = "authenticate"
                    self._authenticate(smtp)
                    _logger.info("SMTP connection verified: code=SMTP_CONNECTION_VERIFIED stage=authenticate")
                    stage = "deliver"
                    self._submit(smtp, message)
                    accepted = True
            else:
                with smtplib.SMTP(settings.smtp_host, settings.smtp_port, timeout=15) as smtp:
                    smtp.ehlo()
                    stage = "tls"
                    smtp.starttls(context=context)
                    smtp.ehlo()
                    stage = "authenticate"
                    self._authenticate(smtp)
                    _logger.info("SMTP connection verified: code=SMTP_CONNECTION_VERIFIED stage=authenticate")
                    stage = "deliver"
                    self._submit(smtp, message)
                    accepted = True
        except (smtplib.SMTPException, OSError) as error:
            if accepted:
                # SMTP DATA acceptance cannot be undone by a later QUIT or
                # socket teardown error. Reporting failure here would retire
                # an action token that the provider has already emailed.
                diagnostic = _delivery_error(error, stage, log_failure=False)
                _logger.warning(
                    "SMTP cleanup failed after email acceptance: code=EMAIL_ACCEPTED_CLEANUP_FAILED "
                    "stage=disconnect error_type=%s smtp_code=%s os_errno=%s winerror=%s",
                    diagnostic.error_type, diagnostic.smtp_code, diagnostic.os_errno, diagnostic.winerror,
                )
                return
            raise _delivery_error(error, stage) from None

    def verify_connection(self, *, timeout: float = 5) -> None:
        """Verify TLS and configured SMTP authentication without sending mail.

        This is intended for an infrequent background health probe, never for
        each HTTP health request. Errors are deliberately stripped of server
        responses, which can contain account details.
        """
        settings = self._settings
        context = ssl.create_default_context()
        stage = "connect"
        verified = False
        try:
            if settings.smtp_secure:
                with smtplib.SMTP_SSL(
                    settings.smtp_host, settings.smtp_port, timeout=timeout, context=context,
                ) as smtp:
                    smtp.ehlo()
                    stage = "authenticate"
                    self._authenticate(smtp)
                    verified = True
            else:
                with smtplib.SMTP(settings.smtp_host, settings.smtp_port, timeout=timeout) as smtp:
                    smtp.ehlo()
                    stage = "tls"
                    smtp.starttls(context=context)
                    smtp.ehlo()
                    stage = "authenticate"
                    self._authenticate(smtp)
                    verified = True
        except (smtplib.SMTPException, OSError) as error:
            if not verified:
                raise _delivery_error(error, stage, connection_check=True) from None
            # A disconnect after successful TLS/authentication does not undo
            # the connection check or justify blocking password recovery.
            diagnostic = _delivery_error(error, stage, connection_check=True, log_failure=False)
            _logger.warning(
                "SMTP cleanup failed after connection verification: code=SMTP_VERIFIED_CLEANUP_FAILED "
                "stage=disconnect error_type=%s smtp_code=%s os_errno=%s winerror=%s",
                diagnostic.error_type, diagnostic.smtp_code, diagnostic.os_errno, diagnostic.winerror,
            )
        _logger.info("SMTP connection verified: code=SMTP_CONNECTION_VERIFIED stage=authenticate")

    @staticmethod
    def _submit(smtp: smtplib.SMTP, message: EmailMessage) -> None:
        refused = smtp.send_message(message)
        if refused:
            # send_message can return partial refusal without raising. Account
            # mail must not report success when its recipient was rejected.
            raise smtplib.SMTPRecipientsRefused(refused)
        _logger.info("SMTP email submission succeeded: code=EMAIL_SUBMITTED stage=deliver")

    def _authenticate(self, smtp: smtplib.SMTP) -> None:
        if self._settings.smtp_user and self._settings.smtp_pass:
            smtp.login(self._settings.smtp_user, self._settings.smtp_pass.get_secret_value())

def get_mail_transport(settings: Settings) -> MailTransport:
    """A small dependency seam for routes to override in integration tests."""
    return SmtpMailTransport(settings)


def _make_message(
    *, recipient_email: str, sender: str, subject: str, action: str,
    action_url: str, explanation: str, expires_minutes: int,
) -> EmailMessage:
    sender = _validated_address(sender, "SMTP_FROM")
    recipient_email = _validated_address(recipient_email, "Recipient email")
    _validated_url(action_url)
    if expires_minutes < 1:
        raise ValueError("Account email expiry must be positive.")

    message = EmailMessage()
    message["From"] = sender
    message["To"] = recipient_email
    message["Subject"] = subject
    message.set_content(
        f"BhuDrishti AI\n\n{explanation}\n\n{action}: {action_url}\n\n"
        f"This link expires in {expires_minutes} minutes.\n\n"
        "If you did not request this, you can ignore this email.\n"
    )
    safe_url = escape(action_url, quote=True)
    message.add_alternative(
        "<!doctype html><html lang=\"en\"><head><meta charset=\"utf-8\"></head>"
        "<body style=\"margin:0;padding:32px 16px;background:#f4f7f5;"
        "font-family:Arial,sans-serif;color:#17352e\">"
        "<div style=\"max-width:560px;margin:auto;background:white;border-radius:12px;"
        "padding:32px;border:1px solid #dfe8e1\">"
        "<div style=\"font-size:21px;font-weight:700;color:#126450\">BhuDrishti AI</div>"
        f"<h1 style=\"font-size:24px;margin:28px 0 12px\">{escape(subject)}</h1>"
        f"<p style=\"line-height:1.6\">{escape(explanation)}</p>"
        f"<p style=\"margin:30px 0\"><a href=\"{safe_url}\" style=\"background:#126450;"
        "color:#fff;text-decoration:none;padding:13px 20px;border-radius:8px;"
        f"display:inline-block\">{escape(action)}</a></p>"
        f"<p style=\"font-size:14px;line-height:1.5\">This link expires in {expires_minutes} minutes.</p>"
        "<p style=\"font-size:14px;line-height:1.5\">If you did not request this, "
        "you can ignore this email.</p>"
        "<p style=\"font-size:12px;color:#536b62;word-break:break-all\">"
        f"If the button does not work, copy this link: {safe_url}</p>"
        "</div></body></html>",
        subtype="html",
    )
    return message


def send_verification_email(
    *, recipient_email: str, verification_url: str, settings: Settings,
    transport: MailTransport | None = None, expires_minutes: int = 24 * 60,
) -> None:
    message = _make_message(
        recipient_email=recipient_email,
        sender=settings.smtp_from or "",
        subject="Verify your BhuDrishti AI email",
        action="Verify email address",
        action_url=verification_url,
        explanation="Confirm your email address to activate your BhuDrishti AI account.",
        expires_minutes=expires_minutes,
    )
    (transport or get_mail_transport(settings)).send(message)


def send_password_reset_email(
    *, recipient_email: str, reset_url: str, settings: Settings,
    transport: MailTransport | None = None, expires_minutes: int = 30,
) -> None:
    message = _make_message(
        recipient_email=recipient_email,
        sender=settings.smtp_from or "",
        subject="Reset your BhuDrishti AI password",
        action="Reset password",
        action_url=reset_url,
        explanation="Use the link below to choose a new password for your BhuDrishti AI account.",
        expires_minutes=expires_minutes,
    )
    (transport or get_mail_transport(settings)).send(message)
