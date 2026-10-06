"""One-time email verification and password reset tokens.

Only a SHA-256 digest of each cryptographically random token is persisted.
The raw token exists only long enough to place it in the outgoing email.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
import hashlib
import secrets
from uuid import uuid4

from sqlalchemy import select, update
from sqlalchemy.orm import Session

from app.db.models import AuthActionTokenModel, AuthSessionModel, UserModel
from app.services.auth.service import hash_password


EMAIL_VERIFICATION = "EMAIL_VERIFICATION"
PASSWORD_RESET = "PASSWORD_RESET"
VERIFICATION_LIFETIME = timedelta(hours=24)
RESET_LIFETIME = timedelta(minutes=30)
REQUEST_COOLDOWN = timedelta(minutes=1)


class InvalidActionToken(Exception):
    """Token is unknown, expired, already consumed, or has the wrong purpose."""


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _aware(value: datetime) -> datetime:
    return value.replace(tzinfo=timezone.utc) if value.tzinfo is None else value


def _digest(raw_token: str) -> str:
    return hashlib.sha256(raw_token.encode("utf-8")).hexdigest()


def recent_token_exists(session: Session, user: UserModel, purpose: str) -> bool:
    latest = session.scalar(
        select(AuthActionTokenModel.created_at)
        .where(
            AuthActionTokenModel.user_id == user.id,
            AuthActionTokenModel.purpose == purpose,
            AuthActionTokenModel.used_at.is_(None),
        )
        .order_by(AuthActionTokenModel.created_at.desc())
        .limit(1)
    )
    return bool(latest and _aware(latest) > _now() - REQUEST_COOLDOWN)


def issue_action_token(session: Session, user: UserModel, purpose: str) -> str:
    if purpose not in {EMAIL_VERIFICATION, PASSWORD_RESET}:
        raise ValueError("Unsupported action token purpose.")
    raw = secrets.token_urlsafe(32)
    now = _now()
    lifetime = VERIFICATION_LIFETIME if purpose == EMAIL_VERIFICATION else RESET_LIFETIME
    session.add(AuthActionTokenModel(
        id=str(uuid4()), user_id=user.id, purpose=purpose,
        token_hash=_digest(raw), created_at=now, expires_at=now + lifetime,
    ))
    session.flush()
    return raw


def invalidate_action_token(session: Session, raw: str) -> None:
    """Retire a token whose email was not accepted by the transport."""
    session.execute(
        update(AuthActionTokenModel)
        .where(AuthActionTokenModel.token_hash == _digest(raw), AuthActionTokenModel.used_at.is_(None))
        .values(used_at=_now())
        .execution_options(synchronize_session=False)
    )


def _claim_action_token(session: Session, raw: str, purpose: str) -> tuple[UserModel, datetime]:
    stored = session.scalar(select(AuthActionTokenModel).where(
        AuthActionTokenModel.token_hash == _digest(raw),
        AuthActionTokenModel.purpose == purpose,
    ))
    now = _now()
    if stored is None or stored.used_at is not None or _aware(stored.expires_at) <= now:
        raise InvalidActionToken
    claimed = session.execute(
        update(AuthActionTokenModel)
        .where(
            AuthActionTokenModel.id == stored.id,
            AuthActionTokenModel.used_at.is_(None),
            AuthActionTokenModel.expires_at > now,
        )
        .values(used_at=now)
        .execution_options(synchronize_session=False)
    )
    if claimed.rowcount != 1:
        raise InvalidActionToken
    user = session.get(UserModel, stored.user_id)
    if user is None:
        raise InvalidActionToken
    return user, now


def verify_email(session: Session, raw: str) -> UserModel:
    user, now = _claim_action_token(session, raw, EMAIL_VERIFICATION)
    if user.status != "UNVERIFIED":
        raise InvalidActionToken
    user.email_verified_at = now
    user.status = "ACTIVE"
    user.is_active = True
    session.execute(
        update(AuthActionTokenModel)
        .where(
            AuthActionTokenModel.user_id == user.id,
            AuthActionTokenModel.purpose == EMAIL_VERIFICATION,
            AuthActionTokenModel.used_at.is_(None),
        )
        .values(used_at=now)
        .execution_options(synchronize_session=False)
    )
    session.flush()
    return user


def reset_password(session: Session, raw: str, new_password: str) -> UserModel:
    user, now = _claim_action_token(session, raw, PASSWORD_RESET)
    if user.status != "ACTIVE" or not user.is_active or user.email_verified_at is None:
        raise InvalidActionToken
    user.password_hash = hash_password(new_password)
    user.failed_login_count = 0
    user.locked_until = None
    session.execute(
        update(AuthSessionModel)
        .where(AuthSessionModel.user_id == user.id, AuthSessionModel.revoked_at.is_(None))
        .values(revoked_at=now)
        .execution_options(synchronize_session=False)
    )
    session.execute(
        update(AuthActionTokenModel)
        .where(
            AuthActionTokenModel.user_id == user.id,
            AuthActionTokenModel.purpose == PASSWORD_RESET,
            AuthActionTokenModel.used_at.is_(None),
        )
        .values(used_at=now)
        .execution_options(synchronize_session=False)
    )
    session.flush()
    return user
