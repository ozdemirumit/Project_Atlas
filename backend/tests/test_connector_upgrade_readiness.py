from __future__ import annotations

import asyncio
from dataclasses import replace
from datetime import timedelta
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from test_browser_sessions import BasicTestIdentityProvider, login, settings
from test_instance_creation import create_instance, instance_fixture, instance_operator
from test_package_acquisition import CollectingAuditSink
from test_target_configuration import bind_target, target_configuration_fixture

from atlas.api.app import create_app
from atlas.modules.connectors.adapters.target_configuration_memory import (
    InMemoryConnectorTargetConfigurationRepository,
)
from atlas.modules.connectors.application.instance_creation_ports import (
    ConnectorInstanceCreationError,
)
from atlas.modules.connectors.application.upgrade_readiness import (
    ConnectorUpgradeReadinessService,
)
from atlas.modules.connectors.domain.package_installation import (
    ConnectorPackageInstallationReceipt,
)
from atlas.modules.connectors.domain.package_registration import (
    ConnectorPackageRegistrationRecord,
    ConnectorRegisteredCapability,
)
from atlas.modules.identity.domain.models import AssuranceLevel, AuthenticationMethod


class UpgradePackageSource:
    def __init__(
        self,
        records: tuple[
            tuple[ConnectorPackageInstallationReceipt, ConnectorPackageRegistrationRecord], ...
        ],
    ) -> None:
        self._records = records

    async def get(
        self, *, receipt_id: str
    ) -> tuple[ConnectorPackageInstallationReceipt, ConnectorPackageRegistrationRecord]:
        return next(item for item in self._records if item[0].receipt_id == receipt_id)

    async def list_scope(
        self, *, organization_id: str, environment_id: str
    ) -> tuple[tuple[ConnectorPackageInstallationReceipt, ConnectorPackageRegistrationRecord], ...]:
        return tuple(
            item
            for item in self._records
            if item[0].organization_id == organization_id
            and item[0].environment_id == environment_id
        )


def upgrade_package(
    current_receipt: ConnectorPackageInstallationReceipt,
    current_registration: ConnectorPackageRegistrationRecord,
) -> tuple[ConnectorPackageInstallationReceipt, ConnectorPackageRegistrationRecord]:
    package_digest = "b" * 64
    manifest_digest = "c" * 64
    registration_digest = "d" * 64
    manifest = replace(
        current_registration.manifest,
        manifest_version="2.0.0",
        release_version="version.2.0.0",
        network_destinations=("api.storage.example", "telemetry.storage.example"),
        configuration_key_count=current_registration.manifest.configuration_key_count + 1,
        secret_reference_count=current_registration.manifest.secret_reference_count + 1,
        capabilities=(
            *current_registration.manifest.capabilities,
            ConnectorRegisteredCapability(
                capability_id="storage.capacity.read",
                capability_class="C1",
                required_permission="connectors.storage.capacity.read",
            ),
        ),
        manifest_digest=manifest_digest,
    )
    registration = replace(
        current_registration,
        record_id="connector-package-registration.upgrade-v2",
        package_digest=package_digest,
        release_version="version.2.0.0",
        manifest=manifest,
        canonical_digest=registration_digest,
    )
    receipt = replace(
        current_receipt,
        receipt_id="connector-package-installation-receipt.upgrade-v2",
        source_registration_record_id=registration.record_id,
        source_registration_record_digest=registration_digest,
        package_digest=package_digest,
        release_version="version.2.0.0",
        manifest_digest=manifest_digest,
        installation=replace(current_receipt.installation, package_digest=package_digest),
        installed_at=current_receipt.installed_at + timedelta(hours=1),
        canonical_digest="e" * 64,
        request_fingerprint="f" * 64,
        idempotency_key="install-upgrade-v2",
    )
    return receipt, registration


