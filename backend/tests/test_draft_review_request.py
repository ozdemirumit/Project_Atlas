from __future__ import annotations

import asyncio
from dataclasses import asdict, replace
from datetime import timedelta
from pathlib import Path
from typing import Any, cast

import pytest
from fastapi.testclient import TestClient
from test_browser_sessions import BasicTestIdentityProvider, login, settings
from test_evidence_draft import create_draft, draft_fixture
from test_package_acquisition import CollectingAuditSink
from test_runtime_activation import FailSecondAuditSink
from test_target_session import target_session_operator

from atlas.api.app import create_app
from atlas.modules.identity.domain.models import AuthenticatedSubject
from atlas.modules.knowledge.adapters.draft_review_request_memory import (
    InMemoryOperationalKnowledgeReviewRequestPolicySource,
    InMemoryOperationalKnowledgeReviewRequestRepository,
)
from atlas.modules.knowledge.adapters.draft_review_request_postgres import (
    PostgreSQLOperationalKnowledgeReviewRequestRepository,
)
from atlas.modules.knowledge.adapters.draft_review_request_synthetic import (
    SyntheticOperationalKnowledgeReviewRequestAdapter,
)
from atlas.modules.knowledge.application.draft_review_request import (
    OperationalKnowledgeReviewRequestService,
    build_development_operational_knowledge_review_request_policy,
)
from atlas.modules.knowledge.application.draft_review_request_ports import (
    OperationalKnowledgeReviewRequestError,
    OperationalKnowledgeReviewRequestUncertainError,
)
from atlas.modules.knowledge.domain.draft_review_request import (
    OperationalKnowledgeReviewRequestInstruction,
    OperationalKnowledgeReviewRequestPolicySnapshot,
    OperationalKnowledgeReviewRequestReceipt,
    OperationalKnowledgeReviewRequestRecord,
)
from atlas.modules.knowledge.domain.evidence_draft import OperationalEvidenceKnowledgeDraftRecord

ACKNOWLEDGEMENT_FIELD = "acknowledged_result_is_only_an_unassigned_review_request"


class RecordingReviewRequestPermissionAuthorizer:
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
            raise OperationalKnowledgeReviewRequestError(
                "operational_knowledge_review_request_permission_denied"
            )


class UncertainReviewRequestAdapter:
    def __init__(self) -> None:
        self.calls = 0

    async def create_review_request(
        self, instruction: OperationalKnowledgeReviewRequestInstruction
    ) -> OperationalKnowledgeReviewRequestReceipt:
        del instruction
        self.calls += 1
        raise OperationalKnowledgeReviewRequestUncertainError(
            "operational_knowledge_review_request_storage_outcome_uncertain"
        )


class AlteredReviewRequestReceiptAdapter(SyntheticOperationalKnowledgeReviewRequestAdapter):
    async def create_review_request(
        self, instruction: OperationalKnowledgeReviewRequestInstruction
    ) -> OperationalKnowledgeReviewRequestReceipt:
        receipt = await super().create_review_request(instruction)
        altered = replace(receipt, domain_queue_id="review-queue.attacker-selected")
        payload = cast(dict[str, object], asdict(altered))
        payload.pop("canonical_digest")
        return replace(
            altered,
            canonical_digest=OperationalKnowledgeReviewRequestService._digest(
                OperationalKnowledgeReviewRequestService._normalize(payload)
            ),
        )


class BlockingReviewRequestAdapter(SyntheticOperationalKnowledgeReviewRequestAdapter):
    def __init__(self) -> None:
        super().__init__()
        self.started = asyncio.Event()
        self.release = asyncio.Event()

    async def create_review_request(
        self, instruction: OperationalKnowledgeReviewRequestInstruction
    ) -> OperationalKnowledgeReviewRequestReceipt:
        self.started.set()
        await self.release.wait()
        return await super().create_review_request(instruction)


