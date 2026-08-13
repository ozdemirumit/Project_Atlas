from __future__ import annotations

import asyncio
from dataclasses import replace
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from test_browser_sessions import BasicTestIdentityProvider, login, settings
from test_instance_creation import (
    create_instance,
    instance_fixture,
    instance_operator,
)
from test_package_acquisition import CollectingAuditSink
from test_target_configuration import bind_target, target_configuration_fixture

from atlas.api.app import create_app
from atlas.modules.connectors.adapters.target_configuration_memory import (
    InMemoryConnectorTargetConfigurationRepository,
)
from atlas.modules.connectors.application.instance_creation_ports import (
    ConnectorInstanceCreationError,
)
from atlas.modules.connectors.application.instance_lifecycle import (
    ConnectorInstanceLifecycleService,
)
from atlas.modules.identity.domain.models import AssuranceLevel, AuthenticationMethod


@pytest.mark.asyncio
async def test_development_password_session_supports_instance_lifecycle() -> None:
    audit = CollectingAuditSink()
    service, _, _, _, installation, policy = await instance_fixture()
    actor = replace(
        instance_operator(),
        authentication_method=AuthenticationMethod.DEVELOPMENT,
        assurance_level=AssuranceLevel.DEVELOPMENT,
    )
    record = await create_instance(service, installation, policy, actor=actor)
    lifecycle = ConnectorInstanceLifecycleService(
        repository=service.repository,
        target_repository=InMemoryConnectorTargetConfigurationRepository(),
        audit_sink=audit,
        environment_id=record.environment_id,
        clock=lambda: record.created_at,
    )
    active = await lifecycle.list(
        actor=actor,
        lifecycle="active",
        query="storage",
        correlation_id="cor_instance_list",
    )
    retired = await lifecycle.retire(
        actor=actor,
        record_id=record.record_id,
        expected_version=record.version,
        reason="The unused connector identity is no longer required in this environment.",
        acknowledged_retirement_preserves_history_and_performs_no_runtime_action=True,
        idempotency_key="connector-instance-retire-001",
        correlation_id="cor_instance_retire",
    )
    replay = await lifecycle.retire(
        actor=actor,
        record_id=record.record_id,
        expected_version=record.version,
        reason="The unused connector identity is no longer required in this environment.",
        acknowledged_retirement_preserves_history_and_performs_no_runtime_action=True,
        idempotency_key="connector-instance-retire-001",
        correlation_id="cor_instance_retire_replay",
    )
    retired_inventory = await lifecycle.list(
        actor=actor,
        lifecycle="retired",
        query="",
        correlation_id="cor_instance_retired_list",
    )

    assert active == (record,)
    assert retired.record_id == record.record_id
    assert retired.version == 2 and retired.instance_state == "retired"
    assert retired.eligible_for_configuration_governance is False
    assert retired.retired_by == actor.subject_id
    assert retired.retirement_reason is not None
    assert replay.reused is True and replay.canonical_digest == retired.canonical_digest
    assert retired_inventory[0].record_id == record.record_id
    assert not retired.target_configured and not retired.credentials_resolved
    assert not retired.connector_enabled and not retired.runtime_trust_granted
    assert not retired.execution_authorized and not retired.infrastructure_mutation_performed
    with pytest.raises(ConnectorInstanceCreationError, match="source_binding_invalid"):
        await service.target_configuration_source(record_id=record.record_id)
    assert {item.result_code for item in audit.records} >= {
        "connector_instances_listed",
        "connector_instance_retirement_requested",
        "connector_instance_retired",
    }


