from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path

import pytest

from atlas.core.audit import AuditRecord
from atlas.core.capabilities import CapabilityClass
from atlas.modules.connectors.adapters.memory import InMemoryConnectorRegistryRepository
from atlas.modules.connectors.application.registry import (
    PACKAGE_REGISTER,
    ConnectorAccessContext,
    ConnectorRegistryService,
    FoundationConnectorValidator,
)
from atlas.modules.connectors.domain.models import (
    ConnectorHealth,
    ConnectorInstance,
    InstanceLifecycle,
    PackageLifecycle,
    SideEffect,
)
from atlas.modules.connectors.vendors.hitachi_ops_center.client import (
    HitachiConnectorError,
    HitachiOpsCenterClient,
)
from atlas.modules.connectors.vendors.hitachi_ops_center.domain import HealthSeverity
from atlas.modules.connectors.vendors.hitachi_ops_center.manifest import (
    HEALTH_CAPABILITY_ID,
    INVENTORY_CAPABILITY_ID,
    build_candidate_manifest,
)
from atlas.modules.connectors.vendors.hitachi_ops_center.synthetic import (
    SyntheticHitachiFault,
    SyntheticHitachiResponse,
    SyntheticHitachiTransport,
)

NOW = datetime(2026, 8, 3, 17, 30, tzinfo=UTC)
VERSION_PATH = "/configuration/version"
INVENTORY_PATH = "/v1/objects/storages"
STORAGE_DEVICE_ID = "836000123456"
HEALTH_PATH = f"/v1/objects/storages/{STORAGE_DEVICE_ID}/components/instance"


class CollectingAuditSink:
    def __init__(self) -> None:
        self.records: list[AuditRecord] = []

    async def record(self, event: AuditRecord) -> None:
        self.records.append(event)


def access_context() -> ConnectorAccessContext:
    return ConnectorAccessContext(
        subject_id="subject.test.storage-engineer",
        actor_type="human",
        authentication_method="development",
        assurance_level="development",
        organization_id="organization.test",
        environment_id="environment.lab",
        site_id="site.storage-lab",
        target_id="target.hitachi.opscenter.lab",
        correlation_id="cor_hitachi_candidate",
        permissions=frozenset({PACKAGE_REGISTER}),
    )


def connector_instance() -> ConnectorInstance:
    return ConnectorInstance(
        instance_id="instance.hitachi.opscenter.lab",
        package_id="connector.hitachi.opscenter.configuration-manager",
        package_version="0.1.0",
        organization_id="organization.test",
        environment_id="environment.lab",
        site_id="site.storage-lab",
        target_id="target.hitachi.opscenter.lab",
        enabled_capability_ids=frozenset({INVENTORY_CAPABILITY_ID, HEALTH_CAPABILITY_ID}),
        secret_reference_ids=("secret.hitachi.opscenter.read-only",),
        lifecycle=InstanceLifecycle.DISABLED,
        health=ConnectorHealth.UNKNOWN,
        configuration_revision=1,
        created_at=NOW,
        created_by="subject.test.storage-engineer",
    )


def client(routes: dict[str, SyntheticHitachiResponse], **limits: int) -> HitachiOpsCenterClient:
    return HitachiOpsCenterClient(
        transport=SyntheticHitachiTransport(routes),
        allowed_storage_device_ids=frozenset({STORAGE_DEVICE_ID, "A34000800556"}),
        clock=lambda: NOW,
        **limits,
    )


@pytest.mark.asyncio
async def test_candidate_manifest_is_c1_and_remains_quarantined() -> None:
    package_manifest = build_candidate_manifest(
        digest_sha256="c" * 64,
        network_destination="opscenter.lab.example:23451",
    )
    assert package_manifest.generated is True
    assert {capability.capability_class for capability in package_manifest.capabilities} == {
        CapabilityClass.C1_READ_ONLY
    }
    assert {
        effect for capability in package_manifest.capabilities for effect in capability.side_effects
    } == {SideEffect.READ}

    repository = InMemoryConnectorRegistryRepository()
    service = ConnectorRegistryService(
        repository=repository,
        audit_sink=CollectingAuditSink(),
        validator=FoundationConnectorValidator(clock=lambda: NOW),
        clock=lambda: NOW,
    )
    package = await service.register_package(package_manifest, access_context())

    assert package.lifecycle is PackageLifecycle.QUARANTINED
    with pytest.raises(ValueError, match="approved host and port"):
        build_candidate_manifest(
            digest_sha256="d" * 64,
            network_destination="opscenter.lab.example:23451/path",
        )


