from __future__ import annotations

import asyncio
import json
import os
from dataclasses import asdict, replace
from datetime import timedelta
from pathlib import Path
from typing import Any, cast
from uuid import uuid4

import pytest
from alembic import command
from alembic.config import Config
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, delete, inspect, text
from sqlalchemy.ext.asyncio import create_async_engine
from test_browser_sessions import BasicTestIdentityProvider, login, settings
from test_evidence_draft import create_draft, draft_fixture
from test_package_acquisition import CollectingAuditSink
from test_runtime_activation import FailSecondAuditSink
from test_target_session import development_target_session_operator, target_session_operator

from atlas.api.app import create_app
from atlas.core.persistence.models import (
    OperationalKnowledgeReviewRequestClaimModel,
    OperationalKnowledgeReviewRequestModel,
)
from atlas.modules.identity.domain.models import AssuranceLevel, AuthenticatedSubject, SubjectKind
from atlas.modules.knowledge.adapters.draft_review_request_memory import (
    InMemoryOperationalKnowledgeReviewRequestPolicySource,
    InMemoryOperationalKnowledgeReviewRequestRepository,
)
from atlas.modules.knowledge.adapters.draft_review_request_postgres import (
    PostgreSQLOperationalKnowledgeReviewRequestRepository,
)
from atlas.modules.knowledge.adapters.draft_review_request_synthetic import (
    SyntheticOperationalKnowledgeReviewRequestAdapter,
    UnavailableOperationalKnowledgeReviewRequestAdapter,
)
from atlas.modules.knowledge.application.draft_review_request import (
    OperationalKnowledgeReviewRequestService,
    _signed_policy,
    build_development_operational_knowledge_review_request_policy,
)
from atlas.modules.knowledge.application.draft_review_request_ports import (
    OperationalKnowledgeReviewRequestError,
    OperationalKnowledgeReviewRequestUncertainError,
)
from atlas.modules.knowledge.domain.draft_review_request import (
    OperationalKnowledgeReviewRequestClaim,
    OperationalKnowledgeReviewRequestInstruction,
    OperationalKnowledgeReviewRequestPolicySnapshot,
    OperationalKnowledgeReviewRequestReceipt,
    OperationalKnowledgeReviewRequestRecord,
)
from atlas.modules.knowledge.domain.evidence_draft import OperationalEvidenceKnowledgeDraftRecord

ACKNOWLEDGEMENT_FIELD = "acknowledged_result_is_only_an_unassigned_review_request"
BACKEND_ROOT = Path(__file__).resolve().parents[1]


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
    available = True
    adapter_id = "operational-knowledge-review-request-adapter.synthetic"
    attestor_id = "subject.operational-knowledge-review-request-adapter-attestor"

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


class MismatchedReviewRequestAdapter(SyntheticOperationalKnowledgeReviewRequestAdapter):
    adapter_id = "operational-knowledge-review-request-adapter.mismatched"


class IdempotencyRaceReviewRequestRepository(InMemoryOperationalKnowledgeReviewRequestRepository):
    def __init__(self) -> None:
        super().__init__()
        self.raced_claim: OperationalKnowledgeReviewRequestClaim | None = None

    async def get_claim_by_idempotency_in_scope(
        self,
        *,
        claimed_by: str,
        idempotency_digest: str,
        organization_id: str,
        environment_id: str,
    ) -> OperationalKnowledgeReviewRequestClaim | None:
        del claimed_by, idempotency_digest, organization_id, environment_id
        return self.raced_claim

    async def claim(self, claim: OperationalKnowledgeReviewRequestClaim) -> bool:
        raced = replace(
            claim,
            source_draft_id="operational-evidence-knowledge-draft.concurrent-other",
            request_binding_digest="f" * 64,
            canonical_digest="0" * 64,
        )
        self.raced_claim = replace(
            raced,
            canonical_digest=OperationalKnowledgeReviewRequestService._digest(
                OperationalKnowledgeReviewRequestService._claim_payload(raced)
            ),
        )
        return False


