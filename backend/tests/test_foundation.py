from __future__ import annotations

from fastapi.testclient import TestClient
from pydantic import ValidationError
import pytest

from app.config import Settings
from app.contracts.land_record import LandRecord, ValidationStatus
from app.main import app
from app.services.validation import ScoringPolicy, score_and_route


client = TestClient(app)


def test_health_reports_actual_document_capabilities_and_core_routes() -> None:
    response = client.get("/api/v1/health")
    assert response.status_code == 200
    assert response.json()["service"] == "BhuDrishti AI API"
    provider = response.json()["provider"]
    assert provider["pdfTextAvailable"] is True
    assert isinstance(provider["ocrAvailable"], bool)
    assert isinstance(provider["installedLanguages"], list)
    assert client.get("/api/v1/auth/me").status_code == 401
    paths = client.get("/openapi.json").json()["paths"]
    assert "/api/v1/auth/login" in paths
    assert "/api/v1/documents/upload" in paths
    assert "/api/v1/reviews/{record_id}/decision" in paths
    assert not any(path.startswith("/api/v1/demo") for path in paths)


def test_no_demo_identity_or_scenario_routes_are_mounted() -> None:
    assert client.post("/api/v1/auth/demo/session", json={"userId": "admin"}).status_code == 404
    assert client.get("/api/v1/demo/cases").status_code == 404
    assert client.get("/api/v1/demo/phase5/scenarios").status_code == 404


def test_canonical_contract_rejects_invented_columns() -> None:
    with pytest.raises(ValidationError):
        LandRecord.model_validate({"ownerName": "Asha", "inventedOwnershipVerdict": "legal owner"})


def test_configured_scoring_and_threshold_boundaries() -> None:
    policy = ScoringPolicy.from_settings(Settings(_env_file=None))
    assert score_and_route(100, 100, 100, policy=policy).routing == ValidationStatus.APPROVED
    assert score_and_route(60, 60, 60, policy=policy).routing == ValidationStatus.HUMAN_REVIEW
    assert score_and_route(59, 59, 59, policy=policy).routing == ValidationStatus.REJECTED
    assert score_and_route(85, 85, 85, policy=policy).routing == ValidationStatus.APPROVED
    assert score_and_route(59.999, 59.999, 59.999, policy=policy).routing == ValidationStatus.REJECTED
    assert score_and_route(84.999, 84.999, 84.999, policy=policy).routing == ValidationStatus.HUMAN_REVIEW
    assert score_and_route(90, 90, 90, warning_penalty=10, policy=policy).quality_score == 80


def test_invalid_scoring_configuration_fails_fast() -> None:
    with pytest.raises(ValidationError):
        Settings(_env_file=None, field_score_weight=0.6)
    with pytest.raises(ValueError):
        score_and_route(101, 90, 90, policy=ScoringPolicy.from_settings(Settings(_env_file=None)))
    with pytest.raises(ValidationError):
        Settings(_env_file=None, environment="production", auth_secret=None)
