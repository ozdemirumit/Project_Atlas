from __future__ import annotations

from dataclasses import replace
from datetime import UTC, datetime

import pytest

from atlas.core.audit import AuditRecord
from atlas.core.capabilities import CapabilityClass
from atlas.modules.connectors.adapters.memory import InMemoryConnectorRegistryRepository
from atlas.modules.connectors.application.ports import ConnectorSelfTestResult
from atlas.modules.connectors.application.registry import (
    CAPABILITY_DISCOVER,
    INSTANCE_MANAGE,
    INSTANCE_READ,
    PACKAGE_READ,
    PACKAGE_REGISTER,
    ConnectorAccessContext,
    ConnectorRegistryError,
    ConnectorRegistryService,
    FoundationConnectorValidator,
)
from atlas.modules.connectors.domain.models import (
    CapabilityManifest,
    ConnectorHealth,
    ConnectorInstance,
    ConnectorPackageManifest,
    IdempotencyClass,
    InstanceLifecycle,
    PackageLifecycle,
    SideEffect,
)

NOW = datetime(2026, 8, 3, 15, 0, tzinfo=UTC)


class CollectingAuditSink:
    def __init__(self) -> None:
        self.records: list[AuditRecord] = []

    async def record(self, event: AuditRecord) -> None:
        self.records.append(event)


class FailingAuditSink:
    async def record(self, event: AuditRecord) -> None:
        raise RuntimeError("audit unavailable")


class HealthySelfTester:
    async def self_test(self, instance: ConnectorInstance) -> ConnectorSelfTestResult:
        return ConnectorSelfTestResult(
            health=ConnectorHealth.HEALTHY,
            checked_at=NOW,
            code="simulator_isolation_verified",
        )


class UnhealthySelfTester:
    async def self_test(self, instance: ConnectorInstance) -> ConnectorSelfTestResult:
        return ConnectorSelfTestResult(
            health=ConnectorHealth.DEGRADED,
            checked_at=NOW,
            code="simulator_self_test_failed",
        )


class RevisionChangingSelfTester:
    def __init__(self, repository: InMemoryConnectorRegistryRepository) -> None:
        self._repository = repository

    async def self_test(self, instance: ConnectorInstance) -> ConnectorSelfTestResult:
        await self._repository.replace_instance(
            replace(instance, configuration_revision=instance.configuration_revision + 1)
        )
        return ConnectorSelfTestResult(
            health=ConnectorHealth.HEALTHY,
            checked_at=NOW,
            code="simulator_isolation_verified",
        )


def capability(
    capability_id: str,
    capability_class: CapabilityClass,
    side_effect: SideEffect,
) -> CapabilityManifest:
    return CapabilityManifest(
        capability_id=capability_id,
        version="1.0.0",
        description=f"Synthetic {capability_id} capability.",
        capability_class=capability_class,
        side_effects=frozenset({side_effect}),
        target_types=("target.storage.array",),
        timeout_seconds=30,
        idempotency=IdempotencyClass.SAFE,
    )


def manifest(*capabilities: CapabilityManifest) -> ConnectorPackageManifest:
    return ConnectorPackageManifest(
        package_id="connector.simulator.storage",
        connector_id="connector.simulator.storage",
        display_name="Storage Simulator",
        publisher="Project Atlas",
        owner="Platform Engineering",
        package_version="1.0.0",
        atlas_compatibility=">=0.1.0,<0.2.0",
        runtime="simulator",
        entry_point="atlas.simulator.storage",
        digest_sha256="a" * 64,
        supported_products=("Synthetic Storage 1.0",),
        network_destinations=(),
        capabilities=capabilities,
    )


def access_context(
    *permissions: str,
    organization_id: str = "organization.test",
    environment_id: str = "environment.test",
    site_id: str = "site.lab",
    target_id: str = "target.storage.lab",
) -> ConnectorAccessContext:
    return ConnectorAccessContext(
        subject_id="subject.test.operator",
        actor_type="human",
        authentication_method="development",
        assurance_level="development",
        organization_id=organization_id,
        environment_id=environment_id,
        site_id=site_id,
        target_id=target_id,
        correlation_id="cor_connector_test",
        permissions=frozenset(permissions),
    )


