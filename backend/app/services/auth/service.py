"""Local password authentication behind a provider boundary.

The bearer is signed with an environment key or a stable local-development key
persisted in the database. It is accepted only while the matching database
session and user remain active; the role always comes from the users table.
"""

from __future__ import annotations

from base64 import urlsafe_b64decode, urlsafe_b64encode
from binascii import Error as Base64Error
from datetime import datetime, timedelta, timezone
from enum import StrEnum
import hashlib
import hmac
import json
import re
import secrets
from typing import Protocol
from uuid import uuid4

from fastapi import Depends, HTTPException
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import Settings, get_settings
from app.contracts.auth import AuthenticatedUser, Role, RoleApprovalStatus, normalize_username
from app.db.models import AuthSessionModel, AuthSigningKeyModel, UserModel
from app.db.session import get_db
from app.email_address import normalize_email_address


class Permission(StrEnum):
    DOCUMENT_READ = "document:read"
    DOCUMENT_UPLOAD = "document:upload"
    DOCUMENT_PROCESS = "document:process"
    REVIEW_READ = "review:read"
    REVIEW_EDIT = "review:edit"
    REVIEW_DECIDE = "review:decide"
    REVIEW_RECOMMEND = "review:recommend"
    REVIEW_ASSIGN = "review:assign"
    RECORD_READ = "record:read"
    GIS_READ = "gis:read"
    AUDIT_READ = "audit:read"
    USER_MANAGE = "user:manage"


_PERMISSIONS: dict[Role, frozenset[Permission]] = {
    Role.ADMIN: frozenset(Permission),
    Role.REVENUE_OFFICER: frozenset({
        Permission.DOCUMENT_READ, Permission.DOCUMENT_UPLOAD, Permission.DOCUMENT_PROCESS,
        Permission.REVIEW_READ, Permission.REVIEW_EDIT, Permission.REVIEW_DECIDE,
        Permission.REVIEW_ASSIGN, Permission.RECORD_READ, Permission.GIS_READ,
        Permission.AUDIT_READ,
    }),
    Role.VERIFIER: frozenset({
        Permission.DOCUMENT_READ, Permission.REVIEW_READ, Permission.REVIEW_EDIT,
        Permission.REVIEW_RECOMMEND, Permission.RECORD_READ,
    }),
    Role.AUDITOR: frozenset({
        Permission.DOCUMENT_READ, Permission.REVIEW_READ, Permission.RECORD_READ,
        Permission.GIS_READ, Permission.AUDIT_READ,
    }),
}

_BEARER = HTTPBearer(auto_error=False)
_ISSUER = "bhudrishti-local-auth-v1"
_PBKDF2_ITERATIONS = 310_000
_DUMMY_HASH = "pbkdf2_sha256$310000$AAAAAAAAAAAAAAAAAAAAAA$ez9XsE0VPa_YQ1lVFNBkW6R_NWyF9vPGb9KuFZ1p3LE"
_GENERIC_LOGIN_ERROR = "Invalid email or password."


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _aware(value: datetime) -> datetime:
    return value.replace(tzinfo=timezone.utc) if value.tzinfo is None else value


def _b64(raw: bytes) -> str:
    return urlsafe_b64encode(raw).rstrip(b"=").decode("ascii")


def _unb64(value: str) -> bytes:
    return urlsafe_b64decode(value + "=" * (-len(value) % 4))


def hash_password(password: str) -> str:
    if len(password) < 12 or len(password) > 256:
        raise ValueError("Password must contain 12 to 256 characters.")
    salt = secrets.token_bytes(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, _PBKDF2_ITERATIONS)
    return f"pbkdf2_sha256${_PBKDF2_ITERATIONS}${_b64(salt)}${_b64(digest)}"


def verify_password(password: str, encoded: str) -> bool:
    try:
        algorithm, rounds, salt, expected = encoded.split("$", 3)
        iterations = int(rounds)
        if algorithm != "pbkdf2_sha256" or not 100_000 <= iterations <= 1_000_000:
            return False
        actual = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), _unb64(salt), iterations)
        return hmac.compare_digest(actual, _unb64(expected))
    except (ValueError, UnicodeError, Base64Error):
        return False


