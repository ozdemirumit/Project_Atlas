from __future__ import annotations

from dataclasses import replace
from datetime import UTC, datetime

import pytest
from fastapi import FastAPI, Request
from fastapi.testclient import TestClient

from atlas.api.routes.bundled_connector_catalog import router
from atlas.api.security import (
    authorize_connector_instance_create,
    authorize_connector_instance_read,
    browser_session_subject,
)
from atlas.core.audit import AuditRecord
from atlas.modules.connectors.adapters.instance_creation_memory import (
    InMemoryConnectorInstanceRepository,
)
from atlas.modules.connectors.application.bundled_catalog import (
    BundledConnectorCatalogError,
    BundledConnectorCatalogService,
    build_hitachi_ops_center_bundled_descriptor,
)
from atlas.modules.connectors.domain.bundled_catalog import BundledConnectorDescriptor
from atlas.modules.connectors.domain.instance_creation import ConnectorInstanceRecord
from atlas.modules.identity.domain.models import (
    AssuranceLevel,
    AuthenticatedSubject,
    AuthenticationMethod,
    SubjectKind,
)

NOW = datetime(2026, 8, 25, 12, 0, tzinfo=UTC)


class CollectingAuditSink:
    def __init__(self) -> None:
        self.records: list[AuditRecord] = []

    async def record(self, record: AuditRecord) -> None:
        self.records.append(record)


def operator(subject_id: str = "subject.catalog-operator") -> AuthenticatedSubject:
    return AuthenticatedSubject(
        subject_id=subject_id,
        display_name="Catalog Operator",
        kind=SubjectKind.HUMAN,
        provider_id="provider.test",
        authentication_method=AuthenticationMethod.DEVELOPMENT,
        assurance_level=AssuranceLevel.DEVELOPMENT,
        authenticated_at=NOW,
        organization_id="organization.test",
        role_ids=("role.connector-operator",),
    )


def fixture() -> tuple[
    BundledConnectorCatalogService,
    BundledConnectorDescriptor,
    InMemoryConnectorInstanceRepository,
    CollectingAuditSink,
]:
    descriptor = build_hitachi_ops_center_bundled_descriptor()
    repository = InMemoryConnectorInstanceRepository()
    audit = CollectingAuditSink()
    service = BundledConnectorCatalogService(
        descriptors=(descriptor,),
        repository=repository,
        audit_sink=audit,
        environment_id="environment.test",
        clock=lambda: NOW,
    )
    return service, descriptor, repository, audit


async def create(
    service: BundledConnectorCatalogService,
    descriptor: BundledConnectorDescriptor,
    *,
    actor: AuthenticatedSubject | None = None,
    instance_key: str = "hitachi-lab",
    idempotency_key: str = "catalog-create-001",
    digest: str | None = None,
) -> ConnectorInstanceRecord:
    return await service.create_instance(
        actor=actor or operator(),
        catalog_item_id=descriptor.catalog_item_id,
        catalog_item_digest=digest or descriptor.canonical_digest,
        instance_key=instance_key,
        display_name="Hitachi Lab",
        purpose="Register bundled development catalog evidence without runtime authority.",
        acknowledged_instance_is_disabled_and_grants_no_authority=True,
        idempotency_key=idempotency_key,
        correlation_id="cor_bundled_catalog",
    )


@pytest.mark.asyncio
async def test_catalog_lists_verified_safe_descriptor_and_requires_human() -> None:
    service, descriptor, _, audit = fixture()

    result = await service.list(actor=operator(), correlation_id="cor_catalog_list")

    assert result == (descriptor,)
    assert descriptor.development_only and descriptor.catalog_evidence_only
    assert not descriptor.target_authority_granted
    assert not descriptor.credential_authority_granted
    assert not descriptor.capability_authority_granted
    assert not descriptor.network_authority_granted
    assert not descriptor.runtime_authority_granted
    assert audit.records[-1].result_code == "bundled_connector_catalog_listed"

    with pytest.raises(BundledConnectorCatalogError, match="human_required"):
        await service.list(
            actor=replace(operator(), kind=SubjectKind.SERVICE),
            correlation_id="cor_catalog_service",
        )


