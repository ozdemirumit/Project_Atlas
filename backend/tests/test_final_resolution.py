from __future__ import annotations

import asyncio
from dataclasses import asdict, replace
from datetime import timedelta

import pytest
from pydantic import ValidationError
from test_package_acquisition import CollectingAuditSink
from test_review_decision import decide, review_decision_fixture
from test_target_session import development_target_session_operator, target_session_operator

from atlas.api.final_resolution_schemas import OperationalKnowledgeFinalResolutionInput
from atlas.modules.identity.domain.models import (
    AssuranceLevel,
    AuthenticatedSubject,
    AuthenticationMethod,
    SubjectKind,
)
from atlas.modules.knowledge.adapters.final_resolution_memory import (
    InMemoryOperationalKnowledgeFinalResolutionPolicySource,
    InMemoryOperationalKnowledgeFinalResolutionRepository,
)
from atlas.modules.knowledge.adapters.final_resolution_postgres import (
    PostgreSQLOperationalKnowledgeFinalResolutionRepository,
)
from atlas.modules.knowledge.adapters.final_resolution_synthetic import (
    SyntheticOperationalKnowledgeFinalResolutionAttestor,
)
from atlas.modules.knowledge.application.final_resolution import (
    OperationalKnowledgeFinalResolutionService,
    build_development_operational_knowledge_final_resolution_policy,
)
from atlas.modules.knowledge.application.final_resolution_ports import (
    OperationalKnowledgeFinalResolutionError,
)
from atlas.modules.knowledge.domain.draft_review_request import (
    OperationalKnowledgeReviewRequestRecord,
)
from atlas.modules.knowledge.domain.evidence_draft import OperationalEvidenceKnowledgeDraftRecord
from atlas.modules.knowledge.domain.final_resolution import (
    OperationalKnowledgeFinalResolutionInstruction,
    OperationalKnowledgeFinalResolutionPolicySnapshot,
    OperationalKnowledgeFinalResolutionReceipt,
    OperationalKnowledgeFinalResolutionRecord,
)
from atlas.modules.knowledge.domain.review_decision import (
    OperationalKnowledgeTrackReviewDecisionRecord,
)


class StaticFinalResolutionSource:
    def __init__(
        self,
        decisions: tuple[OperationalKnowledgeTrackReviewDecisionRecord, ...],
        request: OperationalKnowledgeReviewRequestRecord,
        draft: OperationalEvidenceKnowledgeDraftRecord,
    ) -> None:
        self.decisions = decisions
        self.request = request
        self.draft = draft

    async def final_resolution_source(
        self, *, review_request_id: str
    ) -> tuple[
        tuple[OperationalKnowledgeTrackReviewDecisionRecord, ...],
        OperationalKnowledgeReviewRequestRecord,
        OperationalEvidenceKnowledgeDraftRecord,
    ]:
        if review_request_id != self.request.review_request_id:
            raise OperationalKnowledgeFinalResolutionError(
                "operational_knowledge_final_resolution_source_not_found"
            )
        return self.decisions, self.request, self.draft


class RecordingFinalResolutionPermissionAuthorizer:
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
            raise OperationalKnowledgeFinalResolutionError(
                "operational_knowledge_final_resolution_permission_denied"
            )


class BlockingFinalResolutionAttestor(SyntheticOperationalKnowledgeFinalResolutionAttestor):
    def __init__(self) -> None:
        super().__init__()
        self.started = asyncio.Event()
        self.release = asyncio.Event()

    async def attest(
        self, instruction: OperationalKnowledgeFinalResolutionInstruction
    ) -> OperationalKnowledgeFinalResolutionReceipt:
        self.started.set()
        await self.release.wait()
        return await super().attest(instruction)