@pytest.mark.asyncio
async def test_inventory_normalizes_only_non_endpoint_identity_fields() -> None:
    transport = SyntheticHitachiTransport(
        {
            INVENTORY_PATH: SyntheticHitachiResponse(
                payload={
                    "data": [
                        {
                            "storageDeviceId": STORAGE_DEVICE_ID,
                            "model": "VSP G400",
                            "serialNumber": 123456,
                            "svpIp": "192.0.2.100",
                        },
                        {
                            "storageDeviceId": "A34000800556",
                            "model": "VSP One B28",
                            "serialNumber": 800556,
                            "ip": "192.0.2.20",
                        },
                        {
                            "storageDeviceId": "836000999999",
                            "model": "VSP G900",
                            "serialNumber": 999999,
                            "ctl1Ip": "192.0.2.30",
                        },
                    ]
                }
            )
        }
    )
    connector = HitachiOpsCenterClient(
        transport=transport,
        allowed_storage_device_ids=frozenset({STORAGE_DEVICE_ID, "A34000800556"}),
        clock=lambda: NOW,
    )

    result = await connector.read_inventory()

    assert [array.model for array in result.arrays] == ["VSP G400", "VSP One B28"]
    assert result.arrays[0].storage_device_id == STORAGE_DEVICE_ID
    assert not hasattr(result.arrays[0], "svp_ip")
    assert result.evidence_references[0].startswith("hitachi-ops-center://inventory#sha256:")
    assert transport.requests == [INVENTORY_PATH]


@pytest.mark.asyncio
async def test_hardware_health_preserves_warning_and_unknown_status() -> None:
    connector = client(
        {
            HEALTH_PATH: SyntheticHitachiResponse(
                payload={
                    "dkcs": [
                        {
                            "location": "DKC0",
                            "ctls": [
                                {
                                    "location": "CTL1",
                                    "status": "Normal",
                                    "temperatureStatus": "Warning",
                                },
                                {"location": "CTL2", "status": "Mystery"},
                            ],
                        }
                    ],
                    "bkmfs": [{"location": "BKM1", "status": "Warning (FAN)"}],
                    "fans": [{"location": "FAN1", "status": "Failed"}],
                }
            )
        }
    )

    result = await connector.read_hardware_health(STORAGE_DEVICE_ID)

    assert result.overall_severity is HealthSeverity.CRITICAL
    assert {component.severity for component in result.components} >= {
        HealthSeverity.NORMAL,
        HealthSeverity.WARNING,
        HealthSeverity.CRITICAL,
        HealthSeverity.UNKNOWN,
    }
    assert "unknown_vendor_status:ctls:Mystery" in result.warnings


@pytest.mark.asyncio
async def test_empty_health_is_unknown_not_success() -> None:
    connector = client({HEALTH_PATH: SyntheticHitachiResponse(payload={"ctls": []})})

    result = await connector.read_hardware_health(STORAGE_DEVICE_ID)

    assert result.overall_severity is HealthSeverity.UNKNOWN
    assert result.components == ()
    assert result.warnings == ("no_supported_component_status_returned",)


@pytest.mark.asyncio
async def test_invalid_target_is_rejected_before_transport_access() -> None:
    transport = SyntheticHitachiTransport({})
    connector = HitachiOpsCenterClient(
        transport=transport,
        allowed_storage_device_ids=frozenset({STORAGE_DEVICE_ID}),
        clock=lambda: NOW,
    )

    with pytest.raises(HitachiConnectorError) as error:
        await connector.read_hardware_health("../../other-target")

    assert error.value.code == "invalid_storage_device_id"
    assert transport.requests == []

    with pytest.raises(HitachiConnectorError) as binding_error:
        await connector.read_hardware_health("836000999999")
    assert binding_error.value.code == "target_not_bound"
    assert transport.requests == []


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("fault", "code", "retryable"),
    [
        (SyntheticHitachiFault.DENIED, "vendor_permission_denied", False),
        (SyntheticHitachiFault.TIMEOUT, "target_timeout", True),
        (SyntheticHitachiFault.THROTTLED, "vendor_rate_limited", True),
        (SyntheticHitachiFault.UNAVAILABLE, "target_unavailable", True),
    ],
)
async def test_transport_faults_are_mapped_safely(
    fault: SyntheticHitachiFault, code: str, retryable: bool
) -> None:
    connector = client({INVENTORY_PATH: SyntheticHitachiResponse(fault=fault)})

    with pytest.raises(HitachiConnectorError) as error:
        await connector.read_inventory()

    assert error.value.code == code
    assert error.value.retryable is retryable


