from __future__ import annotations

import asyncio
from dataclasses import asdict, replace
from datetime import timedelta
from pathlib import Path
from typing import Any

import pytest
from fastapi.testclient import TestClient
from test_bounded_invocation import bounded_fixture, invoke_bounded
from test_browser_sessions import BasicTestIdentityProvider, login, settings
from test_package_acquisition import CollectingAuditSink
from test_runtime_activation import FailSecondAuditSink
from test_target_session import target_session_operator

from atlas.api.app import create_app
from atlas.modules.authorization.application.service import AuthorizationService
from atlas.modules.authorization.domain.models import PermissionDefinition
from atlas.modules.connectors.adapters.invocation_evidence_memory import (
    InMemoryConnectorInvocationEvidencePolicySource,
    InMemoryConnectorInvocationEvidenceRepository,
)
from atlas.modules.connectors.adapters.invocation_evidence_postgres import (
    PostgreSQLConnectorInvocationEvidenceRepository,
)
from atlas.modules.connectors.adapters.invocation_evidence_synthetic import (
    SyntheticConnectorInvocationEvidenceAdapter,
)
from atlas.modules.connectors.adapters.invocation_permission import (
    AuthorizationConnectorCapabilityPermissionAuthorizer,
)
from atlas.modules.connectors.application.invocation_authorization_ports import (
    ConnectorInvocationAuthorizationError,
)
from atlas.modules.connectors.application.invocation_evidence import (
    ConnectorInvocationEvidenceService,
    build_development_connector_invocation_evidence_policy,
)
from atlas.modules.connectors.application.invocation_evidence_ports import (
    ConnectorInvocationEvidenceError,
    ConnectorInvocationEvidenceUncertainError,
)
from atlas.modules.connectors.domain.bounded_invocation import ConnectorBoundedInvocationRecord
from atlas.modules.connectors.domain.invocation_evidence import (
    ConnectorInvocationEvidenceInstruction,
    ConnectorInvocationEvidencePolicySnapshot,
    ConnectorInvocationEvidenceReceipt,
    ConnectorInvocationEvidenceRecord,
)
from atlas.modules.identity.domain.models import AuthenticatedSubject

ACKNOWLEDGEMENT_FIELD = (
    "acknowledged_ingestion_is_one_way_and_does_not_publish_knowledge_or_grant_authority"
)


class RecordingPermissionAuthorizer:
    def __init__(self, *, deny: bool = False) -> None:
        self.deny = deny
        self.calls: list[tuple[str, str, str]] = []

    async def authorize(
        self,
        *,
        actor: AuthenticatedSubject,
        permission_id: str,
        capability_id: str,
        capability_class: str,
        organization_id: str,
        environment_id: str,
        correlation_id: str,
    ) -> None:
        del actor, organization_id, environment_id, correlation_id
        self.calls.append((permission_id, capability_id, capability_class))
        if self.deny:
            raise ConnectorInvocationEvidenceError(
                "invocation_evidence_capability_permission_denied"
            )


class UncertainAdapter:
    def __init__(self) -> None:
        self.calls = 0

    async def ingest(
        self, instruction: ConnectorInvocationEvidenceInstruction
    ) -> ConnectorInvocationEvidenceReceipt:
        del instruction
        self.calls += 1
        raise ConnectorInvocationEvidenceUncertainError(
            "invocation_evidence_storage_outcome_uncertain"
        )


class AlteredReceiptAdapter(SyntheticConnectorInvocationEvidenceAdapter):
    async def ingest(
        self, instruction: ConnectorInvocationEvidenceInstruction
    ) -> ConnectorInvocationEvidenceReceipt:
        receipt = await super().ingest(instruction)
        altered = replace(receipt, classification="classification.restricted")
        return replace(altered, canonical_digest=self._receipt_digest(altered))


class BlockingAdapter(SyntheticConnectorInvocationEvidenceAdapter):
    def __init__(self) -> None:
        super().__init__()
        self.started = asyncio.Event()
        self.release = asyncio.Event()

    async def ingest(
        self, instruction: ConnectorInvocationEvidenceInstruction
    ) -> ConnectorInvocationEvidenceReceipt:
        self.started.set()
        await self.release.wait()
        return await super().ingest(instruction)


