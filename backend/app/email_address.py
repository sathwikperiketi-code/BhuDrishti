"""Validate account email as one bare mailbox, never a header address list."""

from __future__ import annotations

import re


_LOCAL_PART = re.compile(r"^[a-z0-9!#$%&'*+/=?^_`{|}~-]+(?:\.[a-z0-9!#$%&'*+/=?^_`{|}~-]+)*$", re.ASCII)
_DOMAIN_LABEL = re.compile(r"^[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?$", re.ASCII)


def normalize_email_address(value: str) -> str:
    """Accept the supported mailbox syntax and return its canonical lookup key.

    Header display names, comments and lists must not be persisted as an account
    address: SMTP would otherwise reinterpret them as a different recipient.
    Plus aliases and punycode domain names remain supported.
    """
    stripped = value.strip()
    normalized = stripped.casefold()
    local, separator, domain = normalized.rpartition("@")
    labels = domain.split(".")
    if (
        not stripped.isascii()
        or not separator
        or len(normalized) > 254
        or not 1 <= len(local) <= 64
        or not _LOCAL_PART.fullmatch(local)
        or len(labels) < 2
        or not all(_DOMAIN_LABEL.fullmatch(label) for label in labels)
    ):
        raise ValueError("Enter a valid email address.")
    return normalized
