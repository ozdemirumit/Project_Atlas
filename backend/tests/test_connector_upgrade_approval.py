from __future__ import annotations

import asyncio
from dataclasses import asdict
from datetime import timedelta
from pathlib import Path
from typing import cast

import pytest
from fastapi.testclient import TestClient
from test_browser_sessions import BasicTestIdentityProvider, login, settings
from test_connector_upgrade_readiness import UpgradePackageSource, upgrade_package
from test_instance_creation import create_instance, instance_fixture, instance_operator
from test_package_acquisition import CollectingAuditSink
from test_target_configuration import bind_target, target_configuration_fixture

from atlas.api.app import create_app
from atlas.modules.connectors.adapters.target_configuration_memory import (
    InMemoryConnectorTargetConfigurationRepository,
)
from atlas.modules.connectors.adapters.upgrade_approval_memory import (
    InMemoryConnectorUpgradeApprovalPolicySource,
    InMemoryConnectorUpgradeApprovalRepository,
)
from atlas.modules.connectors.adapters.upgrade_approval_postgres import (
    PostgreSQLConnectorUpgradeApprovalRepository,
)
from atlas.modules.connectors.application.instance_creation import (
    ConnectorInstanceCreationService,
)
from atlas.modules.connectors.application.package_installation import PackageInstallationService
from atlas.modules.connectors.application.package_registration import PackageRegistrationService
from atlas.modules.connectors.application.registry_publication import RegistryPublicationService
from atlas.modules.connectors.application.upgrade_approval import (
    ConnectorUpgradeApprovalService,
    build_development_connector_upgrade_approval_policy,
)
from atlas.modules.connectors.application.upgrade_approval_ports import (
    ConnectorUpgradeApprovalError,
)
from atlas.modules.connectors.application.upgrade_readiness import (
    ConnectorUpgradeReadinessService,
)
from atlas.modules.connectors.domain.instance_creation import ConnectorInstanceRecord
from atlas.modules.connectors.domain.package_installation import (
    ConnectorPackageInstallationReceipt,
)


async def approval_fixture() -> tuple[
    ConnectorUpgradeApprovalService,
    ConnectorUpgradeReadinessService,
    ConnectorInstanceCreationService,
    PackageInstallationService,
    PackageRegistrationService,
    RegistryPublicationService,
    tuple[ConnectorInstanceRecord, ConnectorPackageInstallationReceipt],
    CollectingAuditSink,
]:
    audit = CollectingAuditSink()
    (
        instance_service,
        package_service,
        registration_service,
        publication_service,
        installation,
        policy,
    ) = await instance_fixture()
    instance = await create_instance(instance_service, installation, policy)
    (
        current_receipt,
        _,
        current_registration,
        _,
    ) = await package_service.connector_instance_creation_source(receipt_id=installation.receipt_id)
    candidate_receipt, candidate_registration = upgrade_package(
        current_receipt, current_registration
    )
    now = installation.installed_at + timedelta(hours=2)
    upgrade_service = ConnectorUpgradeReadinessService(
        instance_repository=instance_service.repository,
        target_repository=InMemoryConnectorTargetConfigurationRepository(),
        package_source=UpgradePackageSource(
            ((current_receipt, current_registration), (candidate_receipt, candidate_registration))
        ),
        audit_sink=audit,
        environment_id=instance.environment_id,
        clock=lambda: now,
    )
    approval_policy = build_development_connector_upgrade_approval_policy(
        organization_id=instance.organization_id,
        environment_id=instance.environment_id,
        issued_at=now - timedelta(hours=1),
        expires_at=now + timedelta(days=1),
    )
    service = ConnectorUpgradeApprovalService(
        repository=InMemoryConnectorUpgradeApprovalRepository(),
        policy_source=InMemoryConnectorUpgradeApprovalPolicySource((approval_policy,)),
        upgrade_service=upgrade_service,
        audit_sink=audit,
        environment_id=instance.environment_id,
        clock=lambda: now,
    )
    return (
        service,
        upgrade_service,
        instance_service,
        package_service,
        registration_service,
        publication_service,
        (instance, candidate_receipt),
        audit,
    )