async def evidence_fixture(
    *,
    audit_sink: CollectingAuditSink | FailSecondAuditSink | None = None,
    permission_authorizer: RecordingPermissionAuthorizer | None = None,
    adapter: SyntheticConnectorInvocationEvidenceAdapter
    | UncertainAdapter
    | AlteredReceiptAdapter
    | BlockingAdapter
    | None = None,
) -> tuple[
    ConnectorInvocationEvidenceService,
    ConnectorBoundedInvocationRecord,
    ConnectorInvocationEvidencePolicySnapshot,
    RecordingPermissionAuthorizer,
    SyntheticConnectorInvocationEvidenceAdapter
    | UncertainAdapter
    | AlteredReceiptAdapter
    | BlockingAdapter,
    tuple[Any, ...],
]:
    bounded = await bounded_fixture()
    bounded_service = bounded[0]
    invocation = await invoke_bounded(bounded_service, bounded[6], bounded[7])
    policy = build_development_connector_invocation_evidence_policy(
        organization_id=invocation.organization_id,
        environment_id=invocation.environment_id,
        issued_at=invocation.completed_at - timedelta(hours=1),
        expires_at=invocation.completed_at + timedelta(days=1),
    )
    authorizer = permission_authorizer or RecordingPermissionAuthorizer()
    resolved_adapter = adapter or SyntheticConnectorInvocationEvidenceAdapter(
        clock=lambda: invocation.completed_at
    )
    service = ConnectorInvocationEvidenceService(
        repository=InMemoryConnectorInvocationEvidenceRepository(),
        source=bounded_service,
        policy_source=InMemoryConnectorInvocationEvidencePolicySource((policy,)),
        permission_authorizer=authorizer,
        adapter=resolved_adapter,
        audit_sink=audit_sink or CollectingAuditSink(),
        environment_id=invocation.environment_id,
        clock=lambda: invocation.completed_at,
    )
    return service, invocation, policy, authorizer, resolved_adapter, bounded


async def ingest_evidence(
    service: ConnectorInvocationEvidenceService,
    invocation: ConnectorBoundedInvocationRecord,
    policy: ConnectorInvocationEvidencePolicySnapshot,
    *,
    actor: AuthenticatedSubject | None = None,
    key: str = "invocation-evidence-001",
) -> ConnectorInvocationEvidenceRecord:
    return await service.create(
        actor=actor or target_session_operator("subject.connector-independent-evidence-ingestor"),
        source_invocation_id=invocation.invocation_id,
        source_invocation_digest=invocation.canonical_digest,
        ingestion_policy_id=policy.policy_id,
        ingestion_policy_digest=policy.canonical_digest,
        purpose="Preserve the exact governed connector observations as immutable evidence.",
        one_way_ingestion_acknowledged=True,
        idempotency_key=key,
        correlation_id="cor_invocation_evidence",
    )


@pytest.mark.asyncio
async def test_invocation_evidence_is_immutable_minimized_and_idempotent() -> None:
    audit = CollectingAuditSink()
    service, invocation, policy, authorizer, adapter, _ = await evidence_fixture(audit_sink=audit)
    record = await ingest_evidence(service, invocation, policy)
    repeated = await ingest_evidence(service, invocation, policy)

    assert record.instance_state == "enabled_invocation_evidence_ingested"
    assert record.source_invocation_completed and record.evidence_ingested
    assert record.immutable_storage_confirmed and record.encrypted_at_rest
    assert record.transient_buffers_erased and record.artifact_channel_closed
    assert not record.knowledge_item_created and not record.retrieval_published
    assert not record.model_context_available and not record.graph_updated
    assert not record.workflow_continued and not record.execution_authorized
    assert repeated.reused and repeated.ingestion_id == record.ingestion_id
    assert isinstance(adapter, SyntheticConnectorInvocationEvidenceAdapter)
    assert len(adapter.calls) == 1
    assert authorizer.calls == [
        (
            invocation.required_permission,
            invocation.capability_id,
            invocation.capability_class,
        )
    ]
    assert [item.result_code for item in audit.records] == [
        "connector_invocation_evidence_requested",
        "connector_invocation_evidence_claimed",
        "connector_invocation_evidence_ingested",
    ]


@pytest.mark.asyncio
async def test_invocation_evidence_atomically_rejects_a_concurrent_second_claim() -> None:
    adapter = BlockingAdapter()
    service, invocation, policy, _, _, _ = await evidence_fixture(adapter=adapter)
    first = asyncio.create_task(
        ingest_evidence(service, invocation, policy, key="evidence-concurrent-first")
    )
    await adapter.started.wait()
    with pytest.raises(ConnectorInvocationEvidenceError, match="idempotency_conflict"):
        await ingest_evidence(
            service,
            invocation,
            policy,
            key="evidence-concurrent-second",
        )
    adapter.release.set()
    record = await first
    assert record.evidence_ingested
    assert len(adapter.calls) == 1