def registry(
    repository: InMemoryConnectorRegistryRepository,
    audit_sink: CollectingAuditSink | FailingAuditSink,
) -> ConnectorRegistryService:
    return ConnectorRegistryService(
        repository=repository,
        audit_sink=audit_sink,
        validator=FoundationConnectorValidator(clock=lambda: NOW),
        clock=lambda: NOW,
    )


@pytest.mark.asyncio
async def test_registers_immutable_c0_and_c1_package_idempotently() -> None:
    repository = InMemoryConnectorRegistryRepository()
    audit_sink = CollectingAuditSink()
    service = registry(repository, audit_sink)
    package_manifest = manifest(
        capability("storage.metadata.describe", CapabilityClass.C0_INFORMATIONAL, SideEffect.NONE),
        capability("storage.health.read", CapabilityClass.C1_READ_ONLY, SideEffect.READ),
    )

    first = await service.register_package(
        package_manifest, access_context(PACKAGE_REGISTER, PACKAGE_READ)
    )
    second = await service.register_package(
        package_manifest, access_context(PACKAGE_REGISTER, PACKAGE_READ)
    )
    packages = await service.list_packages(access_context(PACKAGE_READ))

    assert first == second
    assert packages == (first,)
    assert first.validation_report.report_id.startswith("report.")
    assert [record.event_type for record in audit_sink.records] == [
        "atlas.connector.package.registered"
    ]


@pytest.mark.asyncio
async def test_same_package_version_with_different_digest_is_rejected() -> None:
    repository = InMemoryConnectorRegistryRepository()
    service = registry(repository, CollectingAuditSink())
    package_manifest = manifest(
        capability("storage.health.read", CapabilityClass.C1_READ_ONLY, SideEffect.READ)
    )
    context = access_context(PACKAGE_REGISTER)
    await service.register_package(package_manifest, context)

    with pytest.raises(ConnectorRegistryError, match="different digest") as error:
        await service.register_package(replace(package_manifest, digest_sha256="b" * 64), context)

    assert error.value.code == "package_version_conflict"


@pytest.mark.asyncio
async def test_foundation_registry_rejects_capabilities_above_c1() -> None:
    repository = InMemoryConnectorRegistryRepository()
    audit_sink = CollectingAuditSink()
    service = registry(repository, audit_sink)
    diagnostic = capability(
        "storage.diagnostic.probe", CapabilityClass.C2_DIAGNOSTIC, SideEffect.DIAGNOSTIC
    )

    with pytest.raises(ConnectorRegistryError) as error:
        await service.register_package(manifest(diagnostic), access_context(PACKAGE_REGISTER))

    assert error.value.code == "connector_validation_failed"
    assert error.value.validation_report is not None
    assert error.value.validation_report.findings[0].code == "unsupported_capability_class"
    assert audit_sink.records[-1].event_type == "atlas.connector.package.validation_failed"
    assert await repository.list_packages() == ()


@pytest.mark.asyncio
async def test_generated_package_is_quarantined_and_cannot_create_instances() -> None:
    repository = InMemoryConnectorRegistryRepository()
    audit_sink = CollectingAuditSink()
    service = registry(repository, audit_sink)
    health = capability("storage.health.read", CapabilityClass.C1_READ_ONLY, SideEffect.READ)
    generated = replace(manifest(health), generated=True)

    package = await service.register_package(generated, access_context(PACKAGE_REGISTER))

    assert package.lifecycle is PackageLifecycle.QUARANTINED
    assert audit_sink.records[-1].event_type == "atlas.connector.package.quarantined"
    with pytest.raises(ConnectorRegistryError) as error:
        await service.create_instance(
            instance_id="instance.storage.quarantined",
            package_id=generated.package_id,
            package_version=generated.package_version,
            organization_id="organization.test",
            environment_id="environment.test",
            site_id="site.lab",
            target_id="target.storage.lab",
            enabled_capability_ids=frozenset({"storage.health.read"}),
            secret_reference_ids=(),
            context=access_context(INSTANCE_MANAGE),
        )
    assert error.value.code == "package_not_approved"


