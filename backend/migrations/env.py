"""Alembic environment wired to the application model metadata and settings."""

from alembic import context

from app.config import get_settings
from app.db import models  # noqa: F401  (register mapped classes)
from app.db.base import Base
from app.db.session import build_engine


config = context.config
target_metadata = Base.metadata
database_url = get_settings().database_url


def run_migrations_offline() -> None:
    context.configure(
        url=database_url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        render_as_batch=database_url.startswith("sqlite"),
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    engine = build_engine(database_url)
    with engine.connect() as connection:
        sqlite = connection.dialect.name == "sqlite"
        # SQLite cannot rebuild a referenced parent table in batch mode while
        # foreign-key enforcement is enabled. Check every relationship before
        # restoring enforcement so migrations never silently leave orphans.
        if sqlite:
            connection.exec_driver_sql("PRAGMA foreign_keys=OFF")
            connection.commit()
        migration_succeeded = False
        try:
            context.configure(
                connection=connection,
                target_metadata=target_metadata,
                render_as_batch=sqlite,
            )
            with context.begin_transaction():
                context.run_migrations()
            if sqlite:
                violations = connection.exec_driver_sql("PRAGMA foreign_key_check").fetchall()
                if violations:
                    raise RuntimeError(f"Migration left {len(violations)} foreign-key violation(s).")
            migration_succeeded = True
        finally:
            if sqlite:
                if migration_succeeded:
                    connection.commit()
                else:
                    connection.rollback()
                connection.exec_driver_sql("PRAGMA foreign_keys=ON")
                connection.commit()
    engine.dispose()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
