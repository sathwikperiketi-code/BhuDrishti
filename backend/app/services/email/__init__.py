"""Transactional account email through a replaceable transport."""

from .service import (
    EmailConfigurationError,
    EmailDeliveryError,
    MailTransport,
    SmtpMailTransport,
    get_mail_transport,
    send_password_reset_email,
    send_verification_email,
)

__all__ = [
    "EmailConfigurationError",
    "EmailDeliveryError",
    "MailTransport",
    "SmtpMailTransport",
    "get_mail_transport",
    "send_password_reset_email",
    "send_verification_email",
]