@pytest.mark.asyncio
async def test_upgrade_approval_request_binds_exact_plan_without_granting_authority() -> None:
    service, upgrade_service, _, _, _, _, sources, audit = await approval_fixture()
    instance, candidate_receipt = sources
    actor = instance_operator()
    plan = await upgrade_service.plan(
        actor=actor,
        record_id=instance.record_id,
        candidate_receipt_id=candidate_receipt.receipt_id,
        correlation_id="correlation.connector-upgrade-plan-source",
    )

    request = await service.create(
        actor=actor,
        record_id=instance.record_id,
        candidate_receipt_id=candidate_receipt.receipt_id,
        source_plan_digest=plan.canonical_digest,
        purpose="Submit this exact connector upgrade plan for independent human review.",
        acknowledged_request_is_not_approval_and_grants_no_execution_authority=True,
        idempotency_key="connector-upgrade-approval-001",
        correlation_id="correlation.connector-upgrade-approval",
    )
    replay = await service.create(
        actor=actor,
        record_id=instance.record_id,
        candidate_receipt_id=candidate_receipt.receipt_id,
        source_plan_digest=plan.canonical_digest,
        purpose="Submit this exact connector upgrade plan for independent human review.",
        acknowledged_request_is_not_approval_and_grants_no_execution_authority=True,
        idempotency_key="connector-upgrade-approval-001",
        correlation_id="correlation.connector-upgrade-approval-replay",
    )

    assert request.plan_id == plan.plan_id and request.plan_digest == plan.canonical_digest
    assert request.candidate_receipt_digest == plan.candidate_receipt_digest
    assert request.state == "pending" and request.separation_of_duties_required
    assert not request.approval_granted and not request.decision_recorded
    assert not request.execution_authorized and not request.infrastructure_mutation_performed
    assert request.requested_by == actor.subject_id
    assert replay.request_id == request.request_id and replay.reused
    restored = PostgreSQLConnectorUpgradeApprovalRepository._to_domain(
        cast(
            dict[str, object],
            ConnectorUpgradeApprovalService._normalize(asdict(request)),
        )
    )
    assert restored == request
    assert [item.result_code for item in audit.records].count(
        "connector_upgrade_approval_request_created"
    ) == 1


@pytest.mark.asyncio
async def test_upgrade_approval_request_fails_closed_for_drift_and_configured_target() -> None:
    service, _upgrade_service, _, _, _, _, sources, _ = await approval_fixture()
    instance, candidate_receipt = sources
    actor = instance_operator()
    with pytest.raises(ConnectorUpgradeApprovalError, match="plan_not_eligible"):
        await service.create(
            actor=actor,
            record_id=instance.record_id,
            candidate_receipt_id=candidate_receipt.receipt_id,
            source_plan_digest="0" * 64,
            purpose="Submit this exact connector upgrade plan for independent human review.",
            acknowledged_request_is_not_approval_and_grants_no_execution_authority=True,
            idempotency_key="connector-upgrade-approval-drift",
            correlation_id="correlation.connector-upgrade-approval-drift",
        )

    (
        target_service,
        configured_instance_service,
        package_service,
        _,
        configured_instance,
        profile,
        target_policy,
    ) = await target_configuration_fixture()
    await bind_target(target_service, configured_instance, profile, target_policy)
    (
        current_receipt,
        _,
        current_registration,
        _,
    ) = await package_service.connector_instance_creation_source(
        receipt_id=configured_instance.source_installation_receipt_id
    )
    configured_candidate, configured_registration = upgrade_package(
        current_receipt, current_registration
    )
    configured_upgrade_service = ConnectorUpgradeReadinessService(
        instance_repository=configured_instance_service.repository,
        target_repository=target_service.repository,
        package_source=UpgradePackageSource(
            (
                (current_receipt, current_registration),
                (configured_candidate, configured_registration),
            )
        ),
        audit_sink=CollectingAuditSink(),
        environment_id=configured_instance.environment_id,
    )
    blocked_plan = await configured_upgrade_service.plan(
        actor=actor,
        record_id=configured_instance.record_id,
        candidate_receipt_id=configured_candidate.receipt_id,
        correlation_id="correlation.connector-upgrade-plan-blocked",
    )
    blocked_service = ConnectorUpgradeApprovalService(
        repository=InMemoryConnectorUpgradeApprovalRepository(),
        policy_source=InMemoryConnectorUpgradeApprovalPolicySource(()),
        upgrade_service=configured_upgrade_service,
        audit_sink=CollectingAuditSink(),
        environment_id=configured_instance.environment_id,
    )
    with pytest.raises(ConnectorUpgradeApprovalError, match="plan_not_eligible"):
        await blocked_service.create(
            actor=actor,
            record_id=configured_instance.record_id,
            candidate_receipt_id=configured_candidate.receipt_id,
            source_plan_digest=blocked_plan.canonical_digest,
            purpose="Submit this exact connector upgrade plan for independent human review.",
            acknowledged_request_is_not_approval_and_grants_no_execution_authority=True,
            idempotency_key="connector-upgrade-approval-blocked",
            correlation_id="correlation.connector-upgrade-approval-blocked",
        )