async def review_request_fixture(
    *,
    audit_sink: CollectingAuditSink | FailSecondAuditSink | None = None,
    permission_authorizer: RecordingReviewRequestPermissionAuthorizer | None = None,
    adapter: SyntheticOperationalKnowledgeReviewRequestAdapter
    | UncertainReviewRequestAdapter
    | AlteredReviewRequestReceiptAdapter
    | BlockingReviewRequestAdapter
    | None = None,
) -> tuple[
    OperationalKnowledgeReviewRequestService,
    InMemoryOperationalKnowledgeReviewRequestRepository,
    OperationalEvidenceKnowledgeDraftRecord,
    OperationalKnowledgeReviewRequestPolicySnapshot,
    RecordingReviewRequestPermissionAuthorizer,
    SyntheticOperationalKnowledgeReviewRequestAdapter
    | UncertainReviewRequestAdapter
    | AlteredReviewRequestReceiptAdapter
    | BlockingReviewRequestAdapter,
    tuple[Any, ...],
]:
    draft_parts = await draft_fixture()
    draft_service, _, _, draft_policy, _, _, source = draft_parts
    evidence = source[0]
    draft = await create_draft(draft_service, evidence, draft_policy)
    policy = build_development_operational_knowledge_review_request_policy(
        organization_id=draft.organization_id,
        environment_id=draft.environment_id,
        issued_at=draft.created_at - timedelta(hours=1),
        expires_at=draft.created_at + timedelta(days=1),
    )
    repository = InMemoryOperationalKnowledgeReviewRequestRepository()
    authorizer = permission_authorizer or RecordingReviewRequestPermissionAuthorizer()
    resolved_adapter = adapter or SyntheticOperationalKnowledgeReviewRequestAdapter(
        clock=lambda: draft.created_at
    )
    service = OperationalKnowledgeReviewRequestService(
        repository=repository,
        source=draft_service,
        policy_source=InMemoryOperationalKnowledgeReviewRequestPolicySource((policy,)),
        permission_authorizer=authorizer,
        adapter=resolved_adapter,
        audit_sink=audit_sink or CollectingAuditSink(),
        environment_id=draft.environment_id,
        clock=lambda: draft.created_at,
    )
    return service, repository, draft, policy, authorizer, resolved_adapter, draft_parts


async def request_review(
    service: OperationalKnowledgeReviewRequestService,
    draft: OperationalEvidenceKnowledgeDraftRecord,
    policy: OperationalKnowledgeReviewRequestPolicySnapshot,
    *,
    actor: AuthenticatedSubject | None = None,
    key: str = "knowledge-review-request-001",
) -> OperationalKnowledgeReviewRequestRecord:
    return await service.create(
        actor=actor or target_session_operator("subject.connector-independent-knowledge-curator"),
        source_draft_id=draft.draft_id,
        source_draft_digest=draft.canonical_digest,
        orchestration_policy_id=policy.policy_id,
        orchestration_policy_digest=policy.canonical_digest,
        purpose="Request independent domain and security review for this exact immutable draft.",
        review_request_only_acknowledged=True,
        idempotency_key=key,
        correlation_id="cor_knowledge_review_request",
    )


@pytest.mark.asyncio
async def test_review_request_is_immutable_minimized_and_idempotent() -> None:
    audit = CollectingAuditSink()
    service, _, draft, policy, authorizer, adapter, _ = await review_request_fixture(
        audit_sink=audit
    )
    record = await request_review(service, draft, policy)
    repeated = await request_review(service, draft, policy)

    assert record.instance_state == "operational_knowledge_review_requested"
    assert record.knowledge_lifecycle == "review_requested"
    assert record.review_requested and record.immutable_manifest_confirmed
    assert record.domain_status == record.security_status == "awaiting_reviewer"
    assert not record.reviewer_assigned and not record.content_inspection_opened
    assert not record.domain_review_completed and not record.security_review_completed
    assert not record.knowledge_approved and not record.knowledge_published
    assert not record.retrieval_published and not record.model_context_available
    assert not record.execution_authorized and not record.infrastructure_mutation_performed
    assert repeated.reused and repeated.review_request_id == record.review_request_id
    assert isinstance(adapter, SyntheticOperationalKnowledgeReviewRequestAdapter)
    assert adapter.call_count == 1
    assert authorizer.calls == [(draft.organization_id, draft.environment_id)]
    assert [item.result_code for item in audit.records] == [
        "operational_knowledge_review_requested",
        "operational_knowledge_review_source_claimed",
        "operational_knowledge_review_request_created",
    ]


@pytest.mark.asyncio
async def test_review_request_atomically_rejects_concurrent_second_claim() -> None:
    adapter = BlockingReviewRequestAdapter()
    service, _, draft, policy, _, _, _ = await review_request_fixture(adapter=adapter)
    first = asyncio.create_task(request_review(service, draft, policy, key="review-first"))
    await adapter.started.wait()
    with pytest.raises(OperationalKnowledgeReviewRequestError, match="idempotency_conflict"):
        await request_review(service, draft, policy, key="review-second")
    adapter.release.set()
    record = await first
    assert record.review_requested and adapter.call_count == 1


@pytest.mark.asyncio
async def test_review_request_permission_denial_happens_before_claim() -> None:
    service, repository, draft, policy, _, adapter, _ = await review_request_fixture(
        permission_authorizer=RecordingReviewRequestPermissionAuthorizer(deny=True)
    )
    with pytest.raises(OperationalKnowledgeReviewRequestError, match="permission_denied"):
        await request_review(service, draft, policy)
    assert await repository.get_claim_by_source(source_draft_id=draft.draft_id) is None
    assert isinstance(adapter, SyntheticOperationalKnowledgeReviewRequestAdapter)
    assert adapter.call_count == 0


