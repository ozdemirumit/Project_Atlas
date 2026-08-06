from __future__ import annotations

import asyncio
from dataclasses import asdict, replace
from datetime import timedelta
from pathlib import Path
from typing import Any, cast

import pytest
from fastapi.testclient import TestClient
from test_browser_sessions import BasicTestIdentityProvider, login, settings
from test_invocation_evidence import evidence_fixture, ingest_evidence
from test_package_acquisition import CollectingAuditSink
from test_runtime_activation import FailSecondAuditSink
from test_target_session import target_session_operator

from atlas.api.app import create_app
from atlas.modules.identity.domain.models import AuthenticatedSubject
from atlas.modules.knowledge.adapters.evidence_draft_memory import (
    InMemoryOperationalEvidenceKnowledgeDraftPolicySource,
    InMemoryOperationalEvidenceKnowledgeDraftRepository,
)
from atlas.modules.knowledge.adapters.evidence_draft_postgres import (
    PostgreSQLOperationalEvidenceKnowledgeDraftRepository,
)
from atlas.modules.knowledge.adapters.evidence_draft_synthetic import (
    SyntheticOperationalEvidenceKnowledgeDraftAdapter,
)
from atlas.modules.knowledge.application.evidence_draft import (
    OperationalEvidenceKnowledgeDraftService,
    build_development_operational_evidence_knowledge_draft_policy,
)
from atlas.modules.knowledge.application.evidence_draft_ports import (
    OperationalEvidenceKnowledgeDraftError,
    OperationalEvidenceKnowledgeDraftUncertainError,
)
from atlas.modules.knowledge.domain.evidence_draft import (
    OperationalEvidenceKnowledgeDraftInstruction,
    OperationalEvidenceKnowledgeDraftPolicySnapshot,
    OperationalEvidenceKnowledgeDraftReceipt,
    OperationalEvidenceKnowledgeDraftRecord,
)

ACKNOWLEDGEMENT_FIELD = "acknowledged_result_is_an_unapproved_non_retrievable_draft"


class RecordingDraftPermissionAuthorizer:
    def __init__(self, *, deny: bool = False) -> None:
        self.deny = deny
        self.calls: list[tuple[str, str]] = []

    async def authorize(
        self,
        *,
        actor: AuthenticatedSubject,
        organization_id: str,
        environment_id: str,
        correlation_id: str,
    ) -> None:
        del actor, correlation_id
        self.calls.append((organization_id, environment_id))
        if self.deny:
            raise OperationalEvidenceKnowledgeDraftError(
                "operational_evidence_knowledge_draft_permission_denied"
            )


class UncertainDraftAdapter:
    def __init__(self) -> None:
        self.calls = 0

    async def create_draft(
        self, instruction: OperationalEvidenceKnowledgeDraftInstruction
    ) -> OperationalEvidenceKnowledgeDraftReceipt:
        del instruction
        self.calls += 1
        raise OperationalEvidenceKnowledgeDraftUncertainError(
            "operational_evidence_knowledge_draft_storage_outcome_uncertain"
        )


class AlteredDraftReceiptAdapter(SyntheticOperationalEvidenceKnowledgeDraftAdapter):
    async def create_draft(
        self, instruction: OperationalEvidenceKnowledgeDraftInstruction
    ) -> OperationalEvidenceKnowledgeDraftReceipt:
        receipt = await super().create_draft(instruction)
        altered = replace(receipt, classification="classification.restricted")
        payload = cast(dict[str, object], asdict(altered))
        payload.pop("canonical_digest")
        return replace(
            altered,
            canonical_digest=OperationalEvidenceKnowledgeDraftService._digest(
                OperationalEvidenceKnowledgeDraftService._normalize(payload)
            ),
        )


class BlockingDraftAdapter(SyntheticOperationalEvidenceKnowledgeDraftAdapter):
    def __init__(self) -> None:
        super().__init__()
        self.started = asyncio.Event()
        self.release = asyncio.Event()

    async def create_draft(
        self, instruction: OperationalEvidenceKnowledgeDraftInstruction
    ) -> OperationalEvidenceKnowledgeDraftReceipt:
        self.started.set()
        await self.release.wait()
        return await super().create_draft(instruction)


