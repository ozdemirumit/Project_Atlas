from __future__ import annotations

from datetime import UTC, datetime

import pytest

from atlas.core.audit import AuditRecord
from atlas.modules.connectors.adapters.bundled_connection_configuration_memory import (
    InMemoryBundledConnectionConfigurationRepository,
)
from atlas.modules.connectors.adapters.instance_creation_memory import (
    InMemoryConnectorInstanceRepository,
)
from atlas.modules.connectors.application.bundled_catalog import (
    BundledConnectorCatalogService,
    build_brocade_sannav_bundled_descriptor,
    build_hitachi_ops_center_bundled_descriptor,
)
from atlas.modules.connectors.application.bundled_connection_configuration import (
    BundledConnectionConfigurationService,
)
from atlas.modules.connectors.domain.bundled_catalog import BundledConnectorDescriptor
from atlas.modules.identity.domain.models import (
    AssuranceLevel,
    AuthenticatedSubject,
    AuthenticationMethod,
    SubjectKind,
)

NOW = datetime(2026, 8, 28, 12, 0, tzinfo=UTC)


class CollectingAuditSink:
    def __init__(self) -> None:
        self.records: list[AuditRecord] = []

    async def record(self, record: AuditRecord) -> None:
        self.records.append(record)


def operator() -> AuthenticatedSubject:
    return AuthenticatedSubject(
        subject_id="subject.catalog-operator",
        display_name="Catalog Operator",
        kind=SubjectKind.HUMAN,
        provider_id="provider.test",
        authentication_method=AuthenticationMethod.DEVELOPMENT,
        assurance_level=AssuranceLevel.DEVELOPMENT,
        authenticated_at=NOW,
        organization_id="organization.test",
        role_ids=("role.connector-operator",),
    )


async def create_instance(
    descriptor: BundledConnectorDescriptor,
    instance_repository: InMemoryConnectorInstanceRepository,
    *,
    instance_key: str,
) -> str:
    catalog = BundledConnectorCatalogService(
        descriptors=(descriptor,),
        repository=instance_repository,
        audit_sink=CollectingAuditSink(),
        environment_id="environment.test",
        clock=lambda: NOW,
    )
    record = await catalog.create_instance(
        actor=operator(),
        catalog_item_id=descriptor.catalog_item_id,
        catalog_item_digest=descriptor.canonical_digest,
        instance_key=instance_key,
        display_name="Vendor instance",
        purpose="Register bundled development catalog evidence without runtime authority.",
        acknowledged_instance_is_disabled_and_grants_no_authority=True,
        idempotency_key=f"catalog-create-{instance_key}",
        correlation_id="cor_bundled_catalog",
    )
    return record.instance_id


@pytest.mark.asyncio
async def test_a_non_hitachi_instance_can_be_configured_through_the_shared_service() -> None:
    """Regression test: BundledConnectionConfigurationService.configure() and
    _require_bundled_instance() used to hardcode Hitachi's PACKAGE_ID -- any other vendor's
    instance (e.g. a real, catalog-registered Brocade SANnav instance) would be rejected with
    "bundled_instance_invalid" even though it was a completely valid, disabled, catalog-registered
    instance. This proved the "modular multi-vendor" bundled-catalog flow only actually worked for
    Hitachi end to end. Fixed by deriving connector_id from the matched instance record itself."""
    instance_repository = InMemoryConnectorInstanceRepository()
    brocade_instance_id = await create_instance(
        build_brocade_sannav_bundled_descriptor(),
        instance_repository,
        instance_key="brocade-lab",
    )

    configuration_service = BundledConnectionConfigurationService(
        repository=InMemoryBundledConnectionConfigurationRepository(),
        instance_repository=instance_repository,
        audit_sink=CollectingAuditSink(),
        environment_id="environment.test",
        deployment_environment="development",
        clock=lambda: NOW,
    )

    record = await configuration_service.configure(
        actor=operator(),
        instance_id=brocade_instance_id,
        hostname="sannav.lab.example",
        port=443,
        trust_profile_id="trust.system-ca",
        secret_reference_id="secret.brocade.readonly",
        correlation_id="cor_configure",
    )

    assert record.connector_id == "connector.brocade.sannav.management-portal"
    assert record.system_id is None


@pytest.mark.asyncio
async def test_hitachi_instance_configuration_is_unchanged_and_system_id_is_optional() -> None:
    instance_repository = InMemoryConnectorInstanceRepository()
    hitachi_instance_id = await create_instance(
        build_hitachi_ops_center_bundled_descriptor(),
        instance_repository,
        instance_key="hitachi-lab",
    )

    configuration_service = BundledConnectionConfigurationService(
        repository=InMemoryBundledConnectionConfigurationRepository(),
        instance_repository=instance_repository,
        audit_sink=CollectingAuditSink(),
        environment_id="environment.test",
        deployment_environment="development",
        clock=lambda: NOW,
    )

    record = await configuration_service.configure(
        actor=operator(),
        instance_id=hitachi_instance_id,
        hostname="opscenter.lab.example",
        port=23451,
        trust_profile_id="trust.system-ca",
        secret_reference_id="secret.hitachi.readonly",
        correlation_id="cor_configure",
    )

    assert record.connector_id == "connector.hitachi.opscenter.configuration-manager"
    assert record.system_id is None


@pytest.mark.asyncio
async def test_a_system_scoped_vendor_can_record_its_system_id() -> None:
    instance_repository = InMemoryConnectorInstanceRepository()
    brocade_instance_id = await create_instance(
        build_brocade_sannav_bundled_descriptor(),
        instance_repository,
        instance_key="scoped-lab",
    )
    configuration_service = BundledConnectionConfigurationService(
        repository=InMemoryBundledConnectionConfigurationRepository(),
        instance_repository=instance_repository,
        audit_sink=CollectingAuditSink(),
        environment_id="environment.test",
        deployment_environment="development",
        clock=lambda: NOW,
    )

    record = await configuration_service.configure(
        actor=operator(),
        instance_id=brocade_instance_id,
        hostname="dorado.lab.example",
        port=8088,
        trust_profile_id="trust.system-ca",
        secret_reference_id="secret.huawei.dorado.readonly",
        correlation_id="cor_configure",
        system_id="2102350ABC",
    )

    assert record.system_id == "2102350ABC"
