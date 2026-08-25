from __future__ import annotations

import asyncio
import os
from dataclasses import asdict, replace
from datetime import timedelta
from pathlib import Path
from typing import Any
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import delete
from sqlalchemy.ext.asyncio import create_async_engine
from test_bounded_invocation import bounded_fixture, invoke_bounded
from test_browser_sessions import BasicTestIdentityProvider, login, settings
from test_package_acquisition import CollectingAuditSink
from test_runtime_activation import FailSecondAuditSink
from test_target_session import (
    development_target_session_operator,
    target_session_operator,
)

from atlas.api.app import create_app
from atlas.core.persistence.models import (
    ConnectorInvocationEvidenceClaimModel,
    ConnectorInvocationEvidenceModel,
)
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
    UnavailableConnectorInvocationEvidenceAdapter,
)
from atlas.modules.connectors.adapters.invocation_permission import (
    AuthorizationConnectorCapabilityPermissionAuthorizer,
)
from atlas.modules.connectors.application.invocation_authorization_ports import (
    ConnectorInvocationAuthorizationError,
)
from atlas.modules.connectors.application.invocation_evidence import (
    ConnectorInvocationEvidenceService,
    _signed_policy,
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
from atlas.modules.identity.domain.models import AssuranceLevel, AuthenticatedSubject, SubjectKind

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
    available = True

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
    required_assurance_level: AssuranceLevel = AssuranceLevel.SINGLE_FACTOR,
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
    if policy.required_assurance_level is not required_assurance_level:
        policy = replace(
            policy,
            required_assurance_level=required_assurance_level,
            canonical_digest="0" * 64,
        )
        policy = replace(policy, canonical_digest=_signed_policy(policy))
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
async def test_invocation_evidence_inventory_and_exact_signed_options_are_authoritative() -> None:
    service, invocation, policy, _, _, _ = await evidence_fixture()
    actor = target_session_operator("subject.connector-independent-evidence-ingestor")

    options = await service.list_options(
        actor=actor,
        source_invocation_id=invocation.invocation_id,
        correlation_id="cor_invocation_evidence_options",
    )
    assert len(options) == 1
    option = options[0]
    assert option.source_invocation_id == invocation.invocation_id
    assert option.source_invocation_digest == invocation.canonical_digest
    assert option.ingestion_policy_id == policy.policy_id
    assert option.ingestion_policy_digest == policy.canonical_digest
    assert option.required_assurance_level is AssuranceLevel.SINGLE_FACTOR
    assert option.classification == policy.required_classification
    assert option.retention_policy_id == policy.retention_policy_id
    assert (
        await service.list_evidence(
            actor=actor,
            source_invocation_id=invocation.invocation_id,
            correlation_id="cor_invocation_evidence_empty_inventory",
        )
        == ()
    )

    record = await ingest_evidence(service, invocation, policy, actor=actor)

    assert await service.list_options(
        actor=actor,
        source_invocation_id=invocation.invocation_id,
        correlation_id="cor_invocation_evidence_claimed_options",
    ) == ()
    assert await service.list_evidence(
        actor=actor,
        source_invocation_id=invocation.invocation_id,
        correlation_id="cor_invocation_evidence_inventory",
    ) == (record,)


@pytest.mark.asyncio
async def test_invocation_evidence_options_reject_stale_policy_and_production_fail_closed(
) -> None:
    _, invocation, policy, _, _, bounded = await evidence_fixture()
    actor = target_session_operator("subject.connector-independent-evidence-ingestor")
    stale_policy = replace(
        policy,
        expires_at=invocation.completed_at,
        canonical_digest="0" * 64,
    )
    stale_policy = replace(stale_policy, canonical_digest=_signed_policy(stale_policy))
    source = bounded[0]

    stale_service = ConnectorInvocationEvidenceService(
        repository=InMemoryConnectorInvocationEvidenceRepository(),
        source=source,
        policy_source=InMemoryConnectorInvocationEvidencePolicySource((stale_policy,)),
        permission_authorizer=RecordingPermissionAuthorizer(),
        adapter=UnavailableConnectorInvocationEvidenceAdapter(),
        audit_sink=CollectingAuditSink(),
        environment_id=invocation.environment_id,
        clock=lambda: invocation.completed_at,
    )
    assert await stale_service.list_options(
        actor=actor,
        source_invocation_id=invocation.invocation_id,
        correlation_id="cor_invocation_evidence_stale_options",
    ) == ()

    closed_service = ConnectorInvocationEvidenceService(
        repository=InMemoryConnectorInvocationEvidenceRepository(),
        source=source,
        policy_source=InMemoryConnectorInvocationEvidencePolicySource(()),
        permission_authorizer=RecordingPermissionAuthorizer(),
        adapter=UnavailableConnectorInvocationEvidenceAdapter(),
        audit_sink=CollectingAuditSink(),
        environment_id=invocation.environment_id,
        clock=lambda: invocation.completed_at,
    )
    assert await closed_service.list_options(
        actor=actor,
        source_invocation_id=invocation.invocation_id,
        correlation_id="cor_invocation_evidence_closed_options",
    ) == ()
    with pytest.raises(ConnectorInvocationEvidenceError, match="policy_not_found"):
        await ingest_evidence(closed_service, invocation, policy, actor=actor)

    unavailable_repository = InMemoryConnectorInvocationEvidenceRepository()
    unavailable_service = ConnectorInvocationEvidenceService(
        repository=unavailable_repository,
        source=source,
        policy_source=InMemoryConnectorInvocationEvidencePolicySource((policy,)),
        permission_authorizer=RecordingPermissionAuthorizer(),
        adapter=UnavailableConnectorInvocationEvidenceAdapter(),
        audit_sink=CollectingAuditSink(),
        environment_id=invocation.environment_id,
        clock=lambda: invocation.completed_at,
    )
    assert await unavailable_service.list_options(
        actor=actor,
        source_invocation_id=invocation.invocation_id,
        correlation_id="cor_invocation_evidence_unavailable_options",
    ) == ()
    with pytest.raises(ConnectorInvocationEvidenceError, match="adapter_unavailable"):
        await ingest_evidence(unavailable_service, invocation, policy, actor=actor)
    assert await unavailable_repository.get_claim_by_invocation_in_scope(
        source_invocation_id=invocation.invocation_id,
        organization_id=invocation.organization_id,
        environment_id=invocation.environment_id,
    ) is None


@pytest.mark.asyncio
async def test_invocation_evidence_binds_idempotency_and_reads_to_tenant_scope() -> None:
    service, invocation, policy, _, adapter, _ = await evidence_fixture()
    actor = target_session_operator("subject.connector-independent-evidence-ingestor")
    record = await ingest_evidence(service, invocation, policy, actor=actor)
    claim = await service.repository.get_claim_by_invocation_in_scope(
        source_invocation_id=invocation.invocation_id,
        organization_id=invocation.organization_id,
        environment_id=invocation.environment_id,
    )
    assert claim is not None
    assert claim.request_binding_digest == service._digest(
        {
            "actor_id": actor.subject_id,
            "organization_id": actor.organization_id,
            "environment_id": invocation.environment_id,
            "source_invocation_id": invocation.invocation_id,
            "source_invocation_digest": invocation.canonical_digest,
            "ingestion_policy_id": policy.policy_id,
            "ingestion_policy_digest": policy.canonical_digest,
            "purpose": "Preserve the exact governed connector observations as immutable evidence.",
        }
    )
    assert claim.idempotency_digest == service._digest(
        [
            actor.subject_id,
            actor.organization_id,
            invocation.environment_id,
            "invocation-evidence-001",
        ]
    )

    assert (
        await service.repository.get_in_scope(
            ingestion_id=record.ingestion_id,
            organization_id="org-foreign",
            environment_id=invocation.environment_id,
        )
        is None
    )
    assert (
        await service.repository.get_claim_by_invocation_in_scope(
            source_invocation_id=invocation.invocation_id,
            organization_id="org-foreign",
            environment_id=invocation.environment_id,
        )
        is None
    )
    assert (
        await service.repository.get_claim_by_idempotency_in_scope(
            claimed_by=actor.subject_id,
            idempotency_digest=claim.idempotency_digest,
            organization_id="org-foreign",
            environment_id=invocation.environment_id,
        )
        is None
    )

    foreign_actor = replace(actor, organization_id="org-foreign")
    with pytest.raises(ConnectorInvocationEvidenceError, match="source_not_found"):
        await ingest_evidence(
            service,
            invocation,
            policy,
            actor=foreign_actor,
        )
    assert isinstance(adapter, SyntheticConnectorInvocationEvidenceAdapter)
    assert len(adapter.calls) == 1


@pytest.mark.asyncio
async def test_invocation_evidence_memory_contract_allows_same_ids_in_separate_tenants() -> None:
    service, invocation, policy, _, _, _ = await evidence_fixture()
    record = await ingest_evidence(service, invocation, policy)
    claim = await service.repository.get_claim_by_invocation_in_scope(
        source_invocation_id=invocation.invocation_id,
        organization_id=invocation.organization_id,
        environment_id=invocation.environment_id,
    )
    assert claim is not None

    assert not await service.repository.add(
        replace(
            record,
            claim_id="connector-invocation-evidence-claim.missing",
            ingestion_id="connector-invocation-evidence-ingestion.missing",
            source_invocation_id="connector-bounded-invocation.missing",
        )
    )
    assert not await service.repository.claim(
        replace(
            claim,
            source_invocation_id="connector-bounded-invocation.duplicate-claim-id",
            ingestion_id="connector-invocation-evidence-ingestion.duplicate-claim-id",
            idempotency_digest="1" * 64,
        )
    )

    foreign_claim = replace(
        claim,
        organization_id="org-foreign",
        environment_id="env-foreign",
    )
    foreign_record = replace(
        record,
        organization_id="org-foreign",
        environment_id="env-foreign",
    )
    assert await service.repository.claim(foreign_claim)
    assert await service.repository.add(foreign_record)
    assert not await service.repository.add(
        replace(
            foreign_record,
            ingestion_id="connector-invocation-evidence-ingestion.second-completion",
        )
    )

    duplicate_ingestion_claim = replace(
        foreign_claim,
        claim_id="connector-invocation-evidence-claim.duplicate-ingestion",
        source_invocation_id="connector-bounded-invocation.duplicate-ingestion",
        idempotency_digest="2" * 64,
    )
    assert await service.repository.claim(duplicate_ingestion_claim)
    assert not await service.repository.add(
        replace(
            foreign_record,
            claim_id=duplicate_ingestion_claim.claim_id,
            source_invocation_id=duplicate_ingestion_claim.source_invocation_id,
        )
    )
    assert (
        await service.repository.get_in_scope(
            ingestion_id=record.ingestion_id,
            organization_id="org-foreign",
            environment_id="env-foreign",
        )
        == foreign_record
    )
    assert await service.repository.list_scope(
        organization_id=record.organization_id,
        environment_id=record.environment_id,
    ) == (record,)
    assert await service.repository.list_scope(
        organization_id=foreign_record.organization_id,
        environment_id=foreign_record.environment_id,
    ) == (foreign_record,)
    assert await service.repository.list_scope(
        organization_id="org-missing",
        environment_id=record.environment_id,
    ) == ()

    policy_source = InMemoryConnectorInvocationEvidencePolicySource(
        (
            policy,
            replace(
                policy,
                organization_id="org-foreign",
                environment_id="env-foreign",
            ),
        )
    )
    assert (
        await policy_source.get_by_id_in_scope(
            policy_id=policy.policy_id,
            organization_id=policy.organization_id,
            environment_id=policy.environment_id,
        )
        == policy
    )
    assert (
        await policy_source.get_by_id_in_scope(
            policy_id=policy.policy_id,
            organization_id="org-missing",
            environment_id="env-foreign",
        )
        is None
    )
    assert await policy_source.list_scope(
        organization_id=policy.organization_id,
        environment_id=policy.environment_id,
    ) == (policy,)
    assert await policy_source.list_scope(
        organization_id="org-foreign",
        environment_id="env-foreign",
    ) == (
        replace(
            policy,
            organization_id="org-foreign",
            environment_id="env-foreign",
        ),
    )


@pytest.mark.asyncio
async def test_live_postgres_invocation_evidence_isolates_same_identifiers_by_tenant() -> None:
    database_url = os.getenv("ATLAS_TEST_POSTGRES_DSN")
    if not database_url:
        pytest.skip("ATLAS_TEST_POSTGRES_DSN is not configured")
    service, invocation, policy, _, _, _ = await evidence_fixture()
    base_record = await ingest_evidence(service, invocation, policy)
    base_claim = await service.repository.get_claim_by_invocation_in_scope(
        source_invocation_id=invocation.invocation_id,
        organization_id=invocation.organization_id,
        environment_id=invocation.environment_id,
    )
    assert base_claim is not None
    suffix = uuid4().hex[:12]
    source_invocation_id = f"connector-bounded-invocation.scoped-evidence-{suffix}"

    first_claim = replace(
        base_claim,
        claim_id=f"connector-invocation-evidence-claim.scoped-{suffix}",
        source_invocation_id=source_invocation_id,
        ingestion_id=f"connector-invocation-evidence-ingestion.scoped-{suffix}",
        canonical_digest="0" * 64,
    )
    first_claim = replace(
        first_claim,
        canonical_digest=service._digest(service._claim_payload(first_claim)),
    )
    second_claim = replace(
        first_claim,
        organization_id="organization.foreign",
        canonical_digest="0" * 64,
    )
    second_claim = replace(
        second_claim,
        canonical_digest=service._digest(service._claim_payload(second_claim)),
    )
    first_record = replace(
        base_record,
        ingestion_id=first_claim.ingestion_id,
        claim_id=first_claim.claim_id,
        source_invocation_id=source_invocation_id,
        canonical_digest="0" * 64,
    )
    first_record = replace(
        first_record,
        canonical_digest=service._digest(service._record_payload(first_record)),
    )
    second_record = replace(
        first_record,
        organization_id=second_claim.organization_id,
        canonical_digest="0" * 64,
    )
    second_record = replace(
        second_record,
        canonical_digest=service._digest(service._record_payload(second_record)),
    )

    first_engine = create_async_engine(database_url)
    second_engine = create_async_engine(database_url)
    first_repository = PostgreSQLConnectorInvocationEvidenceRepository(first_engine)
    second_repository = PostgreSQLConnectorInvocationEvidenceRepository(second_engine)
    try:
        assert await first_repository.claim(first_claim)
        assert await second_repository.claim(second_claim)
        assert await first_repository.add(first_record)
        assert await second_repository.add(second_record)
        assert (
            await first_repository.get_in_scope(
                ingestion_id=first_record.ingestion_id,
                organization_id=first_record.organization_id,
                environment_id=first_record.environment_id,
            )
            == first_record
        )
        assert (
            await second_repository.get_in_scope(
                ingestion_id=second_record.ingestion_id,
                organization_id=second_record.organization_id,
                environment_id=second_record.environment_id,
            )
            == second_record
        )
        assert (
            await second_repository.get_claim_by_invocation_in_scope(
                source_invocation_id=source_invocation_id,
                organization_id=second_record.organization_id,
                environment_id=second_record.environment_id,
            )
            == second_claim
        )
        assert (
            await second_repository.get_in_scope(
                ingestion_id=first_record.ingestion_id,
                organization_id="organization.missing",
                environment_id=second_record.environment_id,
            )
            is None
        )
        assert await first_repository.list_scope(
            organization_id=first_record.organization_id,
            environment_id=first_record.environment_id,
        ) == (first_record,)
        assert await second_repository.list_scope(
            organization_id=second_record.organization_id,
            environment_id=second_record.environment_id,
        ) == (second_record,)
    finally:
        async with first_engine.begin() as connection:
            await connection.execute(
                delete(ConnectorInvocationEvidenceModel).where(
                    ConnectorInvocationEvidenceModel.source_invocation_id == source_invocation_id
                )
            )
            await connection.execute(
                delete(ConnectorInvocationEvidenceClaimModel).where(
                    ConnectorInvocationEvidenceClaimModel.source_invocation_id
                    == source_invocation_id
                )
            )
        await first_repository.close()
        await second_repository.close()


@pytest.mark.asyncio
async def test_invocation_evidence_accepts_development_identity_under_default_policy() -> None:
    service, invocation, policy, _, _, _ = await evidence_fixture()
    actor = development_target_session_operator("subject.connector-independent-evidence-ingestor")

    record = await ingest_evidence(service, invocation, policy, actor=actor)

    assert policy.required_assurance_level is AssuranceLevel.SINGLE_FACTOR
    assert record.ingested_by == actor.subject_id
    assert record.evidence_ingested and not record.knowledge_item_created


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "required_assurance_level",
    (AssuranceLevel.MULTI_FACTOR, AssuranceLevel.HARDWARE_BACKED),
)
async def test_invocation_evidence_enforces_explicit_step_up_policy(
    required_assurance_level: AssuranceLevel,
) -> None:
    service, invocation, policy, authorizer, adapter, _ = await evidence_fixture(
        required_assurance_level=required_assurance_level
    )

    with pytest.raises(ConnectorInvocationEvidenceError, match="source_invalid"):
        await ingest_evidence(
            service,
            invocation,
            policy,
            actor=development_target_session_operator(
                "subject.connector-independent-evidence-ingestor"
            ),
        )

    assert authorizer.calls == []
    assert getattr(adapter, "calls", []) in ([], 0)