@pytest.mark.asyncio
async def test_malformed_and_oversized_inventory_are_rejected() -> None:
    malformed = client({INVENTORY_PATH: SyntheticHitachiResponse(payload={"data": "invalid"})})
    oversized = client(
        {INVENTORY_PATH: SyntheticHitachiResponse(payload={"data": [{}, {}]})},
        maximum_arrays=1,
    )
    oversized_bytes = client(
        {INVENTORY_PATH: SyntheticHitachiResponse(payload={"data": [], "padding": "x" * 128})},
        maximum_response_bytes=64,
    )

    with pytest.raises(HitachiConnectorError) as malformed_error:
        await malformed.read_inventory()
    with pytest.raises(HitachiConnectorError) as oversized_error:
        await oversized.read_inventory()
    with pytest.raises(HitachiConnectorError) as oversized_bytes_error:
        await oversized_bytes.read_inventory()

    assert malformed_error.value.code == "malformed_vendor_response"
    assert oversized_error.value.code == "vendor_response_limit_exceeded"
    assert oversized_bytes_error.value.code == "vendor_response_limit_exceeded"


@pytest.mark.asyncio
async def test_self_test_uses_version_only_and_detects_product_mismatch() -> None:
    compatible_transport = SyntheticHitachiTransport(
        {
            VERSION_PATH: SyntheticHitachiResponse(
                payload={
                    "productName": "Configuration Manager REST API",
                    "apiVersion": "1.63.0",
                }
            )
        }
    )
    incompatible_transport = SyntheticHitachiTransport(
        {
            VERSION_PATH: SyntheticHitachiResponse(
                payload={"productName": "Unexpected Product", "apiVersion": "1.63.0"}
            )
        }
    )

    compatible = await HitachiOpsCenterClient(
        transport=compatible_transport,
        allowed_storage_device_ids=frozenset({STORAGE_DEVICE_ID}),
        clock=lambda: NOW,
    ).self_test(connector_instance())
    incompatible = await HitachiOpsCenterClient(
        transport=incompatible_transport,
        allowed_storage_device_ids=frozenset({STORAGE_DEVICE_ID}),
        clock=lambda: NOW,
    ).self_test(connector_instance())

    assert compatible.health is ConnectorHealth.HEALTHY
    assert incompatible.health is ConnectorHealth.INCOMPATIBLE
    assert compatible_transport.requests == [VERSION_PATH]
    assert incompatible_transport.requests == [VERSION_PATH]


def test_synthetic_transport_has_no_external_or_secret_access() -> None:
    transport = SyntheticHitachiTransport(
        {INVENTORY_PATH: SyntheticHitachiResponse(payload={"data": []})}
    )

    assert transport.network_access is False
    assert transport.secret_access is False


def test_candidate_package_assets_are_strict_and_synthetic_only() -> None:
    package_root = Path(__file__).parents[2] / "mcp" / "connectors" / "hitachi_ops_center"
    schema = json.loads((package_root / "configuration.schema.json").read_text(encoding="utf-8"))
    provenance = json.loads((package_root / "source-provenance.json").read_text(encoding="utf-8"))

    assert schema["additionalProperties"] is False
    assert "credential_reference_id" in schema["required"]
    assert "allowed_storage_device_ids" in schema["required"]
    assert "password" not in schema["properties"]
    assert provenance["data_policy"] == "synthetic-only"
    assert provenance["production_credentials_present"] is False
    assert {source["method"] for source in provenance["capability_sources"]} == {"GET"}
