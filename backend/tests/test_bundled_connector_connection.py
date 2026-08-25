from __future__ import annotations

import asyncio
from collections.abc import Callable, Mapping

import pytest
from fastapi import FastAPI, Request
from fastapi.testclient import TestClient
from test_bundled_connector_catalog import create, fixture, operator

from atlas.api.errors import register_error_handlers
from atlas.api.routes.connector_connection_tests import router
from atlas.api.security import (
    authorize_connector_target_session_create,
    authorize_connector_target_session_read,
    browser_session_subject,
)
from atlas.modules.connectors.adapters.bundled_connection_configuration_memory import (
    InMemoryBundledConnectionConfigurationRepository,
)
from atlas.modules.connectors.adapters.bundled_runtime_state_memory import (
    InMemoryBundledConnectorRuntimeStateRepository,
)
from atlas.modules.connectors.adapters.connection_test_credential_environment import (
    DevelopmentEnvironmentCredentialMaterializer,
)
from atlas.modules.connectors.adapters.connection_test_memory import (
    InMemoryConnectorConnectionTestResultRepository,
)
from atlas.modules.connectors.application.bundled_connection_configuration import (
    BundledConnectionConfigurationService,
)
from atlas.modules.connectors.application.bundled_connection_configuration_ports import (
    BundledConnectionConfigurationError,
)
from atlas.modules.connectors.application.bundled_runtime_state import (
    BundledConnectorRuntimeStateService,
)
from atlas.modules.connectors.application.connection_test import ConnectorConnectionTestService
from atlas.modules.connectors.vendors.hitachi_ops_center.ports import HitachiTransportError

RAW_AUTHORIZATION = "Basic dXNlcjpwYXNz"


class RecordingTransport:
    def __init__(
        self,
        *,
        provider: Callable[[], str],
        failure: HitachiTransportError | None = None,
    ) -> None:
        self.provider = provider
        self.failure = failure
        self.paths: list[str] = []

    async def get(self, path: str) -> Mapping[str, object]:
        self.paths.append(path)
        assert self.provider() == RAW_AUTHORIZATION
        if self.failure is not None:
            raise self.failure
        return {
            "productName": "Configuration Manager REST API",
            "apiVersion": "11.0.0",
        }


class RecordingTransportFactory:
    def __init__(self, *, failure: HitachiTransportError | None = None) -> None:
        self.failure = failure
        self.transport: RecordingTransport | None = None
        self.destination: tuple[str, int, str] | None = None

    def create(
        self,
        *,
        hostname: str,
        port: int,
        trust_profile_id: str,
        authorization_header_provider: Callable[[], str],
        timeout_seconds: float,
        maximum_response_bytes: int,
    ) -> RecordingTransport:
        assert timeout_seconds <= 30
        assert maximum_response_bytes <= 1_048_576
        self.destination = (hostname, port, trust_profile_id)
        self.transport = RecordingTransport(
            provider=authorization_header_provider, failure=self.failure
        )
        return self.transport


def build_services(monkeypatch: pytest.MonkeyPatch, *, failure=None):  # type: ignore[no-untyped-def]
    catalog_service, descriptor, instance_repository, audit = fixture()
    instance = asyncio.run(create(catalog_service, descriptor))
    configuration_repository = InMemoryBundledConnectionConfigurationRepository()
    runtime_state_repository = InMemoryBundledConnectorRuntimeStateRepository()
    configuration_service = BundledConnectionConfigurationService(
        repository=configuration_repository,
        instance_repository=instance_repository,
        audit_sink=audit,
        environment_id="environment.test",
        deployment_environment="development",
        runtime_state_repository=runtime_state_repository,
    )
    monkeypatch.setenv("ATLAS_HITACHI_TEST_AUTHORIZATION", RAW_AUTHORIZATION)
    materializer = DevelopmentEnvironmentCredentialMaterializer(
        deployment_environment="development",
        reference_environment_variables={
            "secret.hitachi.readonly": "ATLAS_HITACHI_TEST_AUTHORIZATION"
        },
    )
    transport_factory = RecordingTransportFactory(failure=failure)
    result_repository = InMemoryConnectorConnectionTestResultRepository()
    test_service = ConnectorConnectionTestService(
        configuration_repository=configuration_repository,
        result_repository=result_repository,
        instance_repository=instance_repository,
        credential_materializer=materializer,
        transport_factory=transport_factory,
        audit_sink=audit,
        environment_id="environment.test",
        deployment_environment="development",
    )
    runtime_state_service = BundledConnectorRuntimeStateService(
        repository=runtime_state_repository,
        configuration_repository=configuration_repository,
        connection_test_repository=result_repository,
        instance_repository=instance_repository,
        audit_sink=audit,
        environment_id="environment.test",
        deployment_environment="development",
    )
    return (
        instance,
        configuration_service,
        test_service,
        runtime_state_service,
        transport_factory,
        audit,
        instance_repository,
    )


