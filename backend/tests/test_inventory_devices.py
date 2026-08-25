from __future__ import annotations

import asyncio
import base64
from datetime import UTC, datetime

from fastapi.testclient import TestClient

from atlas.api.app import create_app
from atlas.core.audit import AuditRecord
from atlas.core.capabilities import CapabilityClass
from atlas.core.config import Settings
from atlas.modules.authorization.application.bootstrap import (
    inventory_device_permission_definitions,
    inventory_device_scope,
)
from atlas.modules.authorization.application.service import AuthorizationService
from atlas.modules.authorization.domain.models import RoleAssignment, RoleDefinition
from atlas.modules.identity.domain.models import (
    AssuranceLevel,
    AuthenticatedSubject,
    AuthenticationInput,
    AuthenticationMethod,
    SubjectKind,
)
from atlas.modules.inventory.adapters.memory import InMemoryInventoryDeviceRepository
from atlas.modules.inventory.application.service import InventoryDeviceService
from atlas.modules.inventory.domain.devices import InventoryDeviceType

NOW = datetime(2026, 8, 11, 12, 0, tzinfo=UTC)
ORGANIZATION_ID = "organization.enterprise"
ROLE_ID = "role.inventory-administrator"


class CollectingAuditSink:
    def __init__(self) -> None:
        self.records: list[AuditRecord] = []

    async def record(self, event: AuditRecord) -> None:
        self.records.append(event)


class EnterpriseProvider:
    def __init__(self, subject: AuthenticatedSubject) -> None:
        self.subject = subject

    async def authenticate(
        self, authentication_input: AuthenticationInput
    ) -> AuthenticatedSubject | None:
        if (
            authentication_input.authorization_scheme != "basic"
            or authentication_input.credential is None
        ):
            return None
        decoded = base64.b64decode(authentication_input.credential).decode()
        return self.subject if decoded == "inventory-admin:correct-password" else None


def enterprise_subject(
    *,
    roles: tuple[str, ...] = (ROLE_ID,),
    organization_id: str = ORGANIZATION_ID,
) -> AuthenticatedSubject:
    return AuthenticatedSubject(
        subject_id="subject.enterprise.inventory-admin",
        display_name="Inventory Administrator",
        kind=SubjectKind.HUMAN,
        provider_id="provider.ldap.enterprise",
        authentication_method=AuthenticationMethod.LDAP,
        assurance_level=AssuranceLevel.MULTI_FACTOR,
        authenticated_at=NOW,
        organization_id=organization_id,
        role_ids=roles,
    )


def inventory_authorization(sink: CollectingAuditSink) -> AuthorizationService:
    permissions = inventory_device_permission_definitions()
    role = RoleDefinition(
        role_id=ROLE_ID,
        version=1,
        permissions=frozenset(item.permission_id for item in permissions),
    )
    return AuthorizationService(
        permissions=permissions,
        roles=(role,),
        assignments=tuple(
            RoleAssignment(
                assignment_id=f"assignment.inventory-admin.{index}",
                version=1,
                subject_id="subject.enterprise.inventory-admin",
                role_id=ROLE_ID,
                scope=inventory_device_scope(ORGANIZATION_ID, "test", capability_class),
                valid_from=datetime.min.replace(tzinfo=UTC),
            )
            for index, capability_class in enumerate(
                (CapabilityClass.C0_INFORMATIONAL, CapabilityClass.C2_DIAGNOSTIC), start=1
            )
        ),
        audit_sink=sink,
        clock=lambda: NOW,
    )


class InventoryFixture:
    def __init__(self, *, roles: tuple[str, ...] = (ROLE_ID,)) -> None:
        self.sink = CollectingAuditSink()
        self.repository = InMemoryInventoryDeviceRepository()
        self.service = InventoryDeviceService(
            repository=self.repository,
            audit_sink=self.sink,
            environment_id="environment.test",
            clock=lambda: NOW,
        )
        subject = enterprise_subject(roles=roles)
        self.app = create_app(
            Settings(environment="test", development_identity_enabled=False),
            audit_sink=self.sink,
            identity_provider=EnterpriseProvider(subject),
            authorization_service=inventory_authorization(self.sink),
            inventory_device_service=self.service,
        )