@pytest.mark.asyncio
async def test_invocation_evidence_denies_non_human_identity() -> None:
    service, invocation, policy, authorizer, adapter, _ = await evidence_fixture()
    actor = replace(
        development_target_session_operator("subject.connector-independent-evidence-ingestor"),
        kind=SubjectKind.SERVICE,
    )

    with pytest.raises(ConnectorInvocationEvidenceError, match="human_required"):
        await ingest_evidence(service, invocation, policy, actor=actor)

    assert authorizer.calls == []
    assert getattr(adapter, "calls", []) in ([], 0)


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
        await service.repository.get_claim_by_invocation_in_scope(
            source_invocation_id=invocation.invocation_id,
            organization_id=invocation.organization_id,
            environment_id=invocation.environment_id,
        )
        is None
    )

    denied_service, invocation, policy, _, _, _ = await evidence_fixture(
        permission_authorizer=RecordingPermissionAuthorizer(deny=True)
    )
    with pytest.raises(ConnectorInvocationEvidenceError, match="permission_denied"):
        await ingest_evidence(denied_service, invocation, policy)
    assert (
        await denied_service.repository.get_claim_by_invocation_in_scope(
            source_invocation_id=invocation.invocation_id,
            organization_id=invocation.organization_id,
            environment_id=invocation.environment_id,
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
        await service.repository.get_claim_by_invocation_in_scope(
            source_invocation_id=invocation.invocation_id,
            organization_id=invocation.organization_id,
            environment_id=invocation.environment_id,
        )
        is not None
    )
    with pytest.raises(ConnectorInvocationEvidenceError, match="already_claimed"):
        await ingest_evidence(service, invocation, policy)
    assert uncertain.calls == 1
    actor = target_session_operator("subject.connector-independent-evidence-ingestor")
    assert await service.list_options(
        actor=actor,
        source_invocation_id=invocation.invocation_id,
        correlation_id="cor_invocation_evidence_uncertain_options",
    ) == ()
    assert await service.list_evidence(
        actor=actor,
        source_invocation_id=invocation.invocation_id,
        correlation_id="cor_invocation_evidence_uncertain_inventory",
    ) == ()
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
        await service.repository.get_claim_by_invocation_in_scope(
            source_invocation_id=invocation.invocation_id,
            organization_id=invocation.organization_id,
            environment_id=invocation.environment_id,
        )
        is not None
    )
    assert isinstance(adapter, SyntheticConnectorInvocationEvidenceAdapter)
    assert len(adapter.calls) == 0


