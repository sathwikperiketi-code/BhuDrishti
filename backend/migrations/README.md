# Database migrations

Run from `backend/` with `alembic upgrade head`. The database URL comes from
`BHUDRISHTI_DATABASE_URL`; the local default is SQLite. For PostgreSQL install
the `postgres` optional dependency and set a `postgresql+psycopg://` URL.

Versioned migrations own schema changes. `app.db.session.init_db()` is available
for isolated tests and local experiments, not for normal application startup.
