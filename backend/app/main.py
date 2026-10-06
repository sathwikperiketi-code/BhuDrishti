"""FastAPI composition root."""

from __future__ import annotations

from contextlib import asynccontextmanager
import logging

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from sqlalchemy.exc import InterfaceError, OperationalError, TimeoutError as DatabaseTimeoutError

from app.api.routes import auth, documents, health, phase4, phase5, review
from app.config import get_settings

_logger = logging.getLogger(__name__)
_account_email_handler = logging.StreamHandler()
_account_email_handler.setFormatter(logging.Formatter("%(levelname)s %(name)s: %(message)s"))


def create_app() -> FastAPI:
    # These modules log only fixed event labels and safe diagnostic codes.
    # Uvicorn's default root logging would otherwise hide SMTP success events.
    for logger_name in ("app.services.email.service", "app.api.routes.auth", "app.api.routes.health"):
        account_email_logger = logging.getLogger(logger_name)
        account_email_logger.setLevel(logging.INFO)
        account_email_logger.addHandler(_account_email_handler)
    settings = get_settings()
    smtp_health = health.SmtpHealthMonitor(settings)

    @asynccontextmanager
    async def lifespan(_application: FastAPI):
        smtp_health.start()
        yield

    application = FastAPI(
        title=settings.app_name,
        version=settings.app_version,
        description=(
            "AI-assisted land-record digitization prototype. Validation checks support "
            "human verification and do not determine legal ownership."
        ),
        lifespan=lifespan,
    )
    application.state.smtp_health = smtp_health
    application.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=True,
        allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
        allow_headers=["*"],
    )

    async def database_unavailable(_request: Request, error: Exception) -> JSONResponse:
        # SQLAlchemy exception strings can include SQL parameters/passwords.
        # Log the failure class and numeric driver code, never its raw text.
        original = getattr(error, "orig", None)
        driver_code = getattr(original, "sqlite_errorcode", None)
        _logger.error(
            "Database unavailable error_type=%s driver_error_type=%s driver_code=%s",
            type(error).__name__, type(original).__name__ if original else "none",
            driver_code if isinstance(driver_code, int) else "none",
        )
        return JSONResponse(
            status_code=503,
            content={"detail": "The account database is unavailable. Please try again later."},
            headers={"X-BhuDrishti-Error-Code": "DATABASE_UNAVAILABLE"},
        )

    for database_error in (OperationalError, InterfaceError, DatabaseTimeoutError):
        application.add_exception_handler(database_error, database_unavailable)

    @application.exception_handler(RequestValidationError)
    async def validation_error_without_submitted_values(
        _request: Request, error: RequestValidationError,
    ) -> JSONResponse:
        # FastAPI's default 422 body includes Pydantic's `input` value. On
        # account routes that value can be a password, reset token, or the
        # complete submitted object. Return only safe validation metadata.
        detail = [
            {"type": item["type"], "loc": item["loc"], "msg": item["msg"]}
            for item in error.errors()
        ]
        return JSONResponse(status_code=422, content={"detail": detail})

    application.include_router(health.router, include_in_schema=False)
    application.include_router(health.router, prefix=settings.api_prefix)
    application.include_router(auth.router, prefix=settings.api_prefix)
    application.include_router(documents.router, prefix=settings.api_prefix)
    application.include_router(review.router, prefix=settings.api_prefix)
    application.include_router(phase4.audit_router, prefix=settings.api_prefix)
    application.include_router(phase4.records_router, prefix=settings.api_prefix)
    application.include_router(phase4.gis_router, prefix=settings.api_prefix)
    application.include_router(phase4.notifications_router, prefix=settings.api_prefix)
    application.include_router(phase5.router, prefix=settings.api_prefix)
    return application


app = create_app()