async def draft_fixture(
    *,
    audit_sink: CollectingAuditSink | FailSecondAuditSink | None = None,
    permission_authorizer: RecordingDraftPermissionAuthorizer | None = None,
    adapter: SyntheticOperationalEvidenceKnowledgeDraftAdapter
    | UncertainDraftAdapter
    | AlteredDraftReceiptAdapter
    | BlockingDraftAdapter
    | None = None,
) -> tuple[
    OperationalEvidenceKnowledgeDraftService,
    InMemoryOperationalEvidenceKnowledgeDraftRepository,
    OperationalEvidenceKnowledgeDraftRecord | None,
    OperationalEvidenceKnowledgeDraftPolicySnapshot,
    RecordingDraftPermissionAuthorizer,
    SyntheticOperationalEvidenceKnowledgeDraftAdapter
    | UncertainDraftAdapter
    | AlteredDraftReceiptAdapter
    | BlockingDraftAdapter,
    tuple[Any, ...],
]:
    evidence_parts = await evidence_fixture()
    evidence_service, invocation, ingestion_policy = evidence_parts[:3]
    evidence = await ingest_evidence(evidence_service, invocation, ingestion_policy)
    policy = build_development_operational_evidence_knowledge_draft_policy(
        organization_id=evidence.organization_id,
        environment_id=evidence.environment_id,
        issued_at=evidence.ingested_at - timedelta(hours=1),
        expires_at=evidence.ingested_at + timedelta(days=1),
    )
    repository = InMemoryOperationalEvidenceKnowledgeDraftRepository()
    authorizer = permission_authorizer or RecordingDraftPermissionAuthorizer()
    resolved_adapter = adapter or SyntheticOperationalEvidenceKnowledgeDraftAdapter(
        clock=lambda: evidence.ingested_at
    )
    service = OperationalEvidenceKnowledgeDraftService(
        repository=repository,
        source=evidence_service,
        policy_source=InMemoryOperationalEvidenceKnowledgeDraftPolicySource((policy,)),
        permission_authorizer=authorizer,
        adapter=resolved_adapter,
        audit_sink=audit_sink or CollectingAuditSink(),
        environment_id=evidence.environment_id,
        clock=lambda: evidence.ingested_at,
    )
    return (
        service,
        repository,
        None,
        policy,
        authorizer,
        resolved_adapter,
        (
            evidence,
            evidence_service,
            evidence_parts,
        ),
    )


async def create_draft(
    service: OperationalEvidenceKnowledgeDraftService,
    evidence: Any,
    policy: OperationalEvidenceKnowledgeDraftPolicySnapshot,
    *,
    actor: AuthenticatedSubject | None = None,
    key: str = "evidence-draft-001",
) -> OperationalEvidenceKnowledgeDraftRecord:
    return await service.create(
        actor=actor or target_session_operator("subject.connector-independent-knowledge-curator"),
        source_ingestion_id=evidence.ingestion_id,
        source_ingestion_digest=evidence.canonical_digest,
        curation_policy_id=policy.policy_id,
        curation_policy_digest=policy.canonical_digest,
        purpose="Create a governed review-only draft from exact operational evidence.",
        unapproved_non_retrievable_draft_acknowledged=True,
        idempotency_key=key,
        correlation_id="cor_evidence_draft",
    )


