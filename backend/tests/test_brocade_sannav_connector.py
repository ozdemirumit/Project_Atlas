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
from atlas.modules.connectors.vendors.brocade_sannav.client import (
    BrocadeConnectorError,
    BrocadeSanNavClient,
)
from atlas.modules.connectors.vendors.brocade_sannav.manifest import (
    FABRIC_HEALTH_CAPABILITY_ID,
    FABRIC_INVENTORY_CAPABILITY_ID,
    build_candidate_manifest,
)
from atlas.modules.connectors.vendors.brocade_sannav.synthetic import (
    SyntheticBrocadeFault,
    SyntheticBrocadeResponse,
    SyntheticBrocadeSanNavTransport,
)

NOW = datetime(2026, 8, 28, 12, 0, tzinfo=UTC)
FABRICS_PATH = "/external-api/v1/discovery/fabrics/"
FABRIC_WWN = "10:00:00:05:1e:35:1a:00"
OTHER_FABRIC_WWN = "10:00:00:05:1e:35:2b:11"
FABRIC_MEMBERS_PATH = f"/external-api/v1/discovery/fabric-members/?principalSwitchWWN={FABRIC_WWN}"
FAULT_EVENTS_PATH = "/external-api/v2/fault/events/"


class CollectingAuditSink:
    def __init__(self) -> None:
        self.records: list[AuditRecord] = []

    async def record(self, event: AuditRecord) -> None:
        self.records.append(event)


def access_context() -> ConnectorAccessContext:
    return ConnectorAccessContext(
        subject_id="subject.test.san-engineer",
        actor_type="human",
        authentication_method="development",
        assurance_level="development",
        organization_id="organization.test",
        environment_id="environment.lab",
        site_id="site.storage-lab",
        target_id="target.brocade.sannav.lab",
        correlation_id="cor_brocade_candidate",
        permissions=frozenset({PACKAGE_REGISTER}),
    )


def connector_instance() -> ConnectorInstance:
    return ConnectorInstance(
        instance_id="instance.brocade.sannav.lab",
        package_id="connector.brocade.sannav.management-portal",
        package_version="0.1.0",
        organization_id="organization.test",
        environment_id="environment.lab",
        site_id="site.storage-lab",
        target_id="target.brocade.sannav.lab",
        enabled_capability_ids=frozenset(
            {FABRIC_INVENTORY_CAPABILITY_ID, FABRIC_HEALTH_CAPABILITY_ID}
        ),
        secret_reference_ids=("secret.brocade.sannav.read-only",),
        lifecycle=InstanceLifecycle.DISABLED,
        health=ConnectorHealth.UNKNOWN,
        configuration_revision=1,
        created_at=NOW,
        created_by="subject.test.san-engineer",
    )


def client(routes: dict[str, SyntheticBrocadeResponse], **limits: int) -> BrocadeSanNavClient:
    return BrocadeSanNavClient(
        transport=SyntheticBrocadeSanNavTransport(routes),
        allowed_fabric_wwns=frozenset({FABRIC_WWN, OTHER_FABRIC_WWN}),
        clock=lambda: NOW,
        **limits,
    )


@pytest.mark.asyncio
async def test_candidate_manifest_is_c1_and_remains_quarantined() -> None:
    package_manifest = build_candidate_manifest(
        digest_sha256="c" * 64,
        network_destination="sannav.lab.example:443",
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
            network_destination="sannav.lab.example:443/path",
        )


@pytest.mark.asyncio
async def test_inventory_reads_fabrics_then_their_member_switches() -> None:
    transport = SyntheticBrocadeSanNavTransport(
        {
            FABRICS_PATH: SyntheticBrocadeResponse(
                payload={
                    "Fabrics": [
                        {"principalSwitchWwn": FABRIC_WWN, "name": "Fabric-A"},
                        {"principalSwitchWwn": "10:00:00:05:1e:99:99:99", "name": "Unbound"},
                    ]
                }
            ),
            FABRIC_MEMBERS_PATH: SyntheticBrocadeResponse(
                payload={"Switches": [{"ipAddress": "192.0.2.10"}, {"ipAddress": "192.0.2.11"}]}
            ),
        }
    )
    connector = BrocadeSanNavClient(
        transport=transport,
        allowed_fabric_wwns=frozenset({FABRIC_WWN}),
        clock=lambda: NOW,
    )

    result = await connector.read_inventory()

    assert [fabric.principal_switch_wwn for fabric in result.fabrics] == [FABRIC_WWN]
    assert len(result.switches) == 2
    assert {switch.ip_address for switch in result.switches} == {"192.0.2.10", "192.0.2.11"}
    assert result.evidence_references[0].startswith("brocade-sannav://discovery/fabrics#sha256:")
    assert transport.requests == [FABRICS_PATH, FABRIC_MEMBERS_PATH]


@pytest.mark.asyncio
async def test_fault_summary_counts_events_defensively_across_envelope_shapes() -> None:
    for envelope_key in ("events", "Events", "data", "Data"):
        connector = client(
            {FAULT_EVENTS_PATH: SyntheticBrocadeResponse(payload={envelope_key: [{}, {}, {}]})}
        )

        result = await connector.read_fabric_fault_summary(FABRIC_WWN)

        assert result.event_count == 3
        assert result.fabric_principal_switch_wwn == FABRIC_WWN
        assert result.evidence_references[0].startswith(
            f"brocade-sannav://fault/events/{FABRIC_WWN}#sha256:"
        )