@pytest.mark.asyncio
async def test_invocation_evidence_denies_actor_reuse_and_permission_before_claim() -> None:
    service, invocation, policy, _, _, _ = await evidence_fixture()
    with pytest.raises(ConnectorInvocationEvidenceError, match="separation_required"):
        await ingest_evidence(
            service,
            invocation,
            policy,
            actor=target_session_operator(invocation.invoked_by),
        )
    assert (
        await service.repository.get_claim_by_invocation(
            source_invocation_id=invocation.invocation_id
        )
        is None
    )

    denied_service, invocation, policy, _, _, _ = await evidence_fixture(
        permission_authorizer=RecordingPermissionAuthorizer(deny=True)
    )
    with pytest.raises(ConnectorInvocationEvidenceError, match="permission_denied"):
        await ingest_evidence(denied_service, invocation, policy)
    assert (
        await denied_service.repository.get_claim_by_invocation(
            source_invocation_id=invocation.invocation_id
        )
        is None
    )


@pytest.mark.asyncio
async def test_exact_capability_authorizer_no_longer_bypasses_denial() -> None:
    service, invocation, _, _, _, _ = await evidence_fixture()
    del service
    audit = CollectingAuditSink()
    authorization = AuthorizationService(
        permissions=(
            PermissionDefinition(
                permission_id=invocation.required_permission,
                description="Read governed synthetic storage health.",
            ),
        ),
        roles=(),
        assignments=(),
        audit_sink=audit,
    )
    authorizer = AuthorizationConnectorCapabilityPermissionAuthorizer(
        service=authorization,
        environment="development",
    )
    with pytest.raises(ConnectorInvocationAuthorizationError, match="permission_denied"):
        await authorizer.authorize(
            actor=target_session_operator("subject.connector-unauthorized-invoker"),
            permission_id=invocation.required_permission,
            capability_id=invocation.capability_id,
            capability_class=invocation.capability_class,
            organization_id=invocation.organization_id,
            environment_id=invocation.environment_id,
            correlation_id="cor_exact_capability_denied",
        )
    assert len(audit.records) == 1


@pytest.mark.asyncio
async def test_invocation_evidence_uncertain_or_invalid_receipt_stays_claimed() -> None:
    uncertain = UncertainAdapter()
    service, invocation, policy, _, _, _ = await evidence_fixture(adapter=uncertain)
    with pytest.raises(ConnectorInvocationEvidenceUncertainError, match="uncertain"):
        await ingest_evidence(service, invocation, policy)
    assert uncertain.calls == 1
    assert (
        await service.repository.get_claim_by_invocation(
            source_invocation_id=invocation.invocation_id
        )
        is not None
    )
    with pytest.raises(ConnectorInvocationEvidenceError, match="already_claimed"):
        await ingest_evidence(service, invocation, policy)
    assert uncertain.calls == 1

    altered = AlteredReceiptAdapter(clock=lambda: invocation.completed_at)
    altered_service, invocation, policy, _, _, _ = await evidence_fixture(adapter=altered)
    with pytest.raises(ConnectorInvocationEvidenceUncertainError, match="receipt_invalid"):
        await ingest_evidence(altered_service, invocation, policy)
    assert len(altered.calls) == 1


@pytest.mark.asyncio
async def test_invocation_evidence_claim_audit_failure_stays_claimed() -> None:
    service, invocation, policy, _, adapter, _ = await evidence_fixture(
        audit_sink=FailSecondAuditSink()
    )
    with pytest.raises(RuntimeError, match="audit unavailable"):
        await ingest_evidence(service, invocation, policy)
    assert (
        await service.repository.get_claim_by_invocation(
            source_invocation_id=invocation.invocation_id
        )
        is not None
    )
    assert isinstance(adapter, SyntheticConnectorInvocationEvidenceAdapter)
    assert len(adapter.calls) == 0