@pytest.mark.asyncio
async def test_upgrade_readiness_compares_exact_manifests_without_authorizing_execution() -> None:
    audit = CollectingAuditSink()
    instance_service, package_service, _, _, installation, policy = await instance_fixture()
    actor = replace(
        instance_operator(),
        authentication_method=AuthenticationMethod.DEVELOPMENT,
        assurance_level=AssuranceLevel.DEVELOPMENT,
    )
    instance = await create_instance(instance_service, installation, policy, actor=actor)
    (
        current_receipt,
        _,
        current_registration,
        _,
    ) = await package_service.connector_instance_creation_source(receipt_id=installation.receipt_id)
    candidate_receipt, candidate_registration = upgrade_package(
        current_receipt, current_registration
    )
    service = ConnectorUpgradeReadinessService(
        instance_repository=instance_service.repository,
        target_repository=InMemoryConnectorTargetConfigurationRepository(),
        package_source=UpgradePackageSource(
            (
                (current_receipt, current_registration),
                (candidate_receipt, candidate_registration),
            )
        ),
        audit_sink=audit,
        environment_id=instance.environment_id,
        clock=lambda: installation.installed_at + timedelta(hours=2),
    )

    readiness = await service.evaluate(
        actor=actor,
        record_id=instance.record_id,
        correlation_id="correlation.connector-upgrade-readiness",
    )

    assert readiness.current_release_version == current_receipt.release_version
    assert len(readiness.candidates) == 1
    candidate = readiness.candidates[0]
    assert candidate.release_version == "version.2.0.0"
    assert candidate.upgrade_class == "major" and candidate.risk_level == "high"
    assert candidate.policy_review_required and candidate.configuration_migration_required
    assert candidate.rollback_receipt_id == current_receipt.receipt_id
    assert candidate.review_eligible and not candidate.blockers
    assert candidate.capability_changes[0].change_type == "added"
    assert candidate.network_destinations_added == tuple(
        sorted(
            set(candidate_registration.manifest.network_destinations)
            - set(current_registration.manifest.network_destinations)
        )
    )
    assert candidate.secret_reference_delta == 1
    assert not candidate.execution_authorized and not candidate.infrastructure_mutation_performed
    assert not readiness.execution_authorized and not readiness.infrastructure_mutation_performed
    assert [item.result_code for item in audit.records] == ["connector_upgrade_readiness_evaluated"]


@pytest.mark.asyncio
async def test_upgrade_readiness_fails_closed_for_retired_or_cross_scope_sources() -> None:
    instance_service, package_service, _, _, installation, policy = await instance_fixture()
    instance = await create_instance(instance_service, installation, policy)
    (
        current_receipt,
        _,
        current_registration,
        _,
    ) = await package_service.connector_instance_creation_source(receipt_id=installation.receipt_id)
    service = ConnectorUpgradeReadinessService(
        instance_repository=instance_service.repository,
        target_repository=InMemoryConnectorTargetConfigurationRepository(),
        package_source=UpgradePackageSource(((current_receipt, current_registration),)),
        audit_sink=CollectingAuditSink(),
        environment_id=instance.environment_id,
    )
    foreign = replace(instance_operator(), organization_id="organization.foreign")

    with pytest.raises(ConnectorInstanceCreationError, match="record_not_found"):
        await service.evaluate(
            actor=foreign,
            record_id=instance.record_id,
            correlation_id="correlation.connector-upgrade-foreign",
        )


@pytest.mark.asyncio
async def test_upgrade_readiness_blocks_sdk_changes_and_rejects_inconsistent_lineage() -> None:
    instance_service, package_service, _, _, installation, policy = await instance_fixture()
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
    sdk_registration = replace(
        candidate_registration,
        manifest=replace(candidate_registration.manifest, sdk_profile="atlas.python313.v1"),
    )
    sdk_receipt = replace(candidate_receipt, sdk_profile="atlas.python313.v1")
    service = ConnectorUpgradeReadinessService(
        instance_repository=instance_service.repository,
        target_repository=InMemoryConnectorTargetConfigurationRepository(),
        package_source=UpgradePackageSource(
            ((current_receipt, current_registration), (sdk_receipt, sdk_registration))
        ),
        audit_sink=CollectingAuditSink(),
        environment_id=instance.environment_id,
    )

    readiness = await service.evaluate(
        actor=instance_operator(),
        record_id=instance.record_id,
        correlation_id="correlation.connector-upgrade-sdk",
    )
    sdk_candidate = readiness.candidates[0]
    assert sdk_candidate.risk_level == "critical" and not sdk_candidate.review_eligible
    assert sdk_candidate.blockers == ("connector.upgrade.sdk-profile-changed",)

    inconsistent_registration = replace(
        candidate_registration,
        release_version="version.2.0.1",
        manifest=replace(
            candidate_registration.manifest,
            manifest_version="2.0.1",
            release_version="version.2.0.1",
        ),
    )
    inconsistent_service = ConnectorUpgradeReadinessService(
        instance_repository=instance_service.repository,
        target_repository=InMemoryConnectorTargetConfigurationRepository(),
        package_source=UpgradePackageSource(
            (
                (current_receipt, current_registration),
                (
                    candidate_receipt,
                    inconsistent_registration,
                ),
            )
        ),
        audit_sink=CollectingAuditSink(),
        environment_id=instance.environment_id,
    )
    with pytest.raises(ConnectorInstanceCreationError, match="candidate_binding_invalid"):
        await inconsistent_service.evaluate(
            actor=instance_operator(),
            record_id=instance.record_id,
            correlation_id="correlation.connector-upgrade-invalid-lineage",
        )


