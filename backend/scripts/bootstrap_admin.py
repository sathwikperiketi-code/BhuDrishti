"""Create a missing administrator or explicitly reset its password.

Run after Alembic migration from the backend directory. A password is read
from a prompt or BHUDRISHTI_BOOTSTRAP_PASSWORD for controlled noninteractive
setup. There are no built-in accounts or default passwords.
"""

from __future__ import annotations

import argparse
from collections.abc import Callable
from datetime import datetime, timezone
from getpass import getpass
import os

from sqlalchemy import select, update
from sqlalchemy.orm import Session

from app.config import Settings, get_settings
from app.contracts.auth import Role
from app.db.models import AuthSessionModel, UserModel
from app.db.session import SessionLocal
from app.services.auth.service import create_user, hash_password


def provision_admin(
    session: Session,
    settings: Settings,
    *,
    email: str,
    name: str | None,
    password_supplier: Callable[[], str],
    reset_password: bool = False,
    allow_production_reset: bool = False,
    allow_additional_admin: bool = False,
) -> tuple[UserModel, str]:
    """Return the account and action, prompting for a password only if needed."""
    normalized_email = email.strip().casefold()
    existing = session.scalar(select(UserModel).where(UserModel.email == normalized_email))

    if reset_password:
        if settings.environment.lower() not in {"development", "test", "testing"} and not allow_production_reset:
            raise ValueError("Password reset outside local development requires --allow-production-reset.")
        if existing is None or existing.role != Role.ADMIN.value:
            raise ValueError("The specified administrator account does not exist.")
        existing.password_hash = hash_password(password_supplier())
        existing.failed_login_count = 0
        existing.locked_until = None
        session.execute(
            update(AuthSessionModel)
            .where(AuthSessionModel.user_id == existing.id, AuthSessionModel.revoked_at.is_(None))
            .values(revoked_at=datetime.now(timezone.utc))
        )
        session.flush()
        return existing, "reset"

    if existing is not None:
        if existing.role != Role.ADMIN.value:
            raise ValueError("An account with this email exists but is not an administrator.")
        return existing, "unchanged"

    if session.scalar(select(UserModel.id).where(UserModel.role == Role.ADMIN.value).limit(1)):
        if settings.environment.lower() not in {"development", "test", "testing"}:
            raise ValueError("Additional administrator bootstrap is available only in local development.")
        if not allow_additional_admin:
            raise ValueError("An administrator already exists. Use --allow-additional-admin to create another local administrator.")
    if name is None:
        raise ValueError("--name is required when creating an administrator.")
    user = create_user(session, email=email, name=name, password=password_supplier(), role=Role.ADMIN)
    return user, "created"


def _read_password() -> str:
    password = os.environ.get("BHUDRISHTI_BOOTSTRAP_PASSWORD")
    if password is not None:
        return password
    password = getpass("Administrator password (12+ characters): ")
    if password != getpass("Confirm password: "):
        raise ValueError("Passwords did not match.")
    return password


def main() -> None:
    parser = argparse.ArgumentParser(description="Create a missing BhuDrishti administrator or explicitly reset its password.")
    parser.add_argument("--email", required=True)
    parser.add_argument("--name", help="Required when creating an administrator")
    parser.add_argument("--reset-password", action="store_true", help="Replace this administrator's password and revoke its sessions")
    parser.add_argument("--confirm-email", help="Required for reset; must match --email exactly after normalization")
    parser.add_argument("--allow-production-reset", action="store_true", help="Explicitly permit a reset outside local development")
    parser.add_argument("--allow-additional-admin", action="store_true", help="Explicitly create another administrator in local development")
    args = parser.parse_args()

    if args.reset_password:
        if not args.confirm_email or args.confirm_email.strip().casefold() != args.email.strip().casefold():
            parser.error("--reset-password requires --confirm-email matching --email")
        if args.allow_additional_admin:
            parser.error("--allow-additional-admin cannot be combined with --reset-password")
    elif args.confirm_email or args.allow_production_reset:
        parser.error("--confirm-email and --allow-production-reset require --reset-password")

    with SessionLocal() as session:
        try:
            user, action = provision_admin(
                session,
                get_settings(),
                email=args.email,
                name=args.name,
                password_supplier=_read_password,
                reset_password=args.reset_password,
                allow_production_reset=args.allow_production_reset,
                allow_additional_admin=args.allow_additional_admin,
            )
            session.commit()
        except ValueError as error:
            session.rollback()
            raise SystemExit(str(error)) from error
    if action == "created":
        print(f"Created administrator {user.email} ({user.id}).")
    elif action == "reset":
        print(f"Reset administrator password and revoked sessions for {user.email} ({user.id}).")
    else:
        print(f"Administrator {user.email} already exists; no changes made.")


if __name__ == "__main__":
    main()