async def final_resolution_fixture(
    *,
    changes_required: bool = False,
    one_track_only: bool = False,
    attestor: SyntheticOperationalKnowledgeFinalResolutionAttestor | None = None,
    authorizer: RecordingFinalResolutionPermissionAuthorizer | None = None,
) -> tuple[
    OperationalKnowledgeFinalResolutionService,
    InMemoryOperationalKnowledgeFinalResolutionRepository,
    StaticFinalResolutionSource,
    OperationalKnowledgeFinalResolutionPolicySnapshot,
    AuthenticatedSubject,
    SyntheticOperationalKnowledgeFinalResolutionAttestor,
    RecordingFinalResolutionPermissionAuthorizer,
    CollectingAuditSink,
]:
    (
        decision_service,
        _,
        content,
        finding,
        presentation,
        secret,
        decision_policy,
        *_,
    ) = await review_decision_fixture()
    domain = await decide(
        decision_service,
        content,
        finding,
        presentation,
        secret,
        decision_policy,
        disposition_code=(
            "review-disposition.changes-required"
            if changes_required
            else "review-disposition.passed"
        ),
    )
    source_bundle = await decision_service._source.review_decision_source(
        finding_presentation_id=presentation.finding_presentation_id
    )
    request = source_bundle[6]
    draft = source_bundle[7]
    decisions: tuple[OperationalKnowledgeTrackReviewDecisionRecord, ...] = (domain,)
    if not one_track_only:
        security_basis = ("review-basis.access-control", "review-basis.policy-compliance")
        security = replace(
            domain,
            decision_id="decision.synthetic-security-final-source",
            claim_id="claim.synthetic-security-final-source",
            source_finding_presentation_id="finding-presentation.synthetic-security-final",
            source_finding_presentation_digest=decision_service._digest(
                "finding-presentation.synthetic-security-final"
            ),
            track_code="review-track.security",
            disposition_code="review-disposition.passed",
            basis_codes=security_basis,
            basis_digest=decision_service._digest(security_basis),
            domain_review_completed=False,
            security_review_completed=True,
            domain_review_passed=False,
            security_review_passed=True,
            correction_required=False,
            decided_by_subject_digest=decision_service._digest(
                [decision_policy.subject_digest_salt_digest, "subject.security-reviewer"]
            ),
            canonical_digest="0" * 64,
        )
        security = replace(
            security,
            canonical_digest=decision_service._digest(decision_service._record_payload(security)),
        )
        decisions = (domain, security)
    source = StaticFinalResolutionSource(decisions, request, draft)
    policy = build_development_operational_knowledge_final_resolution_policy(
        organization_id=request.organization_id,
        environment_id=request.environment_id,
        issued_at=presentation.presented_at - timedelta(hours=1),
        expires_at=presentation.presented_at + timedelta(days=1),
    )
    resolved_attestor = attestor or SyntheticOperationalKnowledgeFinalResolutionAttestor()
    resolved_attestor._clock = lambda: presentation.presented_at
    repository = InMemoryOperationalKnowledgeFinalResolutionRepository()
    permission = authorizer or RecordingFinalResolutionPermissionAuthorizer()
    audit = CollectingAuditSink()
    service = OperationalKnowledgeFinalResolutionService(
        repository=repository,
        source=source,
        policy_source=InMemoryOperationalKnowledgeFinalResolutionPolicySource((policy,)),
        permission_authorizer=permission,
        attestor=resolved_attestor,
        audit_sink=audit,
        environment_id=request.environment_id,
        clock=lambda: presentation.presented_at,
    )
    actor = development_target_session_operator("subject.knowledge-final-approver")
    return service, repository, source, policy, actor, resolved_attestor, permission, audit


async def resolve(
    service: OperationalKnowledgeFinalResolutionService,
    source: StaticFinalResolutionSource,
    policy: OperationalKnowledgeFinalResolutionPolicySnapshot,
    actor: AuthenticatedSubject,
    *,
    disposition_code: str = "final-resolution.approved",
    idempotency_key: str = "knowledge-final-resolution-001",
) -> OperationalKnowledgeFinalResolutionRecord:
    ordered = tuple(sorted(source.decisions, key=lambda item: item.track_code))
    return await service.create(
        actor=actor,
        review_request_id=source.request.review_request_id,
        review_request_digest=source.request.canonical_digest,
        decision_ids=(ordered[0].decision_id, ordered[1].decision_id),
        decision_digests=(ordered[0].canonical_digest, ordered[1].canonical_digest),
        disposition_code=disposition_code,
        basis_codes=(
            "final-basis.domain-and-security-passed",
            (
                "final-basis.governance-scope-accepted"
                if disposition_code == "final-resolution.approved"
                else "final-basis.governance-scope-rejected"
            ),
        ),
        resolution_policy_id=policy.policy_id,
        resolution_policy_digest=policy.canonical_digest,
        purpose="Record the accountable final resolution for this exact passed review generation.",
        immutable_generation_acknowledged=True,
        publication_readiness_only_acknowledged=True,
        no_operational_authority_acknowledged=True,
        browser_session_id="session_knowledge_final_resolution_001",
        idempotency_key=idempotency_key,
        correlation_id="cor_knowledge_final_resolution",
    )


@pytest.mark.asyncio
@pytest.mark.parametrize("disposition", ["final-resolution.approved", "final-resolution.rejected"])
async def test_final_resolution_accepts_development_password_and_is_immutable(
    disposition: str,
) -> None:
    (
        service,
        repository,
        source,
        policy,
        actor,
        attestor,
        permission,
        audit,
    ) = await final_resolution_fixture()
    assert actor.authentication_method is AuthenticationMethod.DEVELOPMENT
    assert actor.assurance_level is AssuranceLevel.DEVELOPMENT
    record = await resolve(service, source, policy, actor, disposition_code=disposition)
    repeated = await resolve(service, source, policy, actor, disposition_code=disposition)
    replay = await service.get(
        actor=actor,
        resolution_id=record.resolution_id,
        browser_session_id="session_knowledge_final_resolution_001",
        correlation_id="cor_knowledge_final_resolution_read",
    )

    approved = disposition == "final-resolution.approved"
    assert record.knowledge_approved is approved
    assert record.publication_ready is approved
    assert not record.knowledge_published and not record.retrieval_published
    assert not record.workflow_continued and not record.execution_authorized
    assert repeated.reused and replay.reused and len(attestor.calls) == 1
    assert await repository.get(resolution_id=record.resolution_id) == record
    assert len(permission.calls) == 3
    raw = asdict(record)
    for forbidden in ("content", "finding", "free_form_rationale", "artifact_location"):
        assert forbidden not in raw
    assert [item.result_code for item in audit.records] == [
        "operational_knowledge_final_resolution_requested",
        "operational_knowledge_final_resolution_claimed",
        "operational_knowledge_final_resolution_recorded",
        "operational_knowledge_final_resolution_read",
        "operational_knowledge_final_resolution_read",
    ]