def test_upgrade_approval_api_is_no_store_and_hides_custody_metadata(tmp_path: Path) -> None:
    (
        approval_service,
        upgrade_service,
        instance_service,
        package_service,
        registration_service,
        publication_service,
        sources,
        _,
    ) = asyncio.run(approval_fixture())
    instance, candidate_receipt = sources
    actor = instance_operator()
    plan = asyncio.run(
        upgrade_service.plan(
            actor=actor,
            record_id=instance.record_id,
            candidate_receipt_id=candidate_receipt.receipt_id,
            correlation_id="correlation.connector-upgrade-plan-api",
        )
    )
    app = create_app(
        settings(
            development_subject_id=actor.subject_id,
            mcp_builder_generation_root=tmp_path / "mcp-builder-generations",
        ),
        identity_provider=BasicTestIdentityProvider(actor),
        registry_publication_service=publication_service,
        package_registration_service=registration_service,
        package_installation_service=package_service,
        connector_instance_creation_service=instance_service,
        connector_upgrade_approval_service=approval_service,
    )
    with TestClient(app) as client:
        app.state.connector_upgrade_readiness_service = upgrade_service
        login_response = login(client)
        response = client.post(
            f"/api/v1/connectors/instances/{instance.record_id}/upgrade-plans/"
            f"{candidate_receipt.receipt_id}/approval-requests",
            headers={
                "Idempotency-Key": "connector-upgrade-approval-api",
                "X-CSRF-Token": login_response.headers["X-CSRF-Token"],
            },
            json={
                "schema_version": "atlas.connector-upgrade-approval-create-input.v1",
                "source_plan_digest": plan.canonical_digest,
                "purpose": "Submit this exact connector upgrade plan for independent human review.",
                "acknowledged_request_is_not_approval_and_grants_no_execution_authority": True,
            },
        )
        assert response.status_code == 201, response.text
        request_id = response.json()["data"]["request_id"]
        read_response = client.get(
            f"/api/v1/connectors/instances/{instance.record_id}/upgrade-approval-requests/"
            f"{request_id}"
        )

    assert response.headers["Cache-Control"] == "no-store"
    assert read_response.status_code == 200 and read_response.headers["Cache-Control"] == "no-store"
    data = response.json()["data"]
    assert data["plan_digest"] == plan.canonical_digest and data["state"] == "pending"
    assert data["approval_granted"] is False and data["execution_authorized"] is False
    rendered = response.text.lower()
    for hidden in ("request_fingerprint", "idempotency_key", "credential", "target_endpoint"):
        assert hidden not in rendered