@pytest.mark.asyncio
async def test_upgrade_plan_is_deterministic_and_non_executable_for_unconfigured_instance() -> None:
    audit = CollectingAuditSink()
    instance_service, package_service, _, _, installation, policy = await instance_fixture()
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
    service = ConnectorUpgradeReadinessService(
        instance_repository=instance_service.repository,
        target_repository=InMemoryConnectorTargetConfigurationRepository(),
        package_source=UpgradePackageSource(
            ((current_receipt, current_registration), (candidate_receipt, candidate_registration))
        ),
        audit_sink=audit,
        environment_id=instance.environment_id,
        clock=lambda: installation.installed_at + timedelta(hours=2),
    )

    first = await service.plan(
        actor=instance_operator(),
        record_id=instance.record_id,
        candidate_receipt_id=candidate_receipt.receipt_id,
        correlation_id="correlation.connector-upgrade-plan",
    )
    second = await service.plan(
        actor=instance_operator(),
        record_id=instance.record_id,
        candidate_receipt_id=candidate_receipt.receipt_id,
        correlation_id="correlation.connector-upgrade-plan-repeat",
    )

    assert first.plan_id == second.plan_id and first.canonical_digest == second.canonical_digest
    assert first.plan_state == "ready_for_human_review" and first.plan_eligible
    assert first.estimated_interruption_min_minutes == 0
    assert first.estimated_interruption_max_minutes == 0
    assert len(first.steps) == 7 and first.steps[0].phase == "approval"
    assert first.rollback_step_ids and first.stop_condition_ids and first.validation_check_ids
    assert first.approval_required and first.decision_support_only
    assert not first.execution_authorized and not first.infrastructure_mutation_performed
    assert [item.result_code for item in audit.records] == [
        "connector_upgrade_readiness_evaluated",
        "connector_upgrade_plan_generated",
        "connector_upgrade_readiness_evaluated",
        "connector_upgrade_plan_generated",
    ]


@pytest.mark.asyncio
async def test_upgrade_plan_identity_is_stable_when_only_generation_time_advances() -> None:
    audit = CollectingAuditSink()
    instance_service, package_service, _, _, installation, policy = await instance_fixture()
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
    now = [installation.installed_at + timedelta(hours=2)]
    service = ConnectorUpgradeReadinessService(
        instance_repository=instance_service.repository,
        target_repository=InMemoryConnectorTargetConfigurationRepository(),
        package_source=UpgradePackageSource(
            ((current_receipt, current_registration), (candidate_receipt, candidate_registration))
        ),
        audit_sink=audit,
        environment_id=instance.environment_id,
        clock=lambda: now[0],
    )

    first = await service.plan(
        actor=instance_operator(),
        record_id=instance.record_id,
        candidate_receipt_id=candidate_receipt.receipt_id,
        correlation_id="correlation.connector-upgrade-plan-time-first",
    )
    now[0] += timedelta(minutes=10)
    second = await service.plan(
        actor=instance_operator(),
        record_id=instance.record_id,
        candidate_receipt_id=candidate_receipt.receipt_id,
        correlation_id="correlation.connector-upgrade-plan-time-second",
    )

    assert second.generated_at > first.generated_at
    assert second.expires_at > first.expires_at
    assert second.readiness_digest == first.readiness_digest
    assert second.plan_id == first.plan_id
    assert second.canonical_digest == first.canonical_digest