@pytest.mark.asyncio
async def test_evidence_draft_is_immutable_minimized_and_idempotent() -> None:
    audit = CollectingAuditSink()
    service, _, _, policy, authorizer, adapter, source = await draft_fixture(audit_sink=audit)
    evidence = source[0]
    record = await create_draft(service, evidence, policy)
    repeated = await create_draft(service, evidence, policy)

    assert record.instance_state == "draft_operational_knowledge_created"
    assert record.evidence_ingested and record.knowledge_item_created
    assert record.immutable_draft_confirmed and record.encrypted_at_rest
    assert record.knowledge_lifecycle == "draft"
    assert not record.domain_review_completed and not record.security_review_completed
    assert not record.knowledge_approved and not record.knowledge_published
    assert not record.chunks_created and not record.embeddings_created
    assert not record.retrieval_published and not record.model_context_available
    assert not record.execution_authorized and not record.infrastructure_mutation_performed
    assert repeated.reused and repeated.draft_id == record.draft_id
    assert isinstance(adapter, SyntheticOperationalEvidenceKnowledgeDraftAdapter)
    assert len(adapter.calls) == 1
    assert authorizer.calls == [(evidence.organization_id, evidence.environment_id)]
    assert [item.result_code for item in audit.records] == [
        "operational_evidence_knowledge_draft_requested",
        "operational_evidence_knowledge_draft_source_claimed",
        "operational_evidence_knowledge_draft_created",
    ]


@pytest.mark.asyncio
async def test_evidence_draft_atomically_rejects_concurrent_second_claim() -> None:
    adapter = BlockingDraftAdapter()
    service, _, _, policy, _, _, source = await draft_fixture(adapter=adapter)
    evidence = source[0]
    first = asyncio.create_task(
        create_draft(service, evidence, policy, key="draft-concurrent-first")
    )
    await adapter.started.wait()
    with pytest.raises(OperationalEvidenceKnowledgeDraftError, match="idempotency_conflict"):
        await create_draft(service, evidence, policy, key="draft-concurrent-second")
    adapter.release.set()
    record = await first
    assert record.knowledge_item_created and len(adapter.calls) == 1


@pytest.mark.asyncio
async def test_evidence_draft_denies_actor_reuse_and_permission_before_claim() -> None:
    service, repository, _, policy, _, _, source = await draft_fixture()
    evidence = source[0]
    with pytest.raises(OperationalEvidenceKnowledgeDraftError, match="separation_required"):
        await create_draft(
            service,
            evidence,
            policy,
            actor=target_session_operator(evidence.ingested_by),
        )
    assert await repository.get_claim_by_source(source_ingestion_id=evidence.ingestion_id) is None

    denied_service, denied_repository, _, policy, _, _, source = await draft_fixture(
        permission_authorizer=RecordingDraftPermissionAuthorizer(deny=True)
    )
    evidence = source[0]
    with pytest.raises(OperationalEvidenceKnowledgeDraftError, match="permission_denied"):
        await create_draft(denied_service, evidence, policy)
    assert (
        await denied_repository.get_claim_by_source(source_ingestion_id=evidence.ingestion_id)
        is None
    )


@pytest.mark.asyncio
async def test_evidence_draft_uncertain_or_invalid_receipt_stays_claimed() -> None:
    uncertain = UncertainDraftAdapter()
    service, repository, _, policy, _, _, source = await draft_fixture(adapter=uncertain)
    evidence = source[0]
    with pytest.raises(OperationalEvidenceKnowledgeDraftUncertainError, match="uncertain"):
        await create_draft(service, evidence, policy)
    assert uncertain.calls == 1
    assert await repository.get_claim_by_source(source_ingestion_id=evidence.ingestion_id)
    with pytest.raises(OperationalEvidenceKnowledgeDraftError, match="already_claimed"):
        await create_draft(service, evidence, policy)
    assert uncertain.calls == 1

    altered = AlteredDraftReceiptAdapter(clock=lambda: evidence.ingested_at)
    altered_service, _, _, policy, _, _, source = await draft_fixture(adapter=altered)
    evidence = source[0]
    with pytest.raises(OperationalEvidenceKnowledgeDraftUncertainError, match="receipt_invalid"):
        await create_draft(altered_service, evidence, policy)


@pytest.mark.asyncio
async def test_evidence_draft_claim_audit_failure_stays_claimed() -> None:
    service, repository, _, policy, _, adapter, source = await draft_fixture(
        audit_sink=FailSecondAuditSink()
    )
    evidence = source[0]
    with pytest.raises(RuntimeError, match="audit unavailable"):
        await create_draft(service, evidence, policy)
    assert await repository.get_claim_by_source(source_ingestion_id=evidence.ingestion_id)
    assert isinstance(adapter, SyntheticOperationalEvidenceKnowledgeDraftAdapter)
    assert len(adapter.calls) == 0