def as_user(stored: UserModel) -> AuthenticatedUser:
    return AuthenticatedUser(
        id=stored.id, name=stored.name, username=stored.username,
        email=stored.email, role=Role(stored.role),
        requested_role=Role(stored.requested_role) if stored.requested_role else None,
        role_approval_status=(
            RoleApprovalStatus(stored.role_approval_status) if stored.role_approval_status else None
        ),
    )


def find_user(session: Session, user_id: str | None) -> AuthenticatedUser | None:
    stored = session.get(UserModel, user_id) if user_id else None
    return as_user(stored) if stored else None


def _generated_username(session: Session, email: str) -> str:
    local = email.split("@", 1)[0].lower()
    base = re.sub(r"[^a-z0-9._-]", "_", local).strip("._-")[:24]
    if len(base) < 3:
        base = f"user_{base}" if base else "user"
    candidate = base
    suffix = 2
    while session.scalar(select(UserModel.id).where(UserModel.username == candidate)):
        candidate = f"{base[:32 - len(str(suffix)) - 1]}_{suffix}"
        suffix += 1
    return candidate


def create_user(
    session: Session, *, email: str, name: str, password: str, role: Role,
    username: str | None = None, status: str = "ACTIVE",
    requested_role: Role | None = None,
) -> UserModel:
    normalized_email = normalize_email_address(email)
    clean_name = name.strip()
    if len(clean_name) < 2 or len(clean_name) > 160:
        raise ValueError("Name must contain 2 to 160 characters.")
    if session.scalar(select(UserModel).where(UserModel.email == normalized_email)):
        raise ValueError("An account with this email already exists.")
    normalized_username = normalize_username(username) if username is not None else _generated_username(session, normalized_email)
    if session.scalar(select(UserModel.id).where(UserModel.username == normalized_username)):
        raise ValueError("An account with this username already exists.")
    if status not in {"ACTIVE", "UNVERIFIED"}:
        raise ValueError("Unsupported account status.")
    if requested_role == Role.ADMIN and (role != Role.AUDITOR or status != "UNVERIFIED"):
        raise ValueError("Administrator requests must start as unverified auditors.")
    if requested_role not in {None, Role.ADMIN, role}:
        raise ValueError("Requested role must match the assigned role.")
    now = _now()
    user = UserModel(
        id=str(uuid4()), email=normalized_email, name=clean_name,
        username=normalized_username, status=status,
        email_verified_at=now if status == "ACTIVE" else None,
        role=role.value, password_hash=hash_password(password), is_active=status == "ACTIVE",
        requested_role=requested_role.value if requested_role else None,
        role_approval_status="PENDING" if requested_role == Role.ADMIN else None,
        failed_login_count=0,
    )
    session.add(user)
    session.flush()
    return user


class AuthenticationProvider(Protocol):
    def authenticate(self, session: Session, email: str, password: str) -> UserModel: ...


class LocalPasswordProvider:
    """Database-backed password provider; another provider can implement this protocol."""

    def authenticate(self, session: Session, email: str, password: str) -> UserModel:
        normalized = email.strip().casefold()
        stored = session.scalar(select(UserModel).where(UserModel.email == normalized))
        if stored is None:
            verify_password(password, _DUMMY_HASH)
            raise HTTPException(status_code=401, detail=_GENERIC_LOGIN_ERROR)
        if not _is_active_account(stored):
            verify_password(password, _DUMMY_HASH)
            raise HTTPException(status_code=401, detail=_GENERIC_LOGIN_ERROR)
        if stored.locked_until and _aware(stored.locked_until) > _now():
            verify_password(password, _DUMMY_HASH)
            raise HTTPException(status_code=401, detail=_GENERIC_LOGIN_ERROR)
        if not verify_password(password, stored.password_hash):
            stored.failed_login_count = (stored.failed_login_count or 0) + 1
            if stored.failed_login_count >= 5:
                stored.locked_until = _now() + timedelta(minutes=15)
                stored.failed_login_count = 0
            session.commit()
            raise HTTPException(status_code=401, detail=_GENERIC_LOGIN_ERROR)
        stored.failed_login_count = 0
        stored.locked_until = None
        session.flush()
        return stored