@pytest.mark.asyncio
async def test_instance_is_disabled_until_healthy_self_test_and_then_discovers_capabilities() -> (
    None
):
    repository = InMemoryConnectorRegistryRepository()
    audit_sink = CollectingAuditSink()
    service = registry(repository, audit_sink)
    health = capability("storage.health.read", CapabilityClass.C1_READ_ONLY, SideEffect.READ)
    await service.register_package(manifest(health), access_context(PACKAGE_REGISTER))
    context = access_context(INSTANCE_MANAGE, CAPABILITY_DISCOVER)
    instance = await service.create_instance(
        instance_id="instance.storage.lab",
        package_id="connector.simulator.storage",
        package_version="1.0.0",
        organization_id="organization.test",
        environment_id="environment.test",
        site_id="site.lab",
        target_id="target.storage.lab",
        enabled_capability_ids=frozenset({"storage.health.read"}),
        secret_reference_ids=(),
        context=context,
    )

    assert instance.lifecycle is InstanceLifecycle.DISABLED
    with pytest.raises(ConnectorRegistryError) as error:
        await service.discover_capabilities(instance.instance_id, context)
    assert error.value.code == "instance_not_enabled"

    enabled = await service.enable_instance(
        instance.instance_id,
        HealthySelfTester(),
        context,
    )
    discovered = await service.discover_capabilities(instance.instance_id, context)

    assert enabled.lifecycle is InstanceLifecycle.ENABLED
    assert enabled.configuration_revision == 2
    assert discovered == (health,)
    assert audit_sink.records[-1].event_type == "atlas.connector.capabilities.discovered"


@pytest.mark.asyncio
async def test_simulator_instance_rejects_secret_references() -> None:
    repository = InMemoryConnectorRegistryRepository()
    service = registry(repository, CollectingAuditSink())
    health = capability("storage.health.read", CapabilityClass.C1_READ_ONLY, SideEffect.READ)
    await service.register_package(manifest(health), access_context(PACKAGE_REGISTER))

    with pytest.raises(ConnectorRegistryError) as error:
        await service.create_instance(
            instance_id="instance.storage.secret",
            package_id="connector.simulator.storage",
            package_version="1.0.0",
            organization_id="organization.test",
            environment_id="environment.test",
            site_id="site.lab",
            target_id="target.storage.lab",
            enabled_capability_ids=frozenset({"storage.health.read"}),
            secret_reference_ids=("secret.storage.password",),
            context=access_context(INSTANCE_MANAGE),
        )

    assert error.value.code == "simulator_secret_reference_forbidden"


@pytest.mark.asyncio
async def test_failed_self_test_is_audited_and_instance_stays_disabled() -> None:
    repository = InMemoryConnectorRegistryRepository()
    audit_sink = CollectingAuditSink()
    service = registry(repository, audit_sink)
    health = capability("storage.health.read", CapabilityClass.C1_READ_ONLY, SideEffect.READ)
    await service.register_package(manifest(health), access_context(PACKAGE_REGISTER))
    context = access_context(INSTANCE_MANAGE)
    instance = await service.create_instance(
        instance_id="instance.storage.degraded",
        package_id="connector.simulator.storage",
        package_version="1.0.0",
        organization_id="organization.test",
        environment_id="environment.test",
        site_id="site.lab",
        target_id="target.storage.lab",
        enabled_capability_ids=frozenset({"storage.health.read"}),
        secret_reference_ids=(),
        context=context,
    )

    with pytest.raises(ConnectorRegistryError) as error:
        await service.enable_instance(instance.instance_id, UnhealthySelfTester(), context)

    stored = await repository.get_instance(instance.instance_id)
    assert error.value.code == "self_test_failed"
    assert stored is not None
    assert stored.lifecycle is InstanceLifecycle.DISABLED
    assert audit_sink.records[-1].event_type == "atlas.connector.instance.enablement_failed"


