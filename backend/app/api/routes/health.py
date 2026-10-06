"""Liveness, document capability, and safe SMTP connection status."""

from threading import Lock, Thread
from time import monotonic
import logging

from fastapi import APIRouter, Depends, Request

from app.config import Settings, get_settings
from app.contracts.land_record import ContractModel
from app.contracts.processing import ProviderHealth
from app.services.documents.ocr import local_ocr_capabilities
from app.services.email import EmailConfigurationError, SmtpMailTransport

router = APIRouter(tags=["system"])
_logger = logging.getLogger(__name__)


class SmtpHealth(ContractModel):
    configured: bool
    connection_verified: bool | None
    checking: bool


class HealthResponse(ContractModel):
    status: str
    service: str
    version: str
    environment: str
    provider: ProviderHealth
    smtp: SmtpHealth


class SmtpHealthMonitor:
    """Cache a TLS/auth probe so liveness requests never wait on SMTP.

    The probe is run on startup and refreshed in the background after five
    minutes when health is requested. It sends no message and publishes only
    booleans; server errors and credentials are never logged or returned.
    """

    def __init__(self, settings: Settings, *, refresh_seconds: float = 300):
        self._lock = Lock()
        self._refresh_seconds = refresh_seconds
        self._verified: bool | None = None
        self._checked_at: float | None = None
        self._checking = False
        try:
            self._transport: SmtpMailTransport | None = SmtpMailTransport(settings)
            _logger.info("EMAIL_SERVICE: configured")
        except EmailConfigurationError as error:
            self._transport = None
            _logger.error("EMAIL_SERVICE: configuration missing or invalid setting=%s", error.setting)

    def start(self) -> None:
        if self._transport is None:
            return
        with self._lock:
            if self._checking or (
                self._checked_at is not None
                and monotonic() - self._checked_at < self._refresh_seconds
            ):
                return
            self._checking = True
        Thread(target=self._check, name="smtp-health-check", daemon=True).start()

    def _check(self) -> None:
        verified = False
        try:
            assert self._transport is not None
            self._transport.verify_connection()
            verified = True
        except Exception:
            # SMTP library exceptions may embed server responses or account
            # details. The health contract exposes only a success boolean.
            pass
        with self._lock:
            self._verified = verified
            self._checked_at = monotonic()
            self._checking = False

    def snapshot(self) -> SmtpHealth:
        self.start()
        with self._lock:
            return SmtpHealth(
                configured=self._transport is not None,
                connection_verified=self._verified,
                checking=self._checking,
            )


@router.get("/health", response_model=HealthResponse, summary="API liveness")
def health(request: Request, settings: Settings = Depends(get_settings)) -> HealthResponse:
    ocr = local_ocr_capabilities(settings)
    pdf_text_enabled = settings.ocr_provider in {"auto", "pdf_text"}
    ocr_enabled = settings.ocr_provider in {"auto", "tesseract"} and ocr["available"]
    if settings.ocr_provider == "pdf_text":
        message = "Embedded PDF text extraction is enabled. Scanned pages require Tesseract OCR. " + ocr["message"]
    elif settings.ocr_provider == "tesseract":
        message = "Tesseract is the configured OCR provider. " + ocr["message"]
    else:
        message = "Embedded PDF text is used first; scanned pages use Tesseract. " + ocr["message"]
    return HealthResponse(
        status="ok",
        service=settings.app_name,
        version=settings.app_version,
        environment=settings.environment,
        smtp=request.app.state.smtp_health.snapshot(),
        provider=ProviderHealth(
            provider="pdf-embedded-text + tesseract-local" if ocr_enabled and pdf_text_enabled else
                     "pdf-embedded-text" if pdf_text_enabled else "tesseract-local",
            available=pdf_text_enabled or ocr_enabled,
            deterministic=True,
            message=message,
            pdf_text_available=pdf_text_enabled,
            ocr_available=ocr_enabled,
            installed_languages=ocr["installed_languages"],
            requested_languages=ocr["requested_languages"],
            unsupported_languages=ocr["unsupported_languages"],
        ),
    )