@pytest.mark.asyncio
async def test_final_resolution_rejects_non_human_actor() -> None:
    service, repository, source, policy, actor, *_ = await final_resolution_fixture()
    service_actor = replace(
        actor,
        kind=SubjectKind.SERVICE,
        authentication_method=AuthenticationMethod.WORKLOAD_TOKEN,
    )

    with pytest.raises(OperationalKnowledgeFinalResolutionError, match="human_required"):
        await resolve(service, source, policy, service_actor)

    assert (
        await repository.get_claim_by_review_request(
            review_request_id=source.request.review_request_id
        )
        is None
    )


@pytest.mark.asyncio
@pytest.mark.parametrize("changes_required,one_track_only", [(True, False), (False, True)])
async def test_final_resolution_requires_two_passed_tracks(
    changes_required: bool, one_track_only: bool
) -> None:
    service, repository, source, policy, actor, attestor, *_ = await final_resolution_fixture(
        changes_required=changes_required, one_track_only=one_track_only
    )
    with pytest.raises(OperationalKnowledgeFinalResolutionError):
        if one_track_only:
            decision = source.decisions[0]
            source.decisions = (decision, decision)
        await resolve(service, source, policy, actor)
    assert not attestor.calls
    assert (
        await repository.get_claim_by_review_request(
            review_request_id=source.request.review_request_id
        )
        is None
    )


@pytest.mark.asyncio
async def test_final_resolution_rejects_curator_or_reviewer_before_claim() -> None:
    service, repository, source, policy, _, attestor, *_ = await final_resolution_fixture()
    with pytest.raises(OperationalKnowledgeFinalResolutionError, match="separation_required"):
        await resolve(service, source, policy, target_session_operator(source.draft.curated_by))
    assert not attestor.calls
    assert (
        await repository.get_claim_by_review_request(
            review_request_id=source.request.review_request_id
        )
        is None
    )


@pytest.mark.asyncio
async def test_final_resolution_atomic_claim_blocks_concurrent_duplicate() -> None:
    blocker = BlockingFinalResolutionAttestor()
    service, repository, source, policy, actor, *_ = await final_resolution_fixture(
        attestor=blocker
    )
    first = asyncio.create_task(resolve(service, source, policy, actor))
    await blocker.started.wait()
    with pytest.raises(OperationalKnowledgeFinalResolutionError, match="already_claimed"):
        await resolve(service, source, policy, actor)
    blocker.release.set()
    record = await first
    assert await repository.get(resolution_id=record.resolution_id) == record


def test_postgres_mapping_contains_metadata_only() -> None:
    assert "content" not in OperationalKnowledgeFinalResolutionRecord.__dataclass_fields__
    assert "finding" not in OperationalKnowledgeFinalResolutionRecord.__dataclass_fields__
    assert "raw_identity" not in OperationalKnowledgeFinalResolutionRecord.__dataclass_fields__
    assert hasattr(PostgreSQLOperationalKnowledgeFinalResolutionRepository, "claim")
    assert hasattr(PostgreSQLOperationalKnowledgeFinalResolutionRepository, "add")


def test_final_resolution_api_input_forbids_identity_content_and_lifecycle_fields() -> None:
    payload = {
        "review_request_digest": "a" * 64,
        "decision_ids": ["decision.domain.test", "decision.security.test"],
        "decision_digests": ["b" * 64, "c" * 64],
        "disposition_code": "final-resolution.approved",
        "basis_codes": ["final-basis.domain-and-security-passed"],
        "resolution_policy_id": "operational-knowledge-final-resolution-policy.development",
        "resolution_policy_digest": "d" * 64,
        "purpose": "Record one accountable final resolution for this exact review generation.",
        "acknowledged_immutable_review_generation": True,
        "acknowledged_publication_readiness_only": True,
        "acknowledged_no_operational_authority": True,
    }
    assert OperationalKnowledgeFinalResolutionInput.model_validate(payload)
    for forbidden in ("approver_id", "content", "knowledge_approved", "publication_ready"):
        with pytest.raises(ValidationError):
            OperationalKnowledgeFinalResolutionInput.model_validate(
                {**payload, forbidden: "caller-selected"}
            )