def login(client: TestClient) -> str:
    response = client.post(
        "/api/v1/authentication/sessions",
        json={"username": "inventory-admin", "password": "correct-password"},
    )
    assert response.status_code == 201
    return str(response.headers["X-CSRF-Token"])


def create_payload() -> dict[str, object]:
    return {
        "schema_version": "atlas.inventory-device-create-input.v1",
        "device_key": "storage.vsp-01",
        "display_name": "Primary VSP",
        "device_type": "storage",
        "vendor": "Hitachi Vantara",
        "model": "VSP E790",
        "serial_number": "SN-TEST-0001",
        "management_address": "vsp-01.lab.example",
        "purpose": "Register the array for governed inventory and read-only health correlation.",
        "acknowledged_no_credentials_or_infrastructure_action": True,
    }


def update_payload(*, expected_version: int = 1) -> dict[str, object]:
    return {
        "schema_version": "atlas.inventory-device-update-input.v1",
        "expected_version": expected_version,
        "display_name": "Primary VSP Production",
        "device_type": "storage",
        "vendor": "Hitachi Vantara",
        "model": "VSP E790H",
        "serial_number": "SN-TEST-0001-UPDATED",
        "management_address": "VSP-01-MGMT.LAB.EXAMPLE",
        "purpose": "Maintain current inventory metadata for read-only health correlation.",
    }


def test_inventory_requires_authenticated_authorized_browser_session() -> None:
    fixture = InventoryFixture()
    with TestClient(fixture.app) as client:
        unauthenticated = client.get("/api/v1/inventory/devices")
        basic = base64.b64encode(b"inventory-admin:correct-password").decode()
        direct_mutation = client.post(
            "/api/v1/inventory/devices",
            json=create_payload(),
            headers={
                "Authorization": f"Basic {basic}",
                "Idempotency-Key": "inventory-direct-create",
            },
        )

    assert unauthenticated.status_code == 401
    assert unauthenticated.json()["code"] == "authentication_required"
    assert direct_mutation.status_code == 403
    assert direct_mutation.json()["code"] == "browser_session_required"

    denied_fixture = InventoryFixture(roles=())
    with TestClient(denied_fixture.app) as client:
        login(client)
        denied = client.get("/api/v1/inventory/devices")

    assert denied.status_code == 403
    assert denied.json()["code"] == "authorization_denied"
    assert "inventory" not in denied.json()["detail"].lower()


def test_create_list_and_retire_preserve_history_without_execution_authority() -> None:
    fixture = InventoryFixture()
    with TestClient(fixture.app) as client:
        csrf = login(client)
        created = client.post(
            "/api/v1/inventory/devices",
            json=create_payload(),
            headers={"X-CSRF-Token": csrf, "Idempotency-Key": "inventory-create-0001"},
        )
        inventory = client.get("/api/v1/inventory/devices?lifecycle=active&limit=20")
        record = created.json()["data"]
        retired = client.post(
            f"/api/v1/inventory/devices/{record['device_id']}/retirements",
            json={
                "schema_version": "atlas.inventory-device-retirement-input.v1",
                "expected_version": record["version"],
                "reason": "The lab array was decommissioned after the approved migration window.",
                "acknowledged_retirement_preserves_history_and_stops_active_use": True,
            },
            headers={"X-CSRF-Token": csrf, "Idempotency-Key": "inventory-retire-0001"},
        )
        retired_inventory = client.get("/api/v1/inventory/devices?lifecycle=retired")

    assert created.status_code == 201
    assert created.headers["Cache-Control"] == "no-store"
    assert record["lifecycle"] == "active"
    assert record["management_address"] == "vsp-01.lab.example"
    assert "credential" not in created.text.lower()
    assert "password" not in created.text.lower()
    assert "idempotency_key" not in created.text
    assert "request_fingerprint" not in created.text
    assert inventory.status_code == 200
    assert inventory.json()["data"]["durable"] is False
    assert [item["device_key"] for item in inventory.json()["data"]["devices"]] == [
        "storage.vsp-01"
    ]
    assert retired.status_code == 200
    assert retired.json()["data"]["lifecycle"] == "retired"
    assert retired.json()["data"]["version"] == 2
    assert retired_inventory.json()["data"]["devices"][0]["device_id"] == record["device_id"]
    inventory_events = [
        item for item in fixture.sink.records if item.event_type == "atlas.inventory.device"
    ]
    assert {item.result_code for item in inventory_events} >= {
        "inventory_device_created",
        "inventory_device_inventory_read",
        "inventory_device_retired",
    }
    assert all(item.resource_type == "resource.inventory.device" for item in inventory_events)