@pytest.mark.asyncio
async def test_stale_self_test_result_cannot_enable_changed_instance() -> None:
    repository = InMemoryConnectorRegistryRepository()
    audit_sink = CollectingAuditSink()
    service = registry(repository, audit_sink)
    health = capability("storage.health.read", CapabilityClass.C1_READ_ONLY, SideEffect.READ)
    await service.register_package(manifest(health), access_context(PACKAGE_REGISTER))
    context = access_context(INSTANCE_MANAGE)
    instance = await service.create_instance(
        instance_id="instance.storage.changed",
        package_id="connector.simulator.storage",
        package_version="1.0.0",
        organization_id="organization.test",
        environment_id="environment.test",
        site_id="site.lab",
        target_id="target.storage.lab",
        enabled_capability_ids=frozenset({"storage.health.read"}),
        secret_reference_ids=(),
        context=context,
    )

    with pytest.raises(ConnectorRegistryError) as error:
        await service.enable_instance(
            instance.instance_id, RevisionChangingSelfTester(repository), context
        )

    stored = await repository.get_instance(instance.instance_id)
    assert error.value.code == "instance_changed_during_self_test"
    assert stored is not None
    assert stored.lifecycle is InstanceLifecycle.DISABLED
    assert audit_sink.records[-1].result_code == "instance_changed_during_self_test"


@pytest.mark.asyncio
async def test_permissions_and_organization_scope_are_enforced() -> None:
    repository = InMemoryConnectorRegistryRepository()
    service = registry(repository, CollectingAuditSink())
    package_manifest = manifest(
        capability("storage.health.read", CapabilityClass.C1_READ_ONLY, SideEffect.READ)
    )

    with pytest.raises(ConnectorRegistryError) as permission_error:
        await service.register_package(package_manifest, access_context())
    assert permission_error.value.code == "authorization_denied"

    await service.register_package(package_manifest, access_context(PACKAGE_REGISTER))
    with pytest.raises(ConnectorRegistryError) as scope_error:
        await service.create_instance(
            instance_id="instance.storage.foreign",
            package_id=package_manifest.package_id,
            package_version=package_manifest.package_version,
            organization_id="organization.foreign",
            environment_id="environment.test",
            site_id="site.lab",
            target_id="target.storage.lab",
            enabled_capability_ids=frozenset({"storage.health.read"}),
            secret_reference_ids=(),
            context=access_context(INSTANCE_MANAGE),
        )
    assert scope_error.value.code == "organization_scope_mismatch"

    with pytest.raises(ConnectorRegistryError) as target_scope_error:
        await service.create_instance(
            instance_id="instance.storage.other-target",
            package_id=package_manifest.package_id,
            package_version=package_manifest.package_version,
            organization_id="organization.test",
            environment_id="environment.test",
            site_id="site.lab",
            target_id="target.storage.other",
            enabled_capability_ids=frozenset({"storage.health.read"}),
            secret_reference_ids=(),
            context=access_context(INSTANCE_MANAGE),
        )
    assert target_scope_error.value.code == "connector_scope_mismatch"


@pytest.mark.asyncio
async def test_instance_listing_is_filtered_to_exact_authorized_target_scope() -> None:
    repository = InMemoryConnectorRegistryRepository()
    audit_sink = CollectingAuditSink()
    service = registry(repository, audit_sink)
    health = capability("storage.health.read", CapabilityClass.C1_READ_ONLY, SideEffect.READ)
    await service.register_package(manifest(health), access_context(PACKAGE_REGISTER))
    create_context = access_context(INSTANCE_MANAGE)
    visible = await service.create_instance(
        instance_id="instance.storage.visible",
        package_id="connector.simulator.storage",
        package_version="1.0.0",
        organization_id="organization.test",
        environment_id="environment.test",
        site_id="site.lab",
        target_id="target.storage.lab",
        enabled_capability_ids=frozenset({"storage.health.read"}),
        secret_reference_ids=(),
        context=create_context,
    )
    await repository.add_instance(
        replace(
            visible,
            instance_id="instance.storage.hidden",
            target_id="target.storage.other",
        )
    )

    listed = await service.list_instances(access_context(INSTANCE_READ))

    assert listed == (visible,)
    assert audit_sink.records[-1].event_type == "atlas.connector.instances.listed"


@pytest.mark.asyncio
async def test_audit_failure_prevents_registry_mutation() -> None:
    repository = InMemoryConnectorRegistryRepository()
    service = registry(repository, FailingAuditSink())

    with pytest.raises(RuntimeError, match="audit unavailable"):
        await service.register_package(
            manifest(
                capability("storage.health.read", CapabilityClass.C1_READ_ONLY, SideEffect.READ)
            ),
            access_context(PACKAGE_REGISTER),
        )

    assert await repository.list_packages() == ()