@pytest.mark.asyncio
async def test_invocation_evidence_postgres_round_trip_excludes_content() -> None:
    service, invocation, policy, _, _, _ = await evidence_fixture()
    record = await ingest_evidence(service, invocation, policy)
    claim = await service.repository.get_claim_by_invocation_in_scope(
        source_invocation_id=invocation.invocation_id,
        organization_id=invocation.organization_id,
        environment_id=invocation.environment_id,
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
    subject = development_target_session_operator("subject.connector-independent-evidence-ingestor")
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
        options_before = client.get(
            f"{endpoint}/options", params={"source_invocation_id": invocation.invocation_id}
        )
        inventory_before = client.get(
            endpoint, params={"source_invocation_id": invocation.invocation_id}
        )
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
        options_after = client.get(
            f"{endpoint}/options", params={"source_invocation_id": invocation.invocation_id}
        )
        inventory_after = client.get(
            endpoint, params={"source_invocation_id": invocation.invocation_id}
        )

    assert denied.status_code == 403 and forbidden.status_code == 422
    assert read.status_code == 200
    assert options_before.status_code == inventory_before.status_code == 200
    assert options_after.status_code == inventory_after.status_code == 200
    assert len(options_before.json()["data"]) == 1
    option = options_before.json()["data"][0]
    assert option["source_invocation_digest"] == invocation.canonical_digest
    assert option["ingestion_policy_digest"] == policy.canonical_digest
    assert option["required_assurance_level"] == "single_factor"
    assert option["irreversible_claim_required"] is True
    assert option["automatic_retry_allowed"] is False
    assert option["knowledge_item_created"] is False
    assert inventory_before.json()["data"] == []
    assert options_after.json()["data"] == []
    inventory = inventory_after.json()["data"][0]
    assert inventory["ingestion_id"] == ingestion_id
    assert {
        created.headers["Cache-Control"],
        read.headers["Cache-Control"],
        options_before.headers["Cache-Control"],
        inventory_before.headers["Cache-Control"],
        options_after.headers["Cache-Control"],
        inventory_after.headers["Cache-Control"],
    } == {"no-store"}
    data = created.json()["data"]
    assert data["evidence_ingested"] is True
    assert data["immutable_storage_confirmed"] is True
    assert data["retrieval_published"] is False
    assert data["model_context_available"] is False
    for hidden in (
        "claim_id",
        "organization_id",
        "environment_id",
        "connector_id",
        "instance_id",
        "access_policy_id",
        "encryption_profile_id",
        "ingestion_adapter_id",
        "ingested_by",
        "purpose",
    ):
        assert hidden not in data
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
        assert hidden not in option
        assert hidden not in inventory
    for hidden in (
        "claim_id",
        "organization_id",
        "environment_id",
        "connector_id",
        "release_version",
        "manifest_digest",
        "instance_id",
        "instance_key",
        "display_name",
        "output_schema_digest",
        "result_policy_digest",
        "access_policy_id",
        "access_policy_digest",
        "encryption_profile_id",
        "encryption_profile_digest",
        "ingestion_adapter_id",
        "ingested_by",
        "purpose",
    ):
        assert hidden not in inventory
    for hidden in (
        "access_policy_id",
        "access_policy_digest",
        "retention_policy_digest",
        "encryption_profile_id",
        "encryption_profile_digest",
        "ingestion_adapter_id",
        "signature",
    ):
        assert hidden not in option