def test_create_and_retire_are_idempotent_and_version_bound() -> None:
    fixture = InventoryFixture()
    with TestClient(fixture.app) as client:
        csrf = login(client)
        headers = {"X-CSRF-Token": csrf, "Idempotency-Key": "inventory-create-0002"}
        first = client.post("/api/v1/inventory/devices", json=create_payload(), headers=headers)
        replay = client.post("/api/v1/inventory/devices", json=create_payload(), headers=headers)
        record = first.json()["data"]
        stale = client.post(
            f"/api/v1/inventory/devices/{record['device_id']}/retirements",
            json={
                "expected_version": 99,
                "reason": "Retire the exact device after the governed decommissioning workflow.",
                "acknowledged_retirement_preserves_history_and_stops_active_use": True,
            },
            headers={"X-CSRF-Token": csrf, "Idempotency-Key": "inventory-retire-stale"},
        )

    assert first.status_code == 201
    assert replay.status_code == 201
    assert replay.json()["data"]["reused"] is True
    assert stale.status_code == 409
    assert stale.json()["code"] == "inventory_device_version_conflict"


def test_create_rejects_missing_safety_acknowledgement_without_record() -> None:
    fixture = InventoryFixture()
    payload = create_payload()
    payload["acknowledged_no_credentials_or_infrastructure_action"] = False
    with TestClient(fixture.app) as client:
        csrf = login(client)
        response = client.post(
            "/api/v1/inventory/devices",
            json=payload,
            headers={"X-CSRF-Token": csrf, "Idempotency-Key": "inventory-create-0003"},
        )
        inventory = client.get("/api/v1/inventory/devices")

    assert response.status_code == 422
    assert response.json()["code"] == "inventory_device_acknowledgement_required"
    assert inventory.json()["data"]["devices"] == []


def test_update_inventory_device_changes_mutable_metadata_and_digest() -> None:
    fixture = InventoryFixture()
    with TestClient(fixture.app) as client:
        csrf = login(client)
        created = client.post(
            "/api/v1/inventory/devices",
            json=create_payload(),
            headers={"X-CSRF-Token": csrf, "Idempotency-Key": "inventory-create-update"},
        ).json()["data"]
        updated = client.patch(
            f"/api/v1/inventory/devices/{created['device_id']}",
            json=update_payload(expected_version=created["version"]),
            headers={"X-CSRF-Token": csrf},
        )

    assert updated.status_code == 200
    record = updated.json()["data"]
    assert record["device_key"] == created["device_key"]
    assert record["display_name"] == "Primary VSP Production"
    assert record["model"] == "VSP E790H"
    assert record["management_address"] == "vsp-01-mgmt.lab.example"
    assert record["version"] == created["version"] + 1
    assert record["canonical_digest"] != created["canonical_digest"]
    assert record["updated_by"] == "subject.enterprise.inventory-admin"
    assert {event.result_code for event in fixture.sink.records} >= {
        "inventory_device_update_requested",
        "inventory_device_updated",
    }


def test_update_inventory_device_rejects_version_conflict() -> None:
    fixture = InventoryFixture()
    with TestClient(fixture.app) as client:
        csrf = login(client)
        created = client.post(
            "/api/v1/inventory/devices",
            json=create_payload(),
            headers={"X-CSRF-Token": csrf, "Idempotency-Key": "inventory-create-stale"},
        ).json()["data"]
        stale = client.patch(
            f"/api/v1/inventory/devices/{created['device_id']}",
            json=update_payload(expected_version=99),
            headers={"X-CSRF-Token": csrf},
        )

    assert stale.status_code == 409
    assert stale.json()["code"] == "inventory_device_version_conflict"