@pytest.mark.asyncio
async def test_fault_summary_falls_back_to_zero_for_an_unrecognized_shape() -> None:
    connector = client({FAULT_EVENTS_PATH: SyntheticBrocadeResponse(payload={"unexpected": True})})

    result = await connector.read_fabric_fault_summary(FABRIC_WWN)

    assert result.event_count == 0


@pytest.mark.asyncio
async def test_invalid_target_is_rejected_before_transport_access() -> None:
    transport = SyntheticBrocadeSanNavTransport({})
    connector = BrocadeSanNavClient(
        transport=transport,
        allowed_fabric_wwns=frozenset({FABRIC_WWN}),
        clock=lambda: NOW,
    )

    with pytest.raises(BrocadeConnectorError) as error:
        await connector.read_fabric_fault_summary("../../other-target")

    assert error.value.code == "invalid_fabric_identifier"
    assert transport.requests == []

    with pytest.raises(BrocadeConnectorError) as binding_error:
        await connector.read_fabric_fault_summary(OTHER_FABRIC_WWN)
    assert binding_error.value.code == "target_not_bound"
    assert transport.requests == []


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("fault", "code", "retryable"),
    [
        (SyntheticBrocadeFault.DENIED, "vendor_permission_denied", False),
        (SyntheticBrocadeFault.TIMEOUT, "target_timeout", True),
        (SyntheticBrocadeFault.THROTTLED, "vendor_rate_limited", True),
        (SyntheticBrocadeFault.UNAVAILABLE, "target_unavailable", True),
    ],
)
async def test_transport_faults_are_mapped_safely(
    fault: SyntheticBrocadeFault, code: str, retryable: bool
) -> None:
    connector = client({FABRICS_PATH: SyntheticBrocadeResponse(fault=fault)})

    with pytest.raises(BrocadeConnectorError) as error:
        await connector.read_inventory()

    assert error.value.code == code
    assert error.value.retryable is retryable


@pytest.mark.asyncio
async def test_malformed_and_oversized_inventory_are_rejected() -> None:
    malformed = client({FABRICS_PATH: SyntheticBrocadeResponse(payload={"Fabrics": "invalid"})})
    oversized = client(
        {
            FABRICS_PATH: SyntheticBrocadeResponse(
                payload={
                    "Fabrics": [
                        {"principalSwitchWwn": FABRIC_WWN, "name": "A"},
                        {"principalSwitchWwn": OTHER_FABRIC_WWN, "name": "B"},
                    ]
                }
            )
        },
        maximum_fabrics=1,
    )
    oversized_bytes = client(
        {FABRICS_PATH: SyntheticBrocadeResponse(payload={"Fabrics": [], "padding": "x" * 128})},
        maximum_response_bytes=64,
    )

    with pytest.raises(BrocadeConnectorError) as malformed_error:
        await malformed.read_inventory()
    with pytest.raises(BrocadeConnectorError) as oversized_error:
        await oversized.read_inventory()
    with pytest.raises(BrocadeConnectorError) as oversized_bytes_error:
        await oversized_bytes.read_inventory()

    assert malformed_error.value.code == "malformed_vendor_response"
    assert oversized_error.value.code == "vendor_response_limit_exceeded"
    assert oversized_bytes_error.value.code == "vendor_response_limit_exceeded"


@pytest.mark.asyncio
async def test_self_test_uses_fabric_discovery_and_detects_incompatible_shape() -> None:
    compatible_transport = SyntheticBrocadeSanNavTransport(
        {FABRICS_PATH: SyntheticBrocadeResponse(payload={"Fabrics": []})}
    )
    incompatible_transport = SyntheticBrocadeSanNavTransport(
        {FABRICS_PATH: SyntheticBrocadeResponse(payload={"unexpected": True})}
    )

    compatible = await BrocadeSanNavClient(
        transport=compatible_transport,
        allowed_fabric_wwns=frozenset({FABRIC_WWN}),
        clock=lambda: NOW,
    ).self_test(connector_instance())
    incompatible = await BrocadeSanNavClient(
        transport=incompatible_transport,
        allowed_fabric_wwns=frozenset({FABRIC_WWN}),
        clock=lambda: NOW,
    ).self_test(connector_instance())

    assert compatible.health is ConnectorHealth.HEALTHY
    assert incompatible.health is ConnectorHealth.INCOMPATIBLE
    assert compatible_transport.requests == [FABRICS_PATH]
    assert incompatible_transport.requests == [FABRICS_PATH]


def test_synthetic_transport_has_no_external_or_secret_access() -> None:
    transport = SyntheticBrocadeSanNavTransport(
        {FABRICS_PATH: SyntheticBrocadeResponse(payload={"Fabrics": []})}
    )

    assert transport.network_access is False
    assert transport.secret_access is False


def test_candidate_package_assets_are_strict_and_synthetic_only() -> None:
    package_root = Path(__file__).parents[2] / "mcp" / "connectors" / "brocade_sannav"
    schema = json.loads((package_root / "configuration.schema.json").read_text(encoding="utf-8"))
    provenance = json.loads((package_root / "source-provenance.json").read_text(encoding="utf-8"))

    assert schema["additionalProperties"] is False
    assert "credential_reference_id" in schema["required"]
    assert "allowed_fabric_wwns" in schema["required"]
    assert "password" not in schema["properties"]
    assert provenance["data_policy"] == "synthetic-only"
    assert provenance["production_credentials_present"] is False
    assert {source["method"] for source in provenance["capability_sources"]} == {"GET", "POST"}