@pytest.mark.asyncio
async def test_create_is_idempotent_and_grants_no_authority() -> None:
    service, descriptor, repository, audit = fixture()

    record = await create(service, descriptor)
    repeated = await create(service, descriptor)

    assert repeated.reused and repeated.record_id == record.record_id
    assert record.instance_state == "disabled_unconfigured"
    assert record.eligible_for_configuration_governance
    assert not record.target_configured and not record.credentials_resolved
    assert not record.connector_enabled and not record.runtime_trust_granted
    assert not record.execution_authorized and not record.deployment_approved
    assert not record.infrastructure_mutation_performed
    assert record.source_installation_receipt_id.startswith("bundled-installation-receipt.")
    assert (
        len(
            await repository.list_scope(
                organization_id=record.organization_id, environment_id=record.environment_id
            )
        )
        == 1
    )
    assert [item.result_code for item in audit.records] == [
        "bundled_connector_instance_creation_requested",
        "bundled_connector_instance_creation_completed",
    ]


@pytest.mark.asyncio
async def test_create_rejects_digest_idempotency_and_instance_key_conflicts() -> None:
    service, descriptor, _, _ = fixture()

    with pytest.raises(BundledConnectorCatalogError, match="digest_conflict"):
        await create(service, descriptor, digest="f" * 64)

    await create(service, descriptor)
    with pytest.raises(BundledConnectorCatalogError, match="idempotency_conflict"):
        await create(service, descriptor, instance_key="hitachi-other")
    with pytest.raises(BundledConnectorCatalogError, match="instance_key_conflict"):
        await create(
            service,
            descriptor,
            actor=operator("subject.second-catalog-operator"),
            idempotency_key="catalog-create-002",
        )


def test_catalog_router_uses_safe_envelopes_and_existing_authorization_dependencies() -> None:
    service, descriptor, _, _ = fixture()
    app = FastAPI()
    app.state.bundled_connector_catalog_service = service

    @app.middleware("http")
    async def correlation_id(request: Request, call_next):  # type: ignore[no-untyped-def]
        request.state.correlation_id = "cor_catalog_api"
        return await call_next(request)

    app.dependency_overrides[browser_session_subject] = operator
    app.dependency_overrides[authorize_connector_instance_read] = lambda: object()
    app.dependency_overrides[authorize_connector_instance_create] = lambda: object()
    app.include_router(router, prefix="/api/v1")
    payload = {
        "schema_version": "atlas.bundled-connector-instance-input.v1",
        "catalog_item_digest": descriptor.canonical_digest,
        "instance_key": "hitachi-api",
        "display_name": "Hitachi API",
        "purpose": "Register bundled development catalog evidence without runtime authority.",
        "acknowledged_instance_is_disabled_and_grants_no_authority": True,
    }

    with TestClient(app) as client:
        listed = client.get("/api/v1/connectors/catalog")
        created = client.post(
            f"/api/v1/connectors/catalog/{descriptor.catalog_item_id}/instances",
            json=payload,
            headers={"Idempotency-Key": "catalog-api-001"},
        )

    assert listed.status_code == 200 and created.status_code == 201
    assert listed.headers["Cache-Control"] == created.headers["Cache-Control"] == "no-store"
    listed_data = listed.json()["data"][0]
    assert listed_data["catalog_evidence_only"] is True
    assert listed_data["network_authority_granted"] is False
    created_data = created.json()["data"]
    assert created_data["instance_state"] == "disabled_unconfigured"
    assert created_data["connector_enabled"] is False
    assert created_data["execution_authorized"] is False
    rendered = created.text.lower()
    for hidden in (
        "source_installation_receipt",
        "installation_store",
        "idempotency_key",
        "request_fingerprint",
        "package_digest",
        "target_endpoint",
        "credential_reference",
        "authorization_header",
    ):
        assert hidden not in rendered
