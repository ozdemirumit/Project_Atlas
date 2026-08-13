from fastapi.testclient import TestClient

from atlas.api.app import create_app
from atlas.core.config import Settings


def test_liveness_returns_service_version_and_correlation() -> None:
    with TestClient(create_app(Settings(environment="test"))) as client:
        response = client.get("/health/live")

    assert response.status_code == 200
    assert response.json() == {
        "status": "alive",
        "service": "project-atlas-api",
        "version": "0.1.0",
        "components": [],
    }
    assert response.headers["X-Correlation-ID"].startswith("cor_")


def test_readiness_discloses_disabled_optional_database() -> None:
    with TestClient(create_app(Settings(environment="test"))) as client:
        response = client.get("/health/ready")

    assert response.status_code == 200
    assert response.json()["status"] == "ready"
    assert response.json()["components"] == [
        {
            "name": "database",
            "status": "disabled",
            "required": False,
            "code": "database_not_configured",
        }
    ]


def test_required_database_without_url_is_not_ready() -> None:
    settings = Settings(environment="test", database_required=True)
    with TestClient(create_app(settings)) as client:
        response = client.get("/health/ready")

    assert response.status_code == 503
    assert response.json()["status"] == "not_ready"
    assert response.json()["components"][0]["code"] == "database_url_missing"


def test_production_without_database_is_not_ready_without_memory_fallback() -> None:
    settings = Settings(
        environment="production",
        enable_api_docs=False,
        database_required=False,
    )
    assert settings.database_required is True

    with TestClient(create_app(settings)) as client:
        response = client.get("/health/ready")

    assert response.status_code == 503
    assert response.json()["components"][0]["code"] == "database_url_missing"


def test_platform_status_uses_api_envelope() -> None:
    with TestClient(create_app(Settings(environment="test"))) as client:
        response = client.get(
            "/api/v1/platform/status",
            headers={"X-Correlation-ID": "cor_test-123"},
        )

    payload = response.json()
    assert response.status_code == 200
    assert payload["data"]["status"] == "healthy"
    assert payload["data"]["environment"] == "test"
    assert payload["meta"]["correlation_id"] == "cor_test-123"
    assert response.headers["X-Correlation-ID"] == "cor_test-123"


def test_invalid_correlation_identifier_returns_safe_problem_details() -> None:
    with TestClient(create_app(Settings(environment="test"))) as client:
        response = client.get("/health/live", headers={"X-Correlation-ID": "invalid value"})

    payload = response.json()
    assert response.status_code == 400
    assert response.headers["content-type"] == "application/problem+json"
    assert payload["code"] == "invalid_correlation_id"
    assert payload["correlation_id"].startswith("cor_")
    assert "invalid value" not in response.text