def get_auth_provider(settings: Settings) -> AuthenticationProvider:
    if settings.auth_provider == "local":
        return LocalPasswordProvider()
    raise RuntimeError("Unsupported authentication provider")


def _is_active_account(user: UserModel) -> bool:
    return bool(user.is_active and user.status == "ACTIVE" and user.email_verified_at is not None)


def _signing_key(session: Session, settings: Settings, *, create: bool) -> bytes | None:
    if settings.auth_secret:
        return settings.auth_secret.encode("utf-8")
    if settings.environment.lower() not in {"development", "test", "testing"}:
        return None
    stored = session.get(AuthSigningKeyModel, "local")
    if stored is None and create:
        stored = AuthSigningKeyModel(id="local", secret_hex=secrets.token_hex(32))
        session.add(stored)
        session.flush()
    return bytes.fromhex(stored.secret_hex) if stored else None


def issue_token(session: Session, user: UserModel, settings: Settings) -> tuple[str, datetime]:
    if not _is_active_account(user):
        raise HTTPException(status_code=401, detail="Account is inactive.")
    key = _signing_key(session, settings, create=True)
    if key is None:
        raise HTTPException(status_code=503, detail="Authentication is not configured.")
    now = _now()
    expires = now + timedelta(hours=settings.auth_session_hours)
    session_id = str(uuid4())
    session.add(AuthSessionModel(
        id=session_id, user_id=user.id, created_at=now, expires_at=expires,
    ))
    session.flush()
    payload = {
        "iss": _ISSUER, "sub": user.id, "sid": session_id,
        "iat": int(now.timestamp()), "exp": int(expires.timestamp()),
    }
    body = _b64(json.dumps(payload, separators=(",", ":"), sort_keys=True).encode("utf-8"))
    signature = _b64(hmac.new(key, body.encode("ascii"), hashlib.sha256).digest())
    return f"{body}.{signature}", expires


def authenticate_token(
    token: str, session: Session, settings: Settings,
) -> tuple[AuthenticatedUser, AuthSessionModel]:
    try:
        body, signature = token.split(".")
        key = _signing_key(session, settings, create=False)
        if key is None:
            raise ValueError("No signing key")
        expected = _b64(hmac.new(key, body.encode("ascii"), hashlib.sha256).digest())
        if not hmac.compare_digest(signature, expected):
            raise ValueError("Invalid signature")
        payload = json.loads(_unb64(body))
        now = int(_now().timestamp())
        if (
            not isinstance(payload, dict)
            or payload.get("iss") != _ISSUER
            or not isinstance(payload.get("iat"), int)
            or not isinstance(payload.get("exp"), int)
            or payload["iat"] > now
            or payload["exp"] <= now
            or payload["exp"] - payload["iat"] > settings.auth_session_hours * 3600
        ):
            raise ValueError("Invalid token claims")
        user_id, session_id = payload.get("sub"), payload.get("sid")
        if not isinstance(user_id, str) or not isinstance(session_id, str):
            raise ValueError("Invalid token subject")
        stored_session = session.get(AuthSessionModel, session_id)
        if (
            stored_session is None
            or stored_session.user_id != user_id
            or stored_session.revoked_at is not None
            or _aware(stored_session.expires_at) <= _now()
        ):
            raise ValueError("Inactive session")
        stored_user = session.get(UserModel, user_id)
        if stored_user is None or not _is_active_account(stored_user):
            raise ValueError("Inactive user")
        return as_user(stored_user), stored_session
    except (ValueError, KeyError, TypeError, UnicodeError, Base64Error, json.JSONDecodeError):
        raise HTTPException(status_code=401, detail="Invalid or expired session.") from None


def get_current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(_BEARER),
    session: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
) -> AuthenticatedUser:
    if credentials is None or credentials.scheme.lower() != "bearer":
        raise HTTPException(status_code=401, detail="Bearer session is required.")
    return authenticate_token(credentials.credentials, session, settings)[0]


def require_permission(permission: Permission):
    def dependency(user: AuthenticatedUser = Depends(get_current_user)) -> AuthenticatedUser:
        if permission not in _PERMISSIONS[user.role]:
            raise HTTPException(status_code=403, detail="Your role cannot perform that action.")
        return user

    return dependency