async def review_request_fixture(
    *,
    audit_sink: CollectingAuditSink | FailSecondAuditSink | None = None,
    permission_authorizer: RecordingReviewRequestPermissionAuthorizer | None = None,
    adapter: SyntheticOperationalKnowledgeReviewRequestAdapter
    | UnavailableOperationalKnowledgeReviewRequestAdapter
    | UncertainReviewRequestAdapter
    | AlteredReviewRequestReceiptAdapter
    | BlockingReviewRequestAdapter
    | MismatchedReviewRequestAdapter
    | None = None,
    required_assurance_level: AssuranceLevel = AssuranceLevel.SINGLE_FACTOR,
    repository: InMemoryOperationalKnowledgeReviewRequestRepository | None = None,
) -> tuple[
    OperationalKnowledgeReviewRequestService,
    InMemoryOperationalKnowledgeReviewRequestRepository,
    OperationalEvidenceKnowledgeDraftRecord,
    OperationalKnowledgeReviewRequestPolicySnapshot,
    RecordingReviewRequestPermissionAuthorizer,
    SyntheticOperationalKnowledgeReviewRequestAdapter
    | UnavailableOperationalKnowledgeReviewRequestAdapter
    | UncertainReviewRequestAdapter
    | AlteredReviewRequestReceiptAdapter
    | BlockingReviewRequestAdapter
    | MismatchedReviewRequestAdapter,
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
    if policy.required_assurance_level is not required_assurance_level:
        policy = replace(
            policy,
            required_assurance_level=required_assurance_level,
            canonical_digest="0" * 64,
        )
        policy = replace(policy, canonical_digest=_signed_policy(policy))
    resolved_repository = repository or InMemoryOperationalKnowledgeReviewRequestRepository()
    authorizer = permission_authorizer or RecordingReviewRequestPermissionAuthorizer()
    resolved_adapter = adapter or SyntheticOperationalKnowledgeReviewRequestAdapter(
        clock=lambda: draft.created_at
    )
    service = OperationalKnowledgeReviewRequestService(
        repository=resolved_repository,
        source=draft_service,
        policy_source=InMemoryOperationalKnowledgeReviewRequestPolicySource((policy,)),
        permission_authorizer=authorizer,
        adapter=resolved_adapter,
        audit_sink=audit_sink or CollectingAuditSink(),
        environment_id=draft.environment_id,
        clock=lambda: draft.created_at,
    )
    return service, resolved_repository, draft, policy, authorizer, resolved_adapter, draft_parts


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
        review_request_option_id=service._option_id(draft, policy),
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
async def test_review_request_accepts_development_identity_under_default_policy() -> None:
    service, _, draft, policy, _, _, _ = await review_request_fixture()
    actor = development_target_session_operator("subject.connector-independent-knowledge-curator")

    record = await request_review(service, draft, policy, actor=actor)

    assert policy.required_assurance_level is AssuranceLevel.SINGLE_FACTOR
    assert record.requested_by == actor.subject_id


@pytest.mark.asyncio
async def test_review_request_inventory_and_server_provided_options_are_authoritative() -> None:
    service, repository, draft, policy, _, adapter, _ = await review_request_fixture()
    actor = development_target_session_operator("subject.connector-independent-knowledge-curator")

    assert (
        await service.list_requests(
            actor=actor,
            source_draft_id=draft.draft_id,
            correlation_id="cor_review_inventory_empty",
        )
        == ()
    )
    options = await service.list_options(
        actor=actor,
        source_draft_id=draft.draft_id,
        correlation_id="cor_review_options",
    )
    assert len(options) == 1
    option = options[0]
    assert option.review_request_option_id == service._option_id(draft, policy)
    assert option.source_draft_digest == draft.canonical_digest
    assert option.orchestration_policy_digest == policy.canonical_digest
    assert option.required_assurance_level is AssuranceLevel.SINGLE_FACTOR

    with pytest.raises(OperationalKnowledgeReviewRequestError, match="option_invalid"):
        await service.create(
            actor=actor,
            source_draft_id=draft.draft_id,
            review_request_option_id="operational-knowledge-review-request-option.invalid",
            purpose=(
                "Request independent domain and security review for this exact immutable draft."
            ),
            review_request_only_acknowledged=True,
            idempotency_key="invalid-server-option",
            correlation_id="cor_invalid_server_option",
        )
    assert (
        await repository.get_claim_by_source_in_scope(
            source_draft_id=draft.draft_id,
            organization_id=draft.organization_id,
            environment_id=draft.environment_id,
        )
        is None
    )
    assert getattr(adapter, "call_count", 0) == 0

    record = await request_review(service, draft, policy, actor=actor)
    assert (
        await service.list_options(
            actor=actor,
            source_draft_id=draft.draft_id,
            correlation_id="cor_review_options_consumed",
        )
        == ()
    )
    assert await service.list_requests(
        actor=actor,
        source_draft_id=draft.draft_id,
        correlation_id="cor_review_inventory",
    ) == (record,)


@pytest.mark.asyncio
async def test_review_request_unavailable_adapter_fails_before_claim() -> None:
    service, repository, draft, policy, _, _, _ = await review_request_fixture(
        adapter=UnavailableOperationalKnowledgeReviewRequestAdapter()
    )
    actor = development_target_session_operator("subject.connector-independent-knowledge-curator")

    assert (
        await service.list_options(
            actor=actor,
            source_draft_id=draft.draft_id,
            correlation_id="cor_unavailable_options",
        )
        == ()
    )
    with pytest.raises(OperationalKnowledgeReviewRequestError, match="adapter_unavailable"):
        await request_review(service, draft, policy, actor=actor)
    assert (
        await repository.get_claim_by_source_in_scope(
            source_draft_id=draft.draft_id,
            organization_id=draft.organization_id,
            environment_id=draft.environment_id,
        )
        is None
    )


@pytest.mark.asyncio
async def test_review_request_adapter_identity_mismatch_fails_before_claim() -> None:
    adapter = MismatchedReviewRequestAdapter()
    service, repository, draft, policy, _, _, _ = await review_request_fixture(adapter=adapter)
    actor = development_target_session_operator("subject.connector-independent-knowledge-curator")

    assert (
        await service.list_options(
            actor=actor,
            source_draft_id=draft.draft_id,
            correlation_id="cor_mismatched_adapter_options",
        )
        == ()
    )
    with pytest.raises(OperationalKnowledgeReviewRequestError, match="adapter_mismatch"):
        await request_review(service, draft, policy, actor=actor)
    assert (
        await repository.get_claim_by_source_in_scope(
            source_draft_id=draft.draft_id,
            organization_id=draft.organization_id,
            environment_id=draft.environment_id,
        )
        is None
    )
    assert adapter.call_count == 0


@pytest.mark.parametrize(
    "required_assurance_level",
    [AssuranceLevel.MULTI_FACTOR, AssuranceLevel.HARDWARE_BACKED],
)
@pytest.mark.asyncio
async def test_review_request_enforces_explicit_stronger_assurance_policy(
    required_assurance_level: AssuranceLevel,
) -> None:
    service, _, draft, policy, authorizer, adapter, _ = await review_request_fixture(
        required_assurance_level=required_assurance_level
    )

    with pytest.raises(OperationalKnowledgeReviewRequestError, match="assurance_required"):
        await request_review(
            service,
            draft,
            policy,
            actor=development_target_session_operator(
                "subject.connector-independent-knowledge-curator"
            ),
        )

    assert authorizer.calls == []
    assert getattr(adapter, "call_count", 0) == 0


@pytest.mark.asyncio
async def test_review_request_denies_non_human_identity() -> None:
    service, _, draft, policy, authorizer, adapter, _ = await review_request_fixture()
    actor = replace(
        development_target_session_operator("subject.connector-independent-knowledge-curator"),
        kind=SubjectKind.SERVICE,
    )

    with pytest.raises(OperationalKnowledgeReviewRequestError, match="human_required"):
        await request_review(service, draft, policy, actor=actor)

    assert authorizer.calls == []
    assert getattr(adapter, "call_count", 0) == 0


@pytest.mark.asyncio
async def test_review_request_rejects_foreign_tenant_draft_before_authorization() -> None:
    service, repository, draft, policy, authorizer, adapter, _ = await review_request_fixture()
    foreign_actor = replace(
        development_target_session_operator("subject.connector-independent-knowledge-curator"),
        organization_id="organization.foreign",
    )

    with pytest.raises(OperationalKnowledgeReviewRequestError, match="source_not_found"):
        await request_review(service, draft, policy, actor=foreign_actor)

    assert authorizer.calls == []
    assert getattr(adapter, "call_count", 0) == 0
    assert (
        await repository.get_claim_by_source_in_scope(
            source_draft_id=draft.draft_id,
            organization_id=draft.organization_id,
            environment_id=draft.environment_id,
        )
        is None
    )


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
async def test_review_request_resolves_raced_idempotency_conflict() -> None:
    repository = IdempotencyRaceReviewRequestRepository()
    service, _, draft, policy, _, adapter, _ = await review_request_fixture(repository=repository)

    with pytest.raises(OperationalKnowledgeReviewRequestError, match="idempotency_conflict"):
        await request_review(service, draft, policy)

    assert getattr(adapter, "call_count", 0) == 0


@pytest.mark.asyncio
async def test_review_request_permission_denial_happens_before_claim() -> None:
    service, repository, draft, policy, _, adapter, _ = await review_request_fixture(
        permission_authorizer=RecordingReviewRequestPermissionAuthorizer(deny=True)
    )
    with pytest.raises(OperationalKnowledgeReviewRequestError, match="permission_denied"):
        await request_review(service, draft, policy)
    assert (
        await repository.get_claim_by_source_in_scope(
            source_draft_id=draft.draft_id,
            organization_id=draft.organization_id,
            environment_id=draft.environment_id,
        )
        is None
    )
    assert isinstance(adapter, SyntheticOperationalKnowledgeReviewRequestAdapter)
    assert adapter.call_count == 0


@pytest.mark.asyncio
async def test_review_request_uncertain_or_invalid_receipt_stays_claimed() -> None:
    uncertain = UncertainReviewRequestAdapter()
    service, repository, draft, policy, _, _, _ = await review_request_fixture(adapter=uncertain)
    with pytest.raises(OperationalKnowledgeReviewRequestUncertainError, match="uncertain"):
        await request_review(service, draft, policy)
    assert uncertain.calls == 1
    assert await repository.get_claim_by_source_in_scope(
        source_draft_id=draft.draft_id,
        organization_id=draft.organization_id,
        environment_id=draft.environment_id,
    )
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
    assert await repository.get_claim_by_source_in_scope(
        source_draft_id=draft.draft_id,
        organization_id=draft.organization_id,
        environment_id=draft.environment_id,
    )
    assert isinstance(adapter, SyntheticOperationalKnowledgeReviewRequestAdapter)
    assert adapter.call_count == 0


@pytest.mark.asyncio
async def test_review_request_postgres_round_trip_excludes_content_and_reviewer() -> None:
    service, repository, draft, policy, _, _, _ = await review_request_fixture()
    record = await request_review(service, draft, policy)
    claim = await repository.get_claim_by_source_in_scope(
        source_draft_id=draft.draft_id,
        organization_id=draft.organization_id,
        environment_id=draft.environment_id,
    )
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


@pytest.mark.asyncio
async def test_review_request_memory_repository_isolates_identical_tenant_identifiers() -> None:
    service, repository, draft, policy, _, _, _ = await review_request_fixture()
    first_record = await request_review(service, draft, policy)
    first_claim = await repository.get_claim_by_source_in_scope(
        source_draft_id=draft.draft_id,
        organization_id=draft.organization_id,
        environment_id=draft.environment_id,
    )
    assert first_claim is not None
    second_claim = replace(
        first_claim,
        organization_id="organization.foreign",
        canonical_digest="0" * 64,
    )
    second_claim = replace(
        second_claim,
        canonical_digest=service._digest(service._claim_payload(second_claim)),
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

    assert await repository.claim(second_claim)
    assert await repository.add(second_record)
    assert (
        await repository.get_in_scope(
            review_request_id=first_record.review_request_id,
            organization_id=first_record.organization_id,
            environment_id=first_record.environment_id,
        )
        == first_record
    )
    assert (
        await repository.get_in_scope(
            review_request_id=second_record.review_request_id,
            organization_id=second_record.organization_id,
            environment_id=second_record.environment_id,
        )
        == second_record
    )


@pytest.mark.asyncio
async def test_live_postgres_review_requests_isolate_same_identifiers_before_deserialization(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    database_url = os.getenv("ATLAS_TEST_POSTGRES_DSN")
    if not database_url:
        pytest.skip("ATLAS_TEST_POSTGRES_DSN is not configured")
    service, repository, draft, policy, _, _, _ = await review_request_fixture()
    base_record = await request_review(service, draft, policy)
    base_claim = await repository.get_claim_by_source_in_scope(
        source_draft_id=draft.draft_id,
        organization_id=draft.organization_id,
        environment_id=draft.environment_id,
    )
    assert base_claim is not None
    suffix = uuid4().hex[:12]
    claim_id = f"operational-knowledge-review-request-claim.scoped-{suffix}"
    review_request_id = f"operational-knowledge-review-request.scoped-{suffix}"
    source_draft_id = f"operational-evidence-knowledge-draft.scoped-review-{suffix}"
    first_claim = replace(
        base_claim,
        claim_id=claim_id,
        review_request_id=review_request_id,
        source_draft_id=source_draft_id,
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
        review_request_id=review_request_id,
        claim_id=claim_id,
        source_draft_id=source_draft_id,
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

    async def exercise_repository() -> None:
        first_engine = create_async_engine(database_url)
        second_engine = create_async_engine(database_url)
        first_repository = PostgreSQLOperationalKnowledgeReviewRequestRepository(first_engine)
        second_repository = PostgreSQLOperationalKnowledgeReviewRequestRepository(second_engine)
        try:
            assert await first_repository.claim(first_claim)
            assert await second_repository.claim(second_claim)
            assert await first_repository.add(first_record)
            assert await second_repository.add(second_record)
            assert (
                await first_repository.get_in_scope(
                    review_request_id=review_request_id,
                    organization_id=first_record.organization_id,
                    environment_id=first_record.environment_id,
                )
                == first_record
            )
            assert (
                await second_repository.get_in_scope(
                    review_request_id=review_request_id,
                    organization_id=second_record.organization_id,
                    environment_id=second_record.environment_id,
                )
                == second_record
            )

            def reject_deserialization(
                raw: dict[str, Any],
            ) -> OperationalKnowledgeReviewRequestRecord:
                del raw
                raise AssertionError("foreign tenant payload must not be deserialized")

            with monkeypatch.context() as scoped_patch:
                scoped_patch.setattr(
                    PostgreSQLOperationalKnowledgeReviewRequestRepository,
                    "_record_to_domain",
                    staticmethod(reject_deserialization),
                )
                assert (
                    await second_repository.get_in_scope(
                        review_request_id=review_request_id,
                        organization_id="organization.missing",
                        environment_id=second_record.environment_id,
                    )
                    is None
                )
        finally:
            async with first_engine.begin() as connection:
                await connection.execute(
                    delete(OperationalKnowledgeReviewRequestModel).where(
                        OperationalKnowledgeReviewRequestModel.review_request_id
                        == review_request_id
                    )
                )
                await connection.execute(
                    delete(OperationalKnowledgeReviewRequestClaimModel).where(
                        OperationalKnowledgeReviewRequestClaimModel.claim_id == claim_id
                    )
                )
            await first_repository.close()
            await second_repository.close()

    def run_with_selector_loop() -> None:
        with asyncio.Runner(loop_factory=asyncio.SelectorEventLoop) as runner:
            runner.run(exercise_repository())

    await asyncio.to_thread(run_with_selector_loop)


def test_live_postgres_review_request_migration_round_trip_preserves_and_rejects_collision(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    database_url = os.getenv("ATLAS_TEST_POSTGRES_DSN")
    if not database_url:
        pytest.skip("ATLAS_TEST_POSTGRES_DSN is not configured")
    monkeypatch.setenv("ATLAS_DATABASE_URL", database_url)
    config = Config(str(BACKEND_ROOT / "alembic.ini"))
    config.set_main_option("script_location", str(BACKEND_ROOT / "migrations"))
    suffix = uuid4().hex[:12]
    organization_id = f"organization.legacy-review-{suffix}"
    second_organization_id = f"organization.legacy-review-other-{suffix}"
    environment_id = "environment.development"
    claim_id = f"operational-knowledge-review-request-claim.legacy-{suffix}"
    review_request_id = f"operational-knowledge-review-request.legacy-{suffix}"
    source_draft_id = f"operational-evidence-knowledge-draft.legacy-review-{suffix}"
    expected_digests = {
        "operational_knowledge_review_request_claims": "7" * 64,
        "operational_knowledge_review_requests": "8" * 64,
    }
    engine = create_engine(database_url)
    command.downgrade(config, "20260825_0163")
    try:
        with engine.begin() as connection:
            connection.execute(
                text(
                    "INSERT INTO operational_knowledge_review_request_claims "
                    "(claim_id, source_draft_id, review_request_id, claimed_by, "
                    "idempotency_digest, organization_id, environment_id, canonical_digest, "
                    "payload) VALUES (:claim_id, :source_id, :request_id, :actor, :idem, "
                    ":organization_id, :environment_id, :digest, CAST(:payload AS JSONB))"
                ),
                {
                    "claim_id": claim_id,
                    "source_id": source_draft_id,
                    "request_id": review_request_id,
                    "actor": f"subject.legacy-review-{suffix}",
                    "idem": "9" * 64,
                    "organization_id": organization_id,
                    "environment_id": environment_id,
                    "digest": expected_digests["operational_knowledge_review_request_claims"],
                    "payload": json.dumps({"legacy": "review-claim"}),
                },
            )
            connection.execute(
                text(
                    "INSERT INTO operational_knowledge_review_requests "
                    "(review_request_id, claim_id, source_draft_id, knowledge_item_id, "
                    "requested_by, organization_id, environment_id, canonical_digest, payload) "
                    "VALUES (:request_id, :claim_id, :source_id, :knowledge_id, :actor, "
                    ":organization_id, :environment_id, :digest, CAST(:payload AS JSONB))"
                ),
                {
                    "request_id": review_request_id,
                    "claim_id": claim_id,
                    "source_id": source_draft_id,
                    "knowledge_id": f"knowledge-item.legacy-review-{suffix}",
                    "actor": f"subject.legacy-review-{suffix}",
                    "organization_id": organization_id,
                    "environment_id": environment_id,
                    "digest": expected_digests["operational_knowledge_review_requests"],
                    "payload": json.dumps({"legacy": "review-record"}),
                },
            )

        command.upgrade(config, "head")
        with engine.connect() as connection:
            for table_name, expected in expected_digests.items():
                actual = connection.execute(
                    text(
                        f"SELECT canonical_digest FROM {table_name} "
                        "WHERE organization_id = :organization_id "
                        "AND environment_id = :environment_id"
                    ),
                    {
                        "organization_id": organization_id,
                        "environment_id": environment_id,
                    },
                ).scalar_one()
                assert actual == expected
        schema = inspect(engine)
        assert schema.get_pk_constraint("operational_knowledge_review_request_claims")[
            "constrained_columns"
        ] == ["claim_id", "organization_id", "environment_id"]
        assert schema.get_pk_constraint("operational_knowledge_review_requests")[
            "constrained_columns"
        ] == ["review_request_id", "organization_id", "environment_id"]

        command.downgrade(config, "20260825_0163")
        command.upgrade(config, "head")
        with engine.begin() as connection:
            connection.execute(
                text(
                    "INSERT INTO operational_knowledge_review_request_claims "
                    "(claim_id, source_draft_id, review_request_id, claimed_by, "
                    "idempotency_digest, organization_id, environment_id, canonical_digest, "
                    "payload) SELECT claim_id, source_draft_id, review_request_id, claimed_by, "
                    "idempotency_digest, :second_organization_id, environment_id, "
                    "canonical_digest, payload FROM operational_knowledge_review_request_claims "
                    "WHERE organization_id = :organization_id AND claim_id = :claim_id"
                ),
                {
                    "second_organization_id": second_organization_id,
                    "organization_id": organization_id,
                    "claim_id": claim_id,
                },
            )
            connection.execute(
                text(
                    "INSERT INTO operational_knowledge_review_requests "
                    "(review_request_id, claim_id, source_draft_id, knowledge_item_id, "
                    "requested_by, organization_id, environment_id, canonical_digest, payload) "
                    "SELECT review_request_id, claim_id, source_draft_id, knowledge_item_id, "
                    "requested_by, :second_organization_id, environment_id, canonical_digest, "
                    "payload FROM operational_knowledge_review_requests "
                    "WHERE organization_id = :organization_id "
                    "AND review_request_id = :review_request_id"
                ),
                {
                    "second_organization_id": second_organization_id,
                    "organization_id": organization_id,
                    "review_request_id": review_request_id,
                },
            )

        with pytest.raises(RuntimeError, match="identifiers overlap between tenants"):
            command.downgrade(config, "20260825_0163")
    finally:
        with engine.begin() as connection:
            connection.execute(
                text(
                    "DELETE FROM operational_knowledge_review_requests "
                    "WHERE source_draft_id = :source_draft_id"
                ),
                {"source_draft_id": source_draft_id},
            )
            connection.execute(
                text(
                    "DELETE FROM operational_knowledge_review_request_claims "
                    "WHERE source_draft_id = :source_draft_id"
                ),
                {"source_draft_id": source_draft_id},
            )
        command.upgrade(config, "head")
        engine.dispose()


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
        "review_request_option_id": service._option_id(draft, policy),
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
        options = client.get(f"{endpoint}/options", params={"source_draft_id": draft.draft_id})
        empty_inventory = client.get(endpoint, params={"source_draft_id": draft.draft_id})
        denied = client.post(endpoint, json=payload, headers={"Idempotency-Key": "review-api-1"})
        forbidden = client.post(
            endpoint,
            json={
                **payload,
                "orchestration_policy_id": policy.policy_id,
                "orchestration_policy_digest": policy.canonical_digest,
                "reviewer_id": "subject.self-selected-reviewer",
            },
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
        inventory = client.get(endpoint, params={"source_draft_id": draft.draft_id})
        consumed_options = client.get(
            f"{endpoint}/options", params={"source_draft_id": draft.draft_id}
        )
        read = client.get(f"{endpoint}/{review_request_id}")

    assert denied.status_code == 403 and forbidden.status_code == 422
    assert options.status_code == 200 and len(options.json()["data"]) == 1
    assert (
        options.json()["data"][0]["review_request_option_id"] == payload["review_request_option_id"]
    )
    assert empty_inventory.status_code == 200 and empty_inventory.json()["data"] == []
    assert inventory.status_code == 200 and len(inventory.json()["data"]) == 1
    assert consumed_options.status_code == 200 and consumed_options.json()["data"] == []
    assert read.status_code == 200
    assert all(
        item.headers["Cache-Control"] == "no-store"
        for item in (options, empty_inventory, created, inventory, consumed_options, read)
    )
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
        "manifest_artifact_id",
        "acl_principals",
        "encryption_key",
        "request_binding_digest",
        "idempotency_digest",
        "idempotency_key",
        "requested_by",
        "organization_id",
        "environment_id",
    ):
        assert hidden not in data