@pytest.mark.asyncio
async def test_review_request_uncertain_or_invalid_receipt_stays_claimed() -> None:
    uncertain = UncertainReviewRequestAdapter()
    service, repository, draft, policy, _, _, _ = await review_request_fixture(adapter=uncertain)
    with pytest.raises(OperationalKnowledgeReviewRequestUncertainError, match="uncertain"):
        await request_review(service, draft, policy)
    assert uncertain.calls == 1
    assert await repository.get_claim_by_source(source_draft_id=draft.draft_id)
    with pytest.raises(OperationalKnowledgeReviewRequestError, match="already_claimed"):
        await request_review(service, draft, policy)
    assert uncertain.calls == 1

    altered = AlteredReviewRequestReceiptAdapter(clock=lambda: draft.created_at)
    altered_service, _, altered_draft, altered_policy, _, _, _ = await review_request_fixture(
        adapter=altered
    )
    with pytest.raises(OperationalKnowledgeReviewRequestUncertainError, match="receipt_invalid"):
        await request_review(altered_service, altered_draft, altered_policy)


@pytest.mark.asyncio
async def test_review_request_claim_audit_failure_stays_claimed() -> None:
    service, repository, draft, policy, _, adapter, _ = await review_request_fixture(
        audit_sink=FailSecondAuditSink()
    )
    with pytest.raises(RuntimeError, match="audit unavailable"):
        await request_review(service, draft, policy)
    assert await repository.get_claim_by_source(source_draft_id=draft.draft_id)
    assert isinstance(adapter, SyntheticOperationalKnowledgeReviewRequestAdapter)
    assert adapter.call_count == 0


@pytest.mark.asyncio
async def test_review_request_postgres_round_trip_excludes_content_and_reviewer() -> None:
    service, repository, draft, policy, _, _, _ = await review_request_fixture()
    record = await request_review(service, draft, policy)
    claim = await repository.get_claim_by_source(source_draft_id=draft.draft_id)
    assert claim is not None
    raw_claim = OperationalKnowledgeReviewRequestService._normalize(asdict(claim))
    raw_record = OperationalKnowledgeReviewRequestService._normalize(asdict(record))
    assert isinstance(raw_claim, dict) and isinstance(raw_record, dict)
    assert (
        PostgreSQLOperationalKnowledgeReviewRequestRepository._claim_to_domain(raw_claim) == claim
    )
    assert (
        PostgreSQLOperationalKnowledgeReviewRequestRepository._record_to_domain(raw_record)
        == record
    )
    for hidden in (
        "draft_content",
        "evidence_content",
        "excerpt",
        "reviewer_id",
        "reviewer_group",
        "storage_location",
        "acl_principals",
        "encryption_key",
        "idempotency_key",
    ):
        assert hidden not in raw_claim and hidden not in raw_record


def test_review_request_api_forbids_routing_and_returns_minimized_metadata(
    tmp_path: Path,
) -> None:
    service, _, draft, policy, _, _, draft_parts = asyncio.run(review_request_fixture())
    draft_service = draft_parts[0]
    source = draft_parts[6]
    evidence_service = source[1]
    evidence_parts = source[2]
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
        "schema_version": "atlas.operational-knowledge-review-request-input.v1",
        "source_draft_id": draft.draft_id,
        "source_draft_digest": draft.canonical_digest,
        "orchestration_policy_id": policy.policy_id,
        "orchestration_policy_digest": policy.canonical_digest,
        "purpose": "Request independent domain and security review for this exact immutable draft.",
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
            operational_evidence_knowledge_draft_service=draft_service,
            operational_knowledge_review_request_service=service,
        )
    ) as client:
        login_response = login(client)
        endpoint = "/api/v1/knowledge/operational-review-requests"
        denied = client.post(endpoint, json=payload, headers={"Idempotency-Key": "review-api-1"})
        forbidden = client.post(
            endpoint,
            json={**payload, "reviewer_id": "subject.self-selected-reviewer"},
            headers={
                "Idempotency-Key": "review-api-2",
                "X-CSRF-Token": login_response.headers["X-CSRF-Token"],
            },
        )
        created = client.post(
            endpoint,
            json=payload,
            headers={
                "Idempotency-Key": "review-api-1",
                "X-CSRF-Token": login_response.headers["X-CSRF-Token"],
            },
        )
        assert created.status_code == 201, created.text
        review_request_id = created.json()["data"]["review_request_id"]
        read = client.get(f"{endpoint}/{review_request_id}")

    assert denied.status_code == 403 and forbidden.status_code == 422
    assert read.status_code == 200
    assert created.headers["Cache-Control"] == read.headers["Cache-Control"] == "no-store"
    data = created.json()["data"]
    assert data["knowledge_lifecycle"] == "review_requested"
    assert data["review_requested"] is True
    assert data["reviewer_assigned"] is False
    assert data["content_inspection_opened"] is False
    assert data["knowledge_approved"] is False
    assert data["retrieval_published"] is False
    for hidden in (
        "draft_content",
        "evidence_content",
        "excerpt",
        "reviewer_id",
        "reviewer_group",
        "storage_location",
        "acl_principals",
        "encryption_key",
        "request_binding_digest",
        "idempotency_digest",
        "idempotency_key",
    ):
        assert hidden not in data