def test_update_inventory_device_hides_foreign_scope_and_unknown_records() -> None:
    fixture = InventoryFixture()
    foreign = asyncio.run(
        fixture.service.create(
            actor=enterprise_subject(organization_id="organization.foreign"),
            device_key="storage.foreign-01",
            display_name="Foreign VSP",
            device_type=InventoryDeviceType.STORAGE,
            vendor="Hitachi Vantara",
            model="VSP E790",
            serial_number=None,
            management_address=None,
            purpose="Register foreign-scope metadata for tenant isolation verification.",
            acknowledged_no_credentials_or_infrastructure_action=True,
            idempotency_key="inventory-create-foreign",
            correlation_id="correlation.inventory.foreign",
        )
    )
    with TestClient(fixture.app) as client:
        csrf = login(client)
        foreign_response = client.patch(
            f"/api/v1/inventory/devices/{foreign.device_id}",
            json={
                "expected_version": foreign.version,
                "display_name": "Foreign Device Hidden",
            },
            headers={"X-CSRF-Token": csrf},
        )
        unknown_response = client.patch(
            "/api/v1/inventory/devices/inventory-device.unknown",
            json={"expected_version": 1, "display_name": "Unknown Device"},
            headers={"X-CSRF-Token": csrf},
        )

    assert foreign_response.status_code == 404
    assert foreign_response.json()["code"] == "inventory_device_not_found"
    assert unknown_response.status_code == 404
    assert unknown_response.json()["code"] == "inventory_device_not_found"


def test_update_inventory_device_rejects_immutable_device_key() -> None:
    fixture = InventoryFixture()
    payload = update_payload()
    payload["device_key"] = "storage.renamed"
    with TestClient(fixture.app) as client:
        csrf = login(client)
        created = client.post(
            "/api/v1/inventory/devices",
            json=create_payload(),
            headers={"X-CSRF-Token": csrf, "Idempotency-Key": "inventory-create-key"},
        ).json()["data"]
        response = client.patch(
            f"/api/v1/inventory/devices/{created['device_id']}",
            json=payload,
            headers={"X-CSRF-Token": csrf},
        )

    assert response.status_code == 422
    assert response.json()["code"] == "validation_failed"


def test_reactivate_inventory_device_restores_active_lifecycle_and_clears_retirement() -> None:
    fixture = InventoryFixture()
    with TestClient(fixture.app) as client:
        csrf = login(client)
        created = client.post(
            "/api/v1/inventory/devices",
            json=create_payload(),
            headers={"X-CSRF-Token": csrf, "Idempotency-Key": "inventory-create-reactivate"},
        ).json()["data"]
        retired = client.post(
            f"/api/v1/inventory/devices/{created['device_id']}/retirements",
            json={
                "expected_version": created["version"],
                "reason": "Retire this inventory record for the approved maintenance lifecycle.",
                "acknowledged_retirement_preserves_history_and_stops_active_use": True,
            },
            headers={"X-CSRF-Token": csrf, "Idempotency-Key": "inventory-retire-reactivate"},
        ).json()["data"]
        reactivated = client.post(
            f"/api/v1/inventory/devices/{created['device_id']}/reactivations",
            json={
                "schema_version": "atlas.inventory-device-reactivation-input.v1",
                "expected_version": retired["version"],
            },
            headers={"X-CSRF-Token": csrf},
        )
        active_inventory = client.get("/api/v1/inventory/devices?lifecycle=active")

    assert reactivated.status_code == 200
    record = reactivated.json()["data"]
    assert record["lifecycle"] == "active"
    assert record["version"] == retired["version"] + 1
    assert record["retired_by"] is None
    assert record["retired_at"] is None
    assert record["retirement_reason"] is None
    assert record["device_id"] in {
        item["device_id"] for item in active_inventory.json()["data"]["devices"]
    }
    assert {event.result_code for event in fixture.sink.records} >= {
        "inventory_device_reactivation_requested",
        "inventory_device_reactivated",
    }