def build_app(configuration_service, test_service, runtime_state_service) -> FastAPI:  # type: ignore[no-untyped-def]
    app = FastAPI()
    app.state.bundled_connection_configuration_service = configuration_service
    app.state.connector_connection_test_service = test_service
    app.state.bundled_connector_runtime_state_service = runtime_state_service

    @app.middleware("http")
    async def correlation_id(request: Request, call_next):  # type: ignore[no-untyped-def]
        request.state.correlation_id = "cor_connection_test"
        return await call_next(request)

    app.dependency_overrides[browser_session_subject] = operator
    app.dependency_overrides[authorize_connector_target_session_create] = lambda: object()
    app.dependency_overrides[authorize_connector_target_session_read] = lambda: object()
    app.include_router(router, prefix="/api/v1")
    register_error_handlers(app)
    return app


def test_configure_get_and_read_only_connection_test_hide_raw_secret(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    instance, configuration_service, test_service, runtime_service, factory, audit, _ = (
        build_services(monkeypatch)
    )
    client = TestClient(build_app(configuration_service, test_service, runtime_service))
    base = f"/api/v1/connectors/bundled-instances/{instance.instance_id}"
    payload = {
        "hostname": "opscenter.storage.example",
        "port": 23451,
        "trust_profile_id": "trust.system-ca",
        "secret_reference_id": "secret.hitachi.readonly",
    }

    configured = client.put(f"{base}/connection-configuration", json=payload)
    fetched = client.get(f"{base}/connection-configuration")
    tested = client.post(f"{base}/connection-tests")
    latest = client.get(f"{base}/connection-tests/latest")

    assert configured.status_code == 200 and fetched.status_code == 200
    assert configured.json()["data"]["protocol"] == "https"
    assert configured.json()["data"]["secret_material_stored"] is False
    assert tested.status_code == 200
    assert tested.json()["data"]["result_code"] == "hitachi_api_compatible"
    assert tested.json()["data"]["infrastructure_mutation_performed"] is False
    assert latest.status_code == 200
    assert latest.json()["data"] == tested.json()["data"]
    assert latest.headers["cache-control"] == "no-store"
    assert factory.transport is not None and factory.transport.paths == ["/configuration/version"]
    assert RAW_AUTHORIZATION not in tested.text
    assert RAW_AUTHORIZATION not in repr(audit.records)


def test_latest_connection_test_is_not_found_before_first_result(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    instance, configuration_service, test_service, runtime_service, _, _, _ = build_services(
        monkeypatch
    )
    client = TestClient(build_app(configuration_service, test_service, runtime_service))

    response = client.get(
        f"/api/v1/connectors/bundled-instances/{instance.instance_id}/connection-tests/latest"
    )

    assert response.status_code == 404
    assert response.json()["code"] == "connection_test_result_not_found"


def test_credential_unavailable_failure_is_stored_as_latest_without_secret(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    instance, configuration_service, test_service, runtime_service, _, _, _ = build_services(
        monkeypatch
    )
    client = TestClient(build_app(configuration_service, test_service, runtime_service))
    base = f"/api/v1/connectors/bundled-instances/{instance.instance_id}"
    configured = client.put(
        f"{base}/connection-configuration",
        json={
            "hostname": "opscenter.storage.example",
            "port": 23451,
            "trust_profile_id": "trust.system-ca",
            "secret_reference_id": "secret.hitachi.readonly",
        },
    )
    assert configured.status_code == 200
    monkeypatch.delenv("ATLAS_HITACHI_TEST_AUTHORIZATION")

    tested = client.post(f"{base}/connection-tests")
    latest = client.get(f"{base}/connection-tests/latest")

    assert tested.status_code == 200
    assert tested.json()["data"]["result_code"] == "connection_test_credentials_unavailable"
    assert tested.json()["data"]["managed_infrastructure_contacted"] is False
    assert latest.status_code == 200
    assert latest.json()["data"] == tested.json()["data"]
    assert RAW_AUTHORIZATION not in tested.text
    assert RAW_AUTHORIZATION not in latest.text


def test_each_connection_test_is_stored_and_latest_replaces_previous_result(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    instance, configuration_service, test_service, runtime_service, factory, _, _ = build_services(
        monkeypatch
    )
    client = TestClient(build_app(configuration_service, test_service, runtime_service))
    base = f"/api/v1/connectors/bundled-instances/{instance.instance_id}"
    configured = client.put(
        f"{base}/connection-configuration",
        json={
            "hostname": "opscenter.storage.example",
            "port": 23451,
            "trust_profile_id": "trust.system-ca",
            "secret_reference_id": "secret.hitachi.readonly",
        },
    )
    assert configured.status_code == 200

    first = client.post(f"{base}/connection-tests")
    factory.failure = HitachiTransportError(
        "target_unavailable", "hidden target detail", retryable=True
    )
    second = client.post(f"{base}/connection-tests")
    latest = client.get(f"{base}/connection-tests/latest")

    assert first.json()["data"]["outcome"] == "passed"
    assert second.json()["data"]["result_code"] == "target_unavailable"
    assert latest.json()["data"] == second.json()["data"]
    assert latest.json()["data"]["test_id"] != first.json()["data"]["test_id"]
    assert "hidden target detail" not in latest.text


def test_configuration_rejects_url_and_secret_material_field(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    instance, configuration_service, test_service, runtime_service, _, _, _ = build_services(
        monkeypatch
    )
    client = TestClient(build_app(configuration_service, test_service, runtime_service))
    base = f"/api/v1/connectors/bundled-instances/{instance.instance_id}"
    payload = {
        "hostname": "http://opscenter.storage.example",
        "port": 23451,
        "trust_profile_id": "trust.system-ca",
        "secret_reference_id": "secret.hitachi.readonly",
        "secret": RAW_AUTHORIZATION,
    }

    response = client.put(f"{base}/connection-configuration", json=payload)

    assert response.status_code == 422
    assert RAW_AUTHORIZATION not in response.text


def test_failure_is_minimized_and_production_is_fail_closed(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    failure = HitachiTransportError(
        "target_unavailable", "internal target detail must stay hidden", retryable=True
    )
    (
        instance,
        configuration_service,
        test_service,
        _,
        _,
        audit,
        instance_repository,
    ) = build_services(monkeypatch, failure=failure)
    asyncio.run(
        configuration_service.configure(
            actor=operator(),
            instance_id=instance.instance_id,
            hostname="opscenter.storage.example",
            port=23451,
            trust_profile_id="trust.system-ca",
            secret_reference_id="secret.hitachi.readonly",
            correlation_id="cor_configure",
        )
    )

    result = asyncio.run(
        test_service.test(
            actor=operator(),
            instance_id=instance.instance_id,
            correlation_id="cor_test",
        )
    )
    assert result.result_code == "target_unavailable" and result.retryable
    assert "internal target detail" not in repr(result)
    assert "internal target detail" not in repr(audit.records)

    production_service = BundledConnectionConfigurationService(
        repository=configuration_service.repository,
        instance_repository=instance_repository,
        audit_sink=audit,
        environment_id="environment.test",
        deployment_environment="production",
    )
    with pytest.raises(BundledConnectionConfigurationError, match="development_only"):
        asyncio.run(
            production_service.get(
                actor=operator(),
                instance_id=instance.instance_id,
                correlation_id="cor_production",
            )
        )


def test_read_only_runtime_enable_disable_and_configuration_invalidation(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    (
        instance,
        configuration_service,
        test_service,
        runtime_service,
        _,
        audit,
        _,
    ) = build_services(monkeypatch)
    monkeypatch.setenv("ATLAS_HITACHI_OPSCENTER_PROD", RAW_AUTHORIZATION)
    client = TestClient(build_app(configuration_service, test_service, runtime_service))
    base = f"/api/v1/connectors/bundled-instances/{instance.instance_id}"
    configuration = {
        "hostname": "opscenter.storage.example",
        "port": 23451,
        "trust_profile_id": "trust.system-ca",
        "secret_reference_id": "secret.hitachi.opscenter_prod",
    }

    initial = client.get(f"{base}/runtime-state")
    configured = client.put(f"{base}/connection-configuration", json=configuration)
    tested = client.post(f"{base}/connection-tests")
    enabled = client.post(f"{base}/enable", json={"acknowledged_read_only_operation": True})
    reconfigured = client.put(
        f"{base}/connection-configuration",
        json={**configuration, "hostname": "opscenter-new.storage.example"},
    )
    invalidated = client.get(f"{base}/runtime-state")
    retested = client.post(f"{base}/connection-tests")
    reenabled = client.post(f"{base}/enable", json={"acknowledged_read_only_operation": True})
    disabled = client.post(
        f"{base}/disable",
        json={
            "reason": "Pause scheduled health polling during storage maintenance.",
            "acknowledged_runtime_stop": True,
        },
    )

    assert initial.status_code == 200
    assert initial.json()["data"]["state"] == "disabled"
    assert initial.json()["data"]["version"] == 0
    assert configured.status_code == tested.status_code == enabled.status_code == 200
    assert enabled.json()["data"]["state"] == "enabled_read_only"
    assert enabled.json()["data"]["managed_infrastructure_contacted"] is False
    assert reconfigured.status_code == 200
    assert invalidated.json()["data"]["state"] == "disabled"
    assert invalidated.json()["data"]["version"] == 0
    assert retested.json()["data"]["outcome"] == "passed"
    assert reenabled.json()["data"]["state"] == "enabled_read_only"
    assert disabled.status_code == 200
    assert disabled.json()["data"]["state"] == "disabled"
    assert disabled.json()["data"]["version"] == 2
    assert disabled.json()["data"]["infrastructure_mutation_performed"] is False
    assert {
        "bundled_runtime_enabled_read_only",
        "bundled_runtime_disabled",
    } <= {record.result_code for record in audit.records}
