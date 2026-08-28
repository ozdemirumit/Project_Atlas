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
from atlas.modules.connectors.vendors.huawei_dorado.client import (
    HuaweiConnectorError,
    HuaweiDoradoClient,
)
from atlas.modules.connectors.vendors.huawei_dorado.domain import HuaweiHealthStatus
from atlas.modules.connectors.vendors.huawei_dorado.manifest import (
    CAPACITY_CAPABILITY_ID,
    CONTROLLER_HEALTH_CAPABILITY_ID,
    SYSTEM_IDENTITY_CAPABILITY_ID,
    build_candidate_manifest,
)
from atlas.modules.connectors.vendors.huawei_dorado.synthetic import (
    SyntheticHuaweiDoradoTransport,
    SyntheticHuaweiFault,
    SyntheticHuaweiResponse,
)

NOW = datetime(2026, 8, 28, 12, 0, tzinfo=UTC)
INSTANCE_ID = "connector-instance.huawei-dorado.lab"
SYSTEM_ID = "2102350ABC"
SYSTEM_PATH = "/system/"
CONTROLLER_PATH = "/controller"
STORAGE_POOL_PATH = "/storagepool"


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
        target_id="target.huawei.dorado.lab",
        correlation_id="cor_huawei_candidate",
        permissions=frozenset({PACKAGE_REGISTER}),
    )


def connector_instance() -> ConnectorInstance:
    return ConnectorInstance(
        instance_id=INSTANCE_ID,
        package_id="connector.huawei.dorado.device-manager",
        package_version="0.1.0",
        organization_id="organization.test",
        environment_id="environment.lab",
        site_id="site.storage-lab",
        target_id="target.huawei.dorado.lab",
        enabled_capability_ids=frozenset(
            {SYSTEM_IDENTITY_CAPABILITY_ID, CONTROLLER_HEALTH_CAPABILITY_ID, CAPACITY_CAPABILITY_ID}
        ),
        secret_reference_ids=("secret.huawei.dorado.read-only",),
        lifecycle=InstanceLifecycle.DISABLED,
        health=ConnectorHealth.UNKNOWN,
        configuration_revision=1,
        created_at=NOW,
        created_by="subject.test.storage-engineer",
    )


def client(
    routes: dict[str, SyntheticHuaweiResponse], **limits: int
) -> tuple[HuaweiDoradoClient, SyntheticHuaweiDoradoTransport]:
    transport = SyntheticHuaweiDoradoTransport(routes)
    return (
        HuaweiDoradoClient(transport=transport, system_id=SYSTEM_ID, clock=lambda: NOW, **limits),
        transport,
    )


@pytest.mark.asyncio
async def test_candidate_manifest_is_c1_and_remains_quarantined() -> None:
    package_manifest = build_candidate_manifest(
        digest_sha256="e" * 64,
        network_destination="dorado.lab.example:8088",
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
            digest_sha256="f" * 64,
            network_destination="dorado.lab.example:8088/path",
        )


@pytest.mark.asyncio
async def test_system_identity_reads_real_fields() -> None:
    connector, transport = client(
        {
            SYSTEM_PATH: SyntheticHuaweiResponse(
                payload={
                    "error": {"code": 0},
                    "data": {
                        "MODEL": "OceanStor Dorado 8000 V6",
                        "SOFTWAREVERSION": "6.1.0.SPH12",
                        "HEALTHSTATUS": "1",
                    },
                }
            )
        }
    )

    identity = await connector.read_system_identity()

    assert identity.system_id == SYSTEM_ID
    assert identity.model == "OceanStor Dorado 8000 V6"
    assert identity.health_status is HuaweiHealthStatus.NORMAL
    assert identity.evidence_references[0].startswith("huawei-dorado://system#sha256:")
    assert transport.requests == [SYSTEM_PATH]


@pytest.mark.asyncio
async def test_controller_health_reads_all_controllers() -> None:
    connector, transport = client(
        {
            CONTROLLER_PATH: SyntheticHuaweiResponse(
                payload={
                    "error": {"code": 0},
                    "data": [
                        {"ID": "0A", "ROLE": "Primary", "HEALTHSTATUS": "1"},
                        {"ID": "0B", "ROLE": "Secondary", "HEALTHSTATUS": "2"},
                    ],
                }
            )
        }
    )

    controllers = await connector.read_controller_health()

    assert [item.controller_id for item in controllers] == ["0A", "0B"]
    assert controllers[0].health_status is HuaweiHealthStatus.NORMAL
    assert controllers[1].health_status is HuaweiHealthStatus.FAULTY
    assert transport.requests == [CONTROLLER_PATH]


@pytest.mark.asyncio
async def test_pool_capacity_reads_pools_and_computes_utilization() -> None:
    connector, transport = client(
        {
            STORAGE_POOL_PATH: SyntheticHuaweiResponse(
                payload={
                    "error": {"code": 0},
                    "data": [
                        {
                            "NAME": "StoragePool001",
                            "USERTOTALCAPACITY": "1000",
                            "USERFREECAPACITY": "220",
                            "HEALTHSTATUS": "1",
                        }
                    ],
                }
            )
        }
    )

    pools = await connector.read_pool_capacity()

    assert pools[0].pool_id == "StoragePool001"
    assert pools[0].used_capacity_percent == 78.0
    assert transport.requests == [STORAGE_POOL_PATH]


