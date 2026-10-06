"""Administrator bootstrap and explicit recovery on isolated databases."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from pathlib import Path
import sys

import pytest
from sqlalchemy import func, select
from sqlalchemy.orm import sessionmaker

from app.config import Settings
from app.contracts.auth import Role
from app.db.base import Base
from app.db.models import AuthSessionModel, UserModel
from app.db.session import build_engine
from app.services.auth.service import create_user, verify_password
from scripts import bootstrap_admin


@pytest.fixture
def db_factory(tmp_path: Path):
    engine = build_engine(f"sqlite:///{(tmp_path / 'bootstrap.db').as_posix()}")
    Base.metadata.create_all(bind=engine)
    factory = sessionmaker(bind=engine, autoflush=False, autocommit=False, expire_on_commit=False)
    yield factory
    engine.dispose()


def test_create_if_missing_with_other_users_and_repeat_without_password(db_factory) -> None:
    settings = Settings(_env_file=None, environment="test")
    with db_factory() as session:
        create_user(
            session, email="officer@example.test", name="Test Officer",
            password="OfficerPassword123!", role=Role.REVENUE_OFFICER,
        )
        session.commit()
        admin, action = bootstrap_admin.provision_admin(
            session, settings, email=" ADMIN@EXAMPLE.TEST ", name="Local Administrator",
            password_supplier=lambda: "AdminPassword123!",
        )
        session.commit()
        assert action == "created"
        assert admin.email == "admin@example.test"
        assert verify_password("AdminPassword123!", admin.password_hash)
        admin_id = admin.id

        def unexpected_prompt() -> str:
            raise AssertionError("An idempotent run must not request a password")

        repeat, action = bootstrap_admin.provision_admin(
            session, settings, email="admin@example.test", name=None,
            password_supplier=unexpected_prompt,
        )
        session.commit()
        assert action == "unchanged"
        assert repeat.id == admin_id
        assert session.scalar(select(func.count()).select_from(UserModel)) == 2


def test_explicit_reset_changes_hash_clears_lockout_and_revokes_sessions(db_factory) -> None:
    settings = Settings(_env_file=None, environment="test")
    with db_factory() as session:
        admin = create_user(
            session, email="admin@example.test", name="Local Administrator",
            password="OriginalPassword123!", role=Role.ADMIN,
        )
        admin.failed_login_count = 4
        admin.locked_until = datetime.now(timezone.utc) + timedelta(minutes=10)
        old_session = AuthSessionModel(
            id="existing-session", user_id=admin.id,
            created_at=datetime.now(timezone.utc),
            expires_at=datetime.now(timezone.utc) + timedelta(hours=1),
        )
        session.add(old_session)
        session.commit()
        original_id = admin.id

        recovered, action = bootstrap_admin.provision_admin(
            session, settings, email=" ADMIN@EXAMPLE.TEST ", name=None,
            password_supplier=lambda: "ReplacementPassword123!", reset_password=True,
        )
        session.commit()
        session.refresh(old_session)
        assert action == "reset"
        assert recovered.id == original_id
        assert not verify_password("OriginalPassword123!", recovered.password_hash)
        assert verify_password("ReplacementPassword123!", recovered.password_hash)
        assert recovered.failed_login_count == 0
        assert recovered.locked_until is None
        assert old_session.revoked_at is not None
        assert session.scalar(select(func.count()).select_from(UserModel)) == 1


def test_bootstrap_refuses_role_conflicts_and_requires_flag_for_second_admin(db_factory) -> None:
    settings = Settings(_env_file=None, environment="test")
    with db_factory() as session:
        create_user(
            session, email="officer@example.test", name="Test Officer",
            password="OfficerPassword123!", role=Role.REVENUE_OFFICER,
        )
        session.commit()
        with pytest.raises(ValueError, match="not an administrator"):
            bootstrap_admin.provision_admin(
                session, settings, email="officer@example.test", name="Wrong Role",
                password_supplier=lambda: "AdminPassword123!",
            )
        with pytest.raises(ValueError, match="does not exist"):
            bootstrap_admin.provision_admin(
                session, settings, email="missing@example.test", name=None,
                password_supplier=lambda: "AdminPassword123!", reset_password=True,
            )
        create_user(
            session, email="admin@example.test", name="Local Administrator",
            password="AdminPassword123!", role=Role.ADMIN,
        )
        session.commit()
        with pytest.raises(ValueError, match="already exists"):
            bootstrap_admin.provision_admin(
                session, settings, email="other@example.test", name="Another Admin",
                password_supplier=lambda: "AdminPassword123!",
            )
        second, action = bootstrap_admin.provision_admin(
            session, settings, email="OTHER@EXAMPLE.TEST", name="Another Admin",
            password_supplier=lambda: "SecondPassword123!", allow_additional_admin=True,
        )
        session.commit()
        assert action == "created"
        assert second.email == "other@example.test"
        repeat, action = bootstrap_admin.provision_admin(
            session, settings, email="other@example.test", name=None,
            password_supplier=lambda: pytest.fail("A repeat must not prompt"),
        )
        assert action == "unchanged"
        assert repeat.id == second.id
        assert session.scalar(select(func.count()).select_from(UserModel)) == 3


def test_additional_admin_bootstrap_is_local_only(db_factory) -> None:
    production = Settings(_env_file=None, environment="production", auth_secret="x" * 32, public_app_url="https://app.example.test")
    with db_factory() as session:
        create_user(
            session, email="admin@example.test", name="Initial Administrator",
            password="AdminPassword123!", role=Role.ADMIN,
        )
        session.commit()
        with pytest.raises(ValueError, match="only in local development"):
            bootstrap_admin.provision_admin(
                session, production, email="other@example.test", name="Another Admin",
                password_supplier=lambda: pytest.fail("A denied creation must not prompt"),
                allow_additional_admin=True,
            )
        assert session.scalar(select(func.count()).select_from(UserModel)) == 1


def test_production_reset_requires_an_additional_explicit_flag(db_factory) -> None:
    settings = Settings(_env_file=None, environment="production", auth_secret="x" * 32, public_app_url="https://app.example.test")
    with db_factory() as session:
        admin = create_user(
            session, email="admin@example.test", name="Local Administrator",
            password="OriginalPassword123!", role=Role.ADMIN,
        )
        session.commit()

        def unexpected_prompt() -> str:
            raise AssertionError("A denied reset must not request a password")

        with pytest.raises(ValueError, match="--allow-production-reset"):
            bootstrap_admin.provision_admin(
                session, settings, email="admin@example.test", name=None,
                password_supplier=unexpected_prompt, reset_password=True,
            )
        assert verify_password("OriginalPassword123!", admin.password_hash)
        recovered, action = bootstrap_admin.provision_admin(
            session, settings, email="admin@example.test", name=None,
            password_supplier=lambda: "ReplacementPassword123!",
            reset_password=True, allow_production_reset=True,
        )
        session.commit()
        assert action == "reset"
        assert verify_password("ReplacementPassword123!", recovered.password_hash)


@pytest.mark.parametrize("email", [
    "foo<bar@example.test>", "(alias)bar@example.test", "bar@example.test,",
    "bar@example.test\r\nBcc:other@example.test",
])
def test_direct_user_creation_rejects_header_recipient_syntax(db_factory, email) -> None:
    with db_factory() as session:
        with pytest.raises(ValueError, match="Enter a valid email address"):
            create_user(
                session, email=email, name="Local Administrator",
                password="AdminPassword123!", role=Role.ADMIN,
            )
        assert session.scalar(select(func.count()).select_from(UserModel)) == 0


def test_cli_requires_matching_reset_email_and_does_not_print_password(
    db_factory, monkeypatch, capsys,
) -> None:
    settings = Settings(_env_file=None, environment="test")
    monkeypatch.setattr(bootstrap_admin, "SessionLocal", db_factory)
    monkeypatch.setattr(bootstrap_admin, "get_settings", lambda: settings)
    monkeypatch.setenv("BHUDRISHTI_BOOTSTRAP_PASSWORD", "OriginalPassword123!")
    monkeypatch.setattr(sys, "argv", [
        "bootstrap_admin", "--email", "admin@example.test", "--name", "Local Administrator",
    ])
    bootstrap_admin.main()
    assert "OriginalPassword123!" not in capsys.readouterr().out

    monkeypatch.setattr(sys, "argv", ["bootstrap_admin", "--email", "admin@example.test"])
    bootstrap_admin.main()
    assert "no changes made" in capsys.readouterr().out

    monkeypatch.setattr(sys, "argv", [
        "bootstrap_admin", "--email", "admin@example.test", "--reset-password",
        "--confirm-email", "another@example.test",
    ])
    with pytest.raises(SystemExit) as error:
        bootstrap_admin.main()
    assert error.value.code == 2
    with db_factory() as session:
        admin = session.scalar(select(UserModel).where(UserModel.email == "admin@example.test"))
        assert verify_password("OriginalPassword123!", admin.password_hash)

    monkeypatch.setenv("BHUDRISHTI_BOOTSTRAP_PASSWORD", "ReplacementPassword123!")
    monkeypatch.setattr(sys, "argv", [
        "bootstrap_admin", "--email", "ADMIN@example.test", "--reset-password",
        "--confirm-email", "admin@example.test",
    ])
    bootstrap_admin.main()
    output = capsys.readouterr()
    assert "ReplacementPassword123!" not in output.out + output.err
    with db_factory() as session:
        admin = session.scalar(select(UserModel).where(UserModel.email == "admin@example.test"))
        assert verify_password("ReplacementPassword123!", admin.password_hash)

    monkeypatch.setenv("BHUDRISHTI_BOOTSTRAP_PASSWORD", "SecondPassword123!")
    monkeypatch.setattr(sys, "argv", [
        "bootstrap_admin", "--email", "second@example.test", "--name", "Second Administrator",
        "--allow-additional-admin",
    ])
    bootstrap_admin.main()
    assert "SecondPassword123!" not in capsys.readouterr().out
    with db_factory() as session:
        second = session.scalar(select(UserModel).where(UserModel.email == "second@example.test"))
        assert second is not None
        assert verify_password("SecondPassword123!", second.password_hash)
        assert session.scalar(select(func.count()).select_from(UserModel)) == 2