@pytest.mark.asyncio
async def test_upgrade_plan_blocks_configured_target_until_impact_is_established() -> None:
    (
        target_service,
        instance_service,
        package_service,
        _,
        instance,
        profile,
        policy,
    ) = await target_configuration_fixture()
    binding = await bind_target(target_service, instance, profile, policy)
    (
        current_receipt,
        _,
        current_registration,
        _,
    ) = await package_service.connector_instance_creation_source(
        receipt_id=instance.source_installation_receipt_id
    )
    candidate_receipt, candidate_registration = upgrade_package(
        current_receipt, current_registration
    )
    service = ConnectorUpgradeReadinessService(
        instance_repository=instance_service.repository,
        target_repository=target_service.repository,
        package_source=UpgradePackageSource(
            ((current_receipt, current_registration), (candidate_receipt, candidate_registration))
        ),
        audit_sink=CollectingAuditSink(),
        environment_id=instance.environment_id,
    )

    plan = await service.plan(
        actor=instance_operator(),
        record_id=instance.record_id,
        candidate_receipt_id=candidate_receipt.receipt_id,
        correlation_id="correlation.connector-upgrade-plan-configured",
    )

    assert plan.plan_state == "blocked" and not plan.plan_eligible
    assert "connector.upgrade.impact-evidence-required" in plan.blockers
    assert plan.target_id == binding.target_id and plan.site_id == binding.site_id
    assert plan.target_product == binding.target_product
    assert plan.estimated_interruption_min_minutes is None
    assert plan.estimated_interruption_max_minutes is None
    assert plan.unknowns
    assert any(item.requires_service_interruption for item in plan.steps)


def test_upgrade_readiness_api_is_no_store_and_exposes_no_mutation_authority(
    tmp_path: Path,
) -> None:
    (
        instance_service,
        package_service,
        registration_service,
        publication_service,
        installation,
        policy,
    ) = asyncio.run(instance_fixture())
    instance = asyncio.run(create_instance(instance_service, installation, policy))
    subject = instance_operator()
    app_settings = settings(
        development_subject_id=subject.subject_id,
        mcp_builder_generation_root=tmp_path / "mcp-builder-generations",
    )
    current_receipt, _, current_registration, _ = asyncio.run(
        package_service.connector_instance_creation_source(receipt_id=installation.receipt_id)
    )
    candidate_receipt, candidate_registration = upgrade_package(
        current_receipt, current_registration
    )
    plan_service = ConnectorUpgradeReadinessService(
        instance_repository=instance_service.repository,
        target_repository=InMemoryConnectorTargetConfigurationRepository(),
        package_source=UpgradePackageSource(
            ((current_receipt, current_registration), (candidate_receipt, candidate_registration))
        ),
        audit_sink=CollectingAuditSink(),
        environment_id=instance.environment_id,
    )
    app = create_app(
        app_settings,
        identity_provider=BasicTestIdentityProvider(subject),
        registry_publication_service=publication_service,
        package_registration_service=registration_service,
        package_installation_service=package_service,
        connector_instance_creation_service=instance_service,
    )
    with TestClient(app) as client:
        app.state.connector_upgrade_readiness_service = plan_service
        login(client)
        response = client.get(
            f"/api/v1/connectors/instances/{instance.record_id}/upgrade-readiness"
        )
        plan_response = client.get(
            f"/api/v1/connectors/instances/{instance.record_id}/upgrade-plans/"
            f"{candidate_receipt.receipt_id}"
        )

    assert response.status_code == 200, response.text
    assert response.headers["Cache-Control"] == "no-store"
    data = response.json()["data"]
    assert data["source_record_id"] == instance.record_id
    assert len(data["candidates"]) == 1
    assert data["decision_support_only"] is True
    assert data["execution_authorized"] is False
    assert data["infrastructure_mutation_performed"] is False
    rendered = response.text.lower()
    for hidden in (
        "artifact_reference",
        "request_fingerprint",
        "idempotency_key",
        "secret_value",
        "credential",
    ):
        assert hidden not in rendered
    assert plan_response.status_code == 200, plan_response.text
    assert plan_response.headers["Cache-Control"] == "no-store"
    plan_data = plan_response.json()["data"]
    assert plan_data["plan_state"] == "ready_for_human_review"
    assert plan_data["candidate_receipt_id"] == candidate_receipt.receipt_id
    assert plan_data["approval_required"] is True
    assert plan_data["execution_authorized"] is False
    assert plan_data["infrastructure_mutation_performed"] is False
    assert "target_endpoint" not in plan_response.text.lower()
    assert "secret_reference" not in plan_response.text.lower()