@pytest.mark.asyncio
async def test_vendor_logical_error_is_reported_safely_despite_http_200() -> None:
    connector, transport = client(
        {SYSTEM_PATH: SyntheticHuaweiResponse(payload={"error": {"code": 123, "description": "x"}})}
    )

    with pytest.raises(HuaweiConnectorError) as error:
        await connector.read_system_identity()

    assert error.value.code == "vendor_error_response"
    assert transport.requests == [SYSTEM_PATH]


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("fault", "code", "retryable"),
    [
        (SyntheticHuaweiFault.DENIED, "vendor_permission_denied", False),
        (SyntheticHuaweiFault.TIMEOUT, "target_timeout", True),
        (SyntheticHuaweiFault.THROTTLED, "vendor_rate_limited", True),
        (SyntheticHuaweiFault.UNAVAILABLE, "target_unavailable", True),
    ],
)
async def test_transport_faults_are_mapped_safely(
    fault: SyntheticHuaweiFault, code: str, retryable: bool
) -> None:
    connector, _transport = client({SYSTEM_PATH: SyntheticHuaweiResponse(fault=fault)})

    with pytest.raises(HuaweiConnectorError) as error:
        await connector.read_system_identity()

    assert error.value.code == code
    assert error.value.retryable is retryable


@pytest.mark.asyncio
async def test_malformed_and_oversized_responses_are_rejected() -> None:
    malformed, _ = client(
        {
            CONTROLLER_PATH: SyntheticHuaweiResponse(
                payload={"error": {"code": 0}, "data": "invalid"}
            )
        }
    )
    oversized, _ = client(
        {
            CONTROLLER_PATH: SyntheticHuaweiResponse(
                payload={
                    "error": {"code": 0},
                    "data": [
                        {"ID": "0A", "ROLE": "Primary", "HEALTHSTATUS": "1"},
                        {"ID": "0B", "ROLE": "Secondary", "HEALTHSTATUS": "1"},
                    ],
                }
            )
        },
        maximum_controllers=1,
    )
    oversized_bytes, _ = client(
        {
            SYSTEM_PATH: SyntheticHuaweiResponse(
                payload={"error": {"code": 0}, "data": {}, "padding": "x" * 128}
            )
        },
        maximum_response_bytes=64,
    )

    with pytest.raises(HuaweiConnectorError) as malformed_error:
        await malformed.read_controller_health()
    with pytest.raises(HuaweiConnectorError) as oversized_error:
        await oversized.read_controller_health()
    with pytest.raises(HuaweiConnectorError) as oversized_bytes_error:
        await oversized_bytes.read_system_identity()

    assert malformed_error.value.code == "malformed_vendor_response"
    assert oversized_error.value.code == "vendor_response_limit_exceeded"
    assert oversized_bytes_error.value.code == "vendor_response_limit_exceeded"


@pytest.mark.asyncio
async def test_self_test_uses_system_identity_and_detects_incompatible_shape() -> None:
    compatible_transport = SyntheticHuaweiDoradoTransport(
        {
            SYSTEM_PATH: SyntheticHuaweiResponse(
                payload={"error": {"code": 0}, "data": {"MODEL": "OceanStor Dorado 8000 V6"}}
            )
        }
    )
    incompatible_transport = SyntheticHuaweiDoradoTransport(
        {SYSTEM_PATH: SyntheticHuaweiResponse(payload={"error": {"code": 0}, "data": {}})}
    )

    compatible = await HuaweiDoradoClient(
        transport=compatible_transport, system_id=SYSTEM_ID, clock=lambda: NOW
    ).self_test(connector_instance())
    incompatible = await HuaweiDoradoClient(
        transport=incompatible_transport, system_id=SYSTEM_ID, clock=lambda: NOW
    ).self_test(connector_instance())

    assert compatible.health is ConnectorHealth.HEALTHY
    assert incompatible.health is ConnectorHealth.INCOMPATIBLE
    assert compatible_transport.requests == [SYSTEM_PATH]
    assert incompatible_transport.requests == [SYSTEM_PATH]


def test_synthetic_transport_has_no_external_or_secret_access() -> None:
    transport = SyntheticHuaweiDoradoTransport(
        {SYSTEM_PATH: SyntheticHuaweiResponse(payload={"error": {"code": 0}, "data": {}})}
    )

    assert transport.network_access is False
    assert transport.secret_access is False


def test_candidate_package_assets_are_strict_and_synthetic_only() -> None:
    package_root = Path(__file__).parents[2] / "mcp" / "connectors" / "huawei_dorado"
    schema = json.loads((package_root / "configuration.schema.json").read_text(encoding="utf-8"))
    provenance = json.loads((package_root / "source-provenance.json").read_text(encoding="utf-8"))

    assert schema["additionalProperties"] is False
    assert "credential_reference_id" in schema["required"]
    assert "system_id" in schema["required"]
    assert "password" not in schema["properties"]
    assert "username" not in schema["properties"]
    assert provenance["data_policy"] == "synthetic-only"
    assert provenance["production_credentials_present"] is False
    assert {source["method"] for source in provenance["capability_sources"]} == {"GET"}