@pytest.mark.asyncio
async def test_instance_retirement_rejects_configured_or_stale_instance() -> None:
    (
        target_service,
        instance_service,
        _,
        _,
        instance,
        profile,
        policy,
    ) = await target_configuration_fixture()
    await bind_target(target_service, instance, profile, policy)
    lifecycle = ConnectorInstanceLifecycleService(
        repository=instance_service.repository,
        target_repository=target_service.repository,
        audit_sink=CollectingAuditSink(),
        environment_id=instance.environment_id,
        clock=lambda: instance.created_at,
    )

    with pytest.raises(ConnectorInstanceCreationError, match="version_conflict"):
        await lifecycle.retire(
            actor=instance_operator(),
            record_id=instance.record_id,
            expected_version=99,
            reason="Retire only after the complete governed decommissioning sequence finishes.",
            acknowledged_retirement_preserves_history_and_performs_no_runtime_action=True,
            idempotency_key="connector-instance-retire-stale",
            correlation_id="cor_instance_retire_stale",
        )
    with pytest.raises(ConnectorInstanceCreationError, match="requires_decommissioning"):
        await lifecycle.retire(
            actor=instance_operator(),
            record_id=instance.record_id,
            expected_version=1,
            reason="Retire only after the complete governed decommissioning sequence finishes.",
            acknowledged_retirement_preserves_history_and_performs_no_runtime_action=True,
            idempotency_key="connector-instance-retire-configured",
            correlation_id="cor_instance_retire_configured",
        )


def test_installed_mcp_api_lists_adds_and_retires_without_hard_delete(tmp_path: Path) -> None:
    (
        service,
        installation_service,
        registration_service,
        publication_service,
        installation,
        policy,
    ) = asyncio.run(instance_fixture())
    subject = instance_operator()
    app_settings = settings(
        development_subject_id=subject.subject_id,
        mcp_builder_generation_root=tmp_path / "mcp-builder-generations",
    )
    create_payload = {
        "schema_version": "atlas.connector-instance-creation-input.v1",
        "source_installation_receipt_id": installation.receipt_id,
        "source_installation_receipt_digest": installation.canonical_digest,
        "package_digest": installation.package_digest,
        "instance_key": "storage-managed",
        "display_name": "Managed storage MCP",
        "instance_policy_id": policy.policy_id,
        "instance_policy_digest": policy.canonical_digest,
        "purpose": "Create a disabled MCP identity for governed lifecycle management.",
        "acknowledged_instance_is_disabled_and_grants_no_target_or_runtime_authority": True,
    }
    with TestClient(
        create_app(
            app_settings,
            identity_provider=BasicTestIdentityProvider(subject),
            registry_publication_service=publication_service,
            package_registration_service=registration_service,
            package_installation_service=installation_service,
            connector_instance_creation_service=service,
        )
    ) as client:
        login_response = login(client)
        csrf = login_response.headers["X-CSRF-Token"]
        packages = client.get("/api/v1/connectors/package-installation-receipts")
        policies = client.get("/api/v1/connectors/instances/creation-policies")
        created = client.post(
            "/api/v1/connectors/instances",
            json=create_payload,
            headers={"X-CSRF-Token": csrf, "Idempotency-Key": "instance-managed-create"},
        )
        record = created.json()["data"]
        active = client.get("/api/v1/connectors/instances?lifecycle=active&query=managed")
        retired = client.post(
            f"/api/v1/connectors/instances/{record['record_id']}/retirements",
            json={
                "schema_version": "atlas.connector-instance-retirement-input.v1",
                "expected_version": record["version"],
                "reason": "The unused MCP identity is retired while all history remains available.",
                "acknowledged_retirement_preserves_history_and_performs_no_runtime_action": True,
            },
            headers={"X-CSRF-Token": csrf, "Idempotency-Key": "instance-managed-retire"},
        )
        retired_inventory = client.get("/api/v1/connectors/instances?lifecycle=retired")
        hard_delete = client.delete(f"/api/v1/connectors/instances/{record['record_id']}")

    assert packages.status_code == 200
    assert packages.json()["data"][0]["receipt_id"] == installation.receipt_id
    assert '"artifact_reference":' not in packages.text
    assert policies.status_code == 200
    assert policies.json()["data"][0]["canonical_digest"] == policy.canonical_digest
    assert "signed_by" not in policies.text
    assert created.status_code == 201 and active.status_code == 200
    assert active.json()["data"][0]["display_name"] == "Managed storage MCP"
    assert retired.status_code == 200
    assert retired.json()["data"]["instance_state"] == "retired"
    assert retired.json()["data"]["version"] == 2
    assert retired_inventory.json()["data"][0]["record_id"] == record["record_id"]
    assert hard_delete.status_code == 405
    rendered = retired.text.lower()
    for hidden in (
        "request_fingerprint",
        "idempotency_key",
        "target_endpoint",
        "secret_reference",
        "password",
    ):
        assert hidden not in rendered