@pytest.mark.asyncio
async def test_evidence_draft_postgres_round_trip_excludes_content() -> None:
    service, repository, _, policy, _, _, source = await draft_fixture()
    evidence = source[0]
    record = await create_draft(service, evidence, policy)
    claim = await repository.get_claim_by_source(source_ingestion_id=evidence.ingestion_id)
    assert claim is not None
    raw_claim = OperationalEvidenceKnowledgeDraftService._normalize(asdict(claim))
    raw_record = OperationalEvidenceKnowledgeDraftService._normalize(asdict(record))
    assert isinstance(raw_claim, dict) and isinstance(raw_record, dict)
    assert (
        PostgreSQLOperationalEvidenceKnowledgeDraftRepository._claim_to_domain(raw_claim) == claim
    )
    assert (
        PostgreSQLOperationalEvidenceKnowledgeDraftRepository._record_to_domain(raw_record)
        == record
    )
    for hidden in (
        "evidence_content",
        "draft_content",
        "excerpt",
        "observation_values",
        "storage_location",
        "acl_principals",
        "encryption_key",
        "secret_reference_id",
        "session_handle",
        "idempotency_key",
    ):
        assert hidden not in raw_claim and hidden not in raw_record


def test_evidence_draft_api_forbids_content_and_returns_minimized_metadata(
    tmp_path: Path,
) -> None:
    service, _, _, policy, _, _, source = asyncio.run(draft_fixture())
    evidence, evidence_service, evidence_parts = source
    bounded = evidence_parts[5]
    bounded_service, authorization_service, target_service, runtime_service, brokerage_service = (
        bounded[:5]
    )
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
    subject = target_session_operator("subject.connector-independent-knowledge-curator")
    app_settings = settings(
        development_subject_id=subject.subject_id,
        mcp_builder_generation_root=tmp_path / "mcp-builder-generations",
    )
    payload: dict[str, object] = {
        "schema_version": "atlas.operational-evidence-knowledge-draft-input.v1",
        "source_ingestion_id": evidence.ingestion_id,
        "source_ingestion_digest": evidence.canonical_digest,
        "curation_policy_id": policy.policy_id,
        "curation_policy_digest": policy.canonical_digest,
        "purpose": "Create a governed review-only draft from exact operational evidence.",
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
            invocation_evidence_service=evidence_service,
            operational_evidence_knowledge_draft_service=service,
        )
    ) as client:
        login_response = login(client)
        endpoint = "/api/v1/knowledge/operational-evidence-drafts"
        denied = client.post(endpoint, json=payload, headers={"Idempotency-Key": "draft-api-1"})
        forbidden = client.post(
            endpoint,
            json={**payload, "draft_content": "trusted-looking injected content"},
            headers={
                "Idempotency-Key": "draft-api-2",
                "X-CSRF-Token": login_response.headers["X-CSRF-Token"],
            },
        )
        created = client.post(
            endpoint,
            json=payload,
            headers={
                "Idempotency-Key": "draft-api-1",
                "X-CSRF-Token": login_response.headers["X-CSRF-Token"],
            },
        )
        assert created.status_code == 201, created.text
        draft_id = created.json()["data"]["draft_id"]
        read = client.get(f"{endpoint}/{draft_id}")

    assert denied.status_code == 403 and forbidden.status_code == 422
    assert read.status_code == 200
    assert created.headers["Cache-Control"] == read.headers["Cache-Control"] == "no-store"
    data = created.json()["data"]
    assert data["knowledge_lifecycle"] == "draft"
    assert data["knowledge_item_created"] is True
    assert data["knowledge_approved"] is False
    assert data["retrieval_published"] is False
    assert data["model_context_available"] is False
    for hidden in (
        "evidence_content",
        "draft_content",
        "excerpt",
        "observation_values",
        "storage_location",
        "acl_principals",
        "encryption_key",
        "request_binding_digest",
        "idempotency_digest",
        "idempotency_key",
    ):
        assert hidden not in data