@pytest.mark.asyncio
async def test_invocation_evidence_postgres_round_trip_excludes_content() -> None:
    service, invocation, policy, _, _, _ = await evidence_fixture()
    record = await ingest_evidence(service, invocation, policy)
    claim = await service.repository.get_claim_by_invocation(
        source_invocation_id=invocation.invocation_id
    )
    assert claim is not None
    raw_claim = ConnectorInvocationEvidenceService._normalize(asdict(claim))
    raw_record = ConnectorInvocationEvidenceService._normalize(asdict(record))
    assert isinstance(raw_claim, dict) and isinstance(raw_record, dict)
    assert PostgreSQLConnectorInvocationEvidenceRepository._claim_to_domain(raw_claim) == claim
    assert PostgreSQLConnectorInvocationEvidenceRepository._record_to_domain(raw_record) == record
    for hidden in (
        "evidence_content",
        "evidence_excerpt",
        "observation_values",
        "raw_output",
        "target_address",
        "storage_location",
        "acl_principals",
        "encryption_key",
        "secret_reference_id",
        "lease_handle",
        "session_handle",
        "idempotency_key",
    ):
        assert hidden not in raw_claim
        assert hidden not in raw_record


def test_invocation_evidence_api_forbids_content_and_returns_minimized_metadata(
    tmp_path: Path,
) -> None:
    service, invocation, policy, _, _, bounded = asyncio.run(evidence_fixture())
    bounded_service = bounded[0]
    authorization_service = bounded[1]
    target_service = bounded[2]
    runtime_service = bounded[3]
    brokerage_service = bounded[4]
    runtime_fixture = bounded[5]
    (
        runtime_trust_service,
        enablement_service,
        validation_service,
        assignment_service,
        target_configuration_service,
        instance_service,
        installation_service,
        registration_service,
        *_rest,
    ) = runtime_fixture
    subject = target_session_operator("subject.connector-independent-evidence-ingestor")
    app_settings = settings(
        development_subject_id=subject.subject_id,
        mcp_builder_generation_root=tmp_path / "mcp-builder-generations",
    )
    payload: dict[str, object] = {
        "schema_version": "atlas.connector-invocation-evidence-input.v1",
        "source_invocation_id": invocation.invocation_id,
        "source_invocation_digest": invocation.canonical_digest,
        "ingestion_policy_id": policy.policy_id,
        "ingestion_policy_digest": policy.canonical_digest,
        "purpose": "Preserve the exact governed connector observations as immutable evidence.",
        ACKNOWLEDGEMENT_FIELD: True,
    }
    with TestClient(
        create_app(
            app_settings,
            identity_provider=BasicTestIdentityProvider(subject),
            package_registration_service=registration_service,
            package_installation_service=installation_service,
            connector_instance_creation_service=instance_service,
            target_configuration_service=target_configuration_service,
            credential_assignment_service=assignment_service,
            configuration_validation_service=validation_service,
            capability_enablement_service=enablement_service,
            runtime_trust_service=runtime_trust_service,
            secret_brokerage_service=brokerage_service,
            runtime_activation_service=runtime_service,
            target_session_service=target_service,
            invocation_authorization_service=authorization_service,
            bounded_invocation_service=bounded_service,
            invocation_evidence_service=service,
        )
    ) as client:
        login_response = login(client)
        endpoint = "/api/v1/connectors/invocation-evidence"
        denied = client.post(endpoint, json=payload, headers={"Idempotency-Key": "evidence-api-1"})
        forbidden = client.post(
            endpoint,
            json={**payload, "evidence_content": "vendor response"},
            headers={
                "Idempotency-Key": "evidence-api-2",
                "X-CSRF-Token": login_response.headers["X-CSRF-Token"],
            },
        )
        created = client.post(
            endpoint,
            json=payload,
            headers={
                "Idempotency-Key": "evidence-api-1",
                "X-CSRF-Token": login_response.headers["X-CSRF-Token"],
            },
        )
        assert created.status_code == 201, created.text
        ingestion_id = created.json()["data"]["ingestion_id"]
        read = client.get(f"{endpoint}/{ingestion_id}")

    assert denied.status_code == 403 and forbidden.status_code == 422
    assert read.status_code == 200
    assert created.headers["Cache-Control"] == read.headers["Cache-Control"] == "no-store"
    data = created.json()["data"]
    assert data["evidence_ingested"] is True
    assert data["immutable_storage_confirmed"] is True
    assert data["retrieval_published"] is False
    assert data["model_context_available"] is False
    for hidden in (
        "evidence_content",
        "evidence_excerpt",
        "observation_values",
        "raw_output",
        "target_address",
        "storage_location",
        "acl_principals",
        "encryption_key",
        "secret_reference_id",
        "lease_handle",
        "session_handle",
        "request_binding_digest",
        "idempotency_digest",
        "idempotency_key",
    ):
        assert hidden not in data
