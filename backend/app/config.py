"""Environment-backed application settings.

The defaults keep a local prototype runnable while remaining compatible with a
PostgreSQL deployment through ``BHUDRISHTI_DATABASE_URL``.
"""

from __future__ import annotations

from functools import lru_cache
from ipaddress import ip_address
from pathlib import Path
from urllib.parse import urlsplit

from pydantic import AliasChoices, Field, SecretStr, field_validator, model_validator
from pydantic_settings import BaseSettings, PydanticBaseSettingsSource, SettingsConfigDict


_BACKEND_DIR = Path(__file__).resolve().parents[1]
_REPO_ROOT = _BACKEND_DIR.parent
_LOCAL_DATABASE_URL = f"sqlite:///{(_BACKEND_DIR / 'bhudrishti.db').as_posix()}"


class Settings(BaseSettings):
    app_name: str = "BhuDrishti AI API"
    app_version: str = "0.1.0"
    environment: str = "development"
    api_prefix: str = "/api/v1"
    database_url: str = _LOCAL_DATABASE_URL
    cors_origins: list[str] = Field(default_factory=lambda: ["http://localhost:5173", "http://127.0.0.1:5173"])
    auth_provider: str = "local"
    auth_secret: str | None = None
    auth_session_hours: int = Field(default=8, ge=1, le=168)
    public_app_url: str = Field(
        default="http://localhost:5173",
        validation_alias=AliasChoices("VITE_APP_URL", "BHUDRISHTI_PUBLIC_APP_URL"),
    )

    # Support the project's existing plain SMTP_* environment variable contract
    # while also accepting BHUDRISHTI_SMTP_* in deployment environments.
    smtp_host: str | None = Field(default=None, validation_alias=AliasChoices("SMTP_HOST", "BHUDRISHTI_SMTP_HOST"))
    smtp_port: int = Field(default=587, ge=1, le=65535, validation_alias=AliasChoices("SMTP_PORT", "BHUDRISHTI_SMTP_PORT"))
    smtp_secure: bool = Field(default=False, validation_alias=AliasChoices("SMTP_SECURE", "BHUDRISHTI_SMTP_SECURE"))
    smtp_user: str | None = Field(default=None, validation_alias=AliasChoices("SMTP_USER", "BHUDRISHTI_SMTP_USER"))
    smtp_pass: SecretStr | None = Field(default=None, validation_alias=AliasChoices("SMTP_PASS", "BHUDRISHTI_SMTP_PASS"))
    smtp_from: str | None = Field(default=None, validation_alias=AliasChoices("SMTP_FROM", "BHUDRISHTI_SMTP_FROM"))

    document_storage_dir: str = "./document_storage"
    upload_max_bytes: int = Field(default=20 * 1024 * 1024, ge=1024)
    geometry_upload_max_bytes: int = Field(default=1024 * 1024, ge=1024, le=10 * 1024 * 1024)
    upload_max_pages: int = Field(default=25, ge=1, le=200)
    upload_max_total_pixels: int = Field(default=80_000_000, ge=1_000_000)
    render_dpi: int = Field(default=120, ge=72, le=240)
    ocr_provider: str = "auto"
    ocr_language: str = "eng"
    tesseract_cmd: str | None = None
    preprocess_grayscale: bool = True
    preprocess_denoise: bool = True
    preprocess_contrast: bool = True
    preprocess_deskew: bool = True
    preprocess_crop: bool = False

    field_score_weight: float = Field(default=0.5, ge=0, le=1)
    record_score_weight: float = Field(default=0.3, ge=0, le=1)
    cross_system_score_weight: float = Field(default=0.2, ge=0, le=1)
    reject_threshold: float = Field(default=60, ge=0, le=100)
    approve_threshold: float = Field(default=85, ge=0, le=100)

    model_config = SettingsConfigDict(
        env_prefix="BHUDRISHTI_",
        # Resolve configuration independently of the shell's working directory.
        # Vite reads the same repository .env for the canonical frontend URL.
        env_file=(_BACKEND_DIR / ".env", _REPO_ROOT / ".env"),
        env_file_encoding="utf-8",
        populate_by_name=True,
        extra="ignore",
        # Startup validation errors may otherwise include the raw combined
        # environment input, including SMTP credentials, in their traceback.
        hide_input_in_errors=True,
    )

    @classmethod
    def settings_customise_sources(
        cls,
        settings_cls: type[BaseSettings],
        init_settings: PydanticBaseSettingsSource,
        env_settings: PydanticBaseSettingsSource,
        dotenv_settings: PydanticBaseSettingsSource,
        file_secret_settings: PydanticBaseSettingsSource,
    ):
        def canonical_app_url(source: PydanticBaseSettingsSource):
            def read_source():
                values = source()
                # Normalize aliases before sources are merged. Otherwise a legacy
                # process override can lose to VITE_APP_URL in a lower-priority
                # dotenv file, breaking explicitly isolated QA deployments.
                keys = ("VITE_APP_URL", "BHUDRISHTI_PUBLIC_APP_URL", "public_app_url")
                present = next((key for key in keys if key in values), None)
                if present is not None:
                    value = values[present]
                    for key in keys:
                        values.pop(key, None)
                    values["VITE_APP_URL"] = value
                return values

            return read_source

        return tuple(canonical_app_url(source) for source in (
            init_settings, env_settings, dotenv_settings, file_secret_settings,
        ))

    @field_validator("public_app_url")
    @classmethod
    def validate_public_app_url(cls, value: str) -> str:
        """Require a clean HTTP(S) origin or path prefix for emailed links."""
        clean = value.strip()
        try:
            parts = urlsplit(clean)
            valid = (
                parts.scheme in {"http", "https"}
                and bool(parts.hostname)
                and parts.username is None
                and parts.password is None
                and not parts.query
                and not parts.fragment
                and not any(char.isspace() for char in clean)
            )
            # Force validation of malformed numeric ports, which urlsplit
            # otherwise leaves uninterpreted until `.port` is accessed.
            _ = parts.port
        except ValueError:
            valid = False
        if not valid:
            raise ValueError("VITE_APP_URL must be an absolute HTTP(S) base URL without a query or fragment")
        return clean.rstrip("/")

    @model_validator(mode="after")
    def validate_scoring_configuration(self) -> "Settings":
        if "*" in self.cors_origins:
            raise ValueError("CORS origins must be explicit when authenticated browser requests are enabled")
        if self.auth_provider != "local":
            raise ValueError("Unsupported authentication provider; configure 'local' until an external adapter is installed")
        if self.auth_secret is not None and len(self.auth_secret) < 32:
            raise ValueError("BHUDRISHTI_AUTH_SECRET must contain at least 32 characters")
        if self.environment.lower() not in {"development", "test", "testing"} and not self.auth_secret:
            raise ValueError("BHUDRISHTI_AUTH_SECRET is required outside local development and tests")
        if self.environment.lower() not in {"development", "test", "testing"}:
            public_url = urlsplit(self.public_app_url)
            hostname = (public_url.hostname or "").lower().rstrip(".")
            local_host = hostname == "localhost" or hostname.endswith(".localhost")
            try:
                local_host = local_host or ip_address(hostname).is_loopback
            except ValueError:
                pass
            if public_url.scheme != "https" or local_host:
                raise ValueError("VITE_APP_URL must use a deployed HTTPS frontend URL outside local development and tests")
        total = (
            self.field_score_weight
            + self.record_score_weight
            + self.cross_system_score_weight
        )
        if abs(total - 1.0) > 1e-6:
            raise ValueError("field, record and cross-system score weights must sum to 1")
        if self.reject_threshold >= self.approve_threshold:
            raise ValueError("reject_threshold must be lower than approve_threshold")
        return self


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()
