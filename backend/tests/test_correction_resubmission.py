from __future__ import annotations

import asyncio
from dataclasses import asdict, replace
from datetime import timedelta
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError
from test_browser_sessions import BasicTestIdentityProvider, login, settings
from test_package_acquisition import CollectingAuditSink
from test_review_decision import decide, review_decision_fixture
from test_runtime_activation import FailSecondAuditSink
from test_target_session import development_target_session_operator

from atlas.api.app import create_app
from atlas.api.correction_resubmission_schemas import OperationalKnowledgeCorrectionInput
from atlas.modules.identity.domain.models import (
    AssuranceLevel,
    AuthenticatedSubject,
    AuthenticationMethod,
    SubjectKind,
)
from atlas.modules.knowledge.adapters.correction_resubmission_memory import (
    InMemoryOperationalKnowledgeCorrectionPolicySource,
    InMemoryOperationalKnowledgeCorrectionRepository,
)
from atlas.modules.knowledge.adapters.correction_resubmission_postgres import (
    PostgreSQLOperationalKnowledgeCorrectionRepository,
)
from atlas.modules.knowledge.adapters.correction_resubmission_synthetic import (
    SyntheticOperationalKnowledgeCorrectionAdapter,
    UnavailableOperationalKnowledgeCorrectionAdapter,
)
from atlas.modules.knowledge.application.correction_resubmission import (
    OperationalKnowledgeCorrectionService,
    build_development_operational_knowledge_correction_policy,
)
from atlas.modules.knowledge.application.correction_resubmission_ports import (
    OperationalKnowledgeCorrectionError,
)
from atlas.modules.knowledge.domain.correction_resubmission import (
    OperationalKnowledgeCorrectionInstruction,
    OperationalKnowledgeCorrectionPolicySnapshot,
    OperationalKnowledgeCorrectionReceipt,
    OperationalKnowledgeCorrectionRecord,
)
from atlas.modules.knowledge.domain.draft_review_request import (
    OperationalKnowledgeReviewRequestRecord,
)
from atlas.modules.knowledge.domain.evidence_draft import OperationalEvidenceKnowledgeDraftRecord
from atlas.modules.knowledge.domain.review_decision import (
    OperationalKnowledgeTrackReviewDecisionRecord,
)


class StaticCorrectionSource:
    def __init__(
        self,
        decisions: tuple[OperationalKnowledgeTrackReviewDecisionRecord, ...],
        request: OperationalKnowledgeReviewRequestRecord,
        draft: OperationalEvidenceKnowledgeDraftRecord,
    ) -> None:
        self.decisions = decisions
        self.request = request
        self.draft = draft

    async def correction_resubmission_source(
        self,
        *,
        review_request_id: str,
        organization_id: str,
        environment_id: str,
    ) -> tuple[
        tuple[OperationalKnowledgeTrackReviewDecisionRecord, ...],
        OperationalKnowledgeReviewRequestRecord,
        OperationalEvidenceKnowledgeDraftRecord,
    ]:
        if (
            review_request_id != self.request.review_request_id
            or organization_id != self.request.organization_id
            or environment_id != self.request.environment_id
        ):
            raise OperationalKnowledgeCorrectionError(
                "operational_knowledge_correction_source_not_found"
            )
        return self.decisions, self.request, self.draft


class RecordingCorrectionPermissionAuthorizer:
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
            raise OperationalKnowledgeCorrectionError(
                "operational_knowledge_correction_permission_denied"
            )


class BlockingCorrectionAdapter(SyntheticOperationalKnowledgeCorrectionAdapter):
    def __init__(self) -> None:
        super().__init__()
        self.started = asyncio.Event()
        self.release = asyncio.Event()

    async def correct_and_resubmit(
        self, instruction: OperationalKnowledgeCorrectionInstruction
    ) -> OperationalKnowledgeCorrectionReceipt:
        self.started.set()
        await self.release.wait()
        return await super().correct_and_resubmit(instruction)


async def correction_fixture(
    *,
    adapter: SyntheticOperationalKnowledgeCorrectionAdapter | None = None,
    authorizer: RecordingCorrectionPermissionAuthorizer | None = None,
    audit_sink: CollectingAuditSink | FailSecondAuditSink | None = None,
    all_passed: bool = False,
    one_track_only: bool = False,
    required_assurance_level: AssuranceLevel = AssuranceLevel.SINGLE_FACTOR,
) -> tuple[
    OperationalKnowledgeCorrectionService,
    InMemoryOperationalKnowledgeCorrectionRepository,
    StaticCorrectionSource,
    OperationalKnowledgeCorrectionPolicySnapshot,
    AuthenticatedSubject,
    SyntheticOperationalKnowledgeCorrectionAdapter,
    RecordingCorrectionPermissionAuthorizer,
    CollectingAuditSink | FailSecondAuditSink,
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
            "review-disposition.passed" if all_passed else "review-disposition.changes-required"
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
            decision_id="decision.synthetic-security-correction-source",
            claim_id="claim.synthetic-security-correction-source",
            source_finding_presentation_id="finding-presentation.synthetic-security-correction",
            source_finding_presentation_digest=decision_service._digest(
                "finding-presentation.synthetic-security-correction"
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
            canonical_digest="0" * 64,
        )
        security = replace(
            security,
            canonical_digest=decision_service._digest(decision_service._record_payload(security)),
        )
        decisions = (domain, security)
    source = StaticCorrectionSource(decisions, request, draft)
    policy = build_development_operational_knowledge_correction_policy(
        organization_id=request.organization_id,
        environment_id=request.environment_id,
        issued_at=presentation.presented_at - timedelta(hours=1),
        expires_at=presentation.presented_at + timedelta(days=1),
        required_assurance_level=required_assurance_level,
    )
    resolved_adapter = adapter or SyntheticOperationalKnowledgeCorrectionAdapter(
        clock=lambda: presentation.presented_at
    )
    resolved_adapter._clock = lambda: presentation.presented_at
    repository = InMemoryOperationalKnowledgeCorrectionRepository()
    permission = authorizer or RecordingCorrectionPermissionAuthorizer()
    audit = audit_sink or CollectingAuditSink()
    service = OperationalKnowledgeCorrectionService(
        repository=repository,
        source=source,
        policy_source=InMemoryOperationalKnowledgeCorrectionPolicySource((policy,)),
        permission_authorizer=permission,
        adapter=resolved_adapter,
        audit_sink=audit,
        environment_id=request.environment_id,
        clock=lambda: presentation.presented_at,
    )
    actor = development_target_session_operator(draft.curated_by)
    return service, repository, source, policy, actor, resolved_adapter, permission, audit


async def correct(
    service: OperationalKnowledgeCorrectionService,
    source: StaticCorrectionSource,
    policy: OperationalKnowledgeCorrectionPolicySnapshot,
    actor: AuthenticatedSubject,
    *,
    idempotency_key: str = "knowledge-correction-001",
    browser_session_id: str = "session_knowledge_correction_001",
) -> OperationalKnowledgeCorrectionRecord:
    ordered = tuple(sorted(source.decisions, key=lambda item: item.track_code))
    return await service.create(
        actor=actor,
        source_review_request_id=source.request.review_request_id,
        source_review_request_digest=source.request.canonical_digest,
        source_decision_ids=(ordered[0].decision_id, ordered[1].decision_id),
        source_decision_digests=(ordered[0].canonical_digest, ordered[1].canonical_digest),
        correction_submission_id="trusted-correction-submission.synthetic-001",
        correction_submission_digest=service._digest("trusted-correction-submission-001"),
        correction_policy_id=policy.policy_id,
        correction_policy_digest=policy.canonical_digest,
        purpose="Create a corrected immutable draft and a fresh independent review generation.",
        exact_change_requirements_addressed_acknowledged=True,
        new_immutable_generation_acknowledged=True,
        no_later_authority_acknowledged=True,
        browser_session_id=browser_session_id,
        idempotency_key=idempotency_key,
        correlation_id="cor_knowledge_correction",
    )


@pytest.mark.asyncio
async def test_correction_accepts_development_password_and_is_immutable_idempotent() -> None:
    (
        service,
        repository,
        source,
        policy,
        actor,
        adapter,
        authorizer,
        audit,
    ) = await correction_fixture()
    assert actor.authentication_method is AuthenticationMethod.DEVELOPMENT
    assert actor.assurance_level is AssuranceLevel.DEVELOPMENT
    assert policy.required_assurance_level is AssuranceLevel.SINGLE_FACTOR
    record = await correct(service, source, policy, actor)
    repeated = await correct(service, source, policy, actor)
    replay = await service.get(
        actor=actor,
        correction_id=record.correction_id,
        browser_session_id="session_knowledge_correction_001",
        correlation_id="cor_knowledge_correction_read",
    )

    assert record.correction_created and record.corrected_draft_created
    assert record.review_resubmitted and record.review_generation == 2
    assert not record.reviewer_assigned and not record.content_inspection_opened
    assert not record.domain_review_completed and not record.security_review_completed
    assert not record.knowledge_approved and not record.knowledge_published
    assert not record.retrieval_published and not record.execution_authorized
    assert repeated.reused and replay.reused and len(adapter.calls) == 1
    assert await repository.get(correction_id=record.correction_id) == record
    new_request, new_draft = await service.protected_content_lineage(
        review_request_id=record.new_review_request_id,
        organization_id=record.organization_id,
        environment_id=record.environment_id,
    )
    assert new_draft.draft_id == record.new_draft_id
    assert new_draft.draft_version_id != source.draft.draft_version_id
    assert new_request.source_draft_id == new_draft.draft_id
    assert new_request.domain_status == "awaiting_reviewer"
    assert new_request.security_status == "awaiting_reviewer"
    assert not new_request.reviewer_assigned
    raw = asdict(record)
    for forbidden in (
        "corrected_content",
        "correction_patch",
        "finding_summary",
        "artifact_location",
        "raw_identity",
    ):
        assert forbidden not in raw
    assert len(authorizer.calls) == 3
    assert isinstance(audit, CollectingAuditSink)
    assert [item.result_code for item in audit.records] == [
        "operational_knowledge_correction_requested",
        "operational_knowledge_correction_claimed",
        "operational_knowledge_correction_resubmitted",
        "operational_knowledge_correction_read",
        "operational_knowledge_correction_read",
    ]


@pytest.mark.parametrize(
    "required_assurance_level",
    [AssuranceLevel.MULTI_FACTOR, AssuranceLevel.HARDWARE_BACKED],
)
@pytest.mark.asyncio
async def test_correction_enforces_explicit_stronger_assurance_policy(
    required_assurance_level: AssuranceLevel,
) -> None:
    service, repository, source, policy, actor, *_ = await correction_fixture(
        required_assurance_level=required_assurance_level
    )

    with pytest.raises(OperationalKnowledgeCorrectionError, match="assurance_required"):
        await correct(service, source, policy, actor)

    assert (
        await repository.get_claim_by_source_request(
            source_review_request_id=source.request.review_request_id
        )
        is None
    )


@pytest.mark.asyncio
async def test_correction_rejects_non_human_actor() -> None:
    service, repository, source, policy, actor, *_ = await correction_fixture()
    service_actor = replace(
        actor,
        kind=SubjectKind.SERVICE,
        authentication_method=AuthenticationMethod.WORKLOAD_TOKEN,
    )

    with pytest.raises(OperationalKnowledgeCorrectionError, match="human_required"):
        await correct(service, source, policy, service_actor)

    assert (
        await repository.get_claim_by_source_request(
            source_review_request_id=source.request.review_request_id
        )
        is None
    )


@pytest.mark.asyncio
@pytest.mark.parametrize("all_passed,one_track_only", [(True, False), (False, True)])
async def test_correction_requires_two_tracks_and_at_least_one_change(
    all_passed: bool, one_track_only: bool
) -> None:
    service, repository, source, policy, actor, adapter, *_ = await correction_fixture(
        all_passed=all_passed, one_track_only=one_track_only
    )
    with pytest.raises(
        OperationalKnowledgeCorrectionError, match=r"source_invalid|request_invalid"
    ):
        if one_track_only:
            decision = source.decisions[0]
            await service.create(
                actor=actor,
                source_review_request_id=source.request.review_request_id,
                source_review_request_digest=source.request.canonical_digest,
                source_decision_ids=(decision.decision_id, decision.decision_id),
                source_decision_digests=(decision.canonical_digest, decision.canonical_digest),
                correction_submission_id="trusted-correction-submission.synthetic-001",
                correction_submission_digest=service._digest("submission"),
                correction_policy_id=policy.policy_id,
                correction_policy_digest=policy.canonical_digest,
                purpose="Attempt an invalid correction without two completed review tracks.",
                exact_change_requirements_addressed_acknowledged=True,
                new_immutable_generation_acknowledged=True,
                no_later_authority_acknowledged=True,
                browser_session_id="session_knowledge_correction_001",
                idempotency_key="invalid-correction",
                correlation_id="cor_invalid_correction",
            )
        else:
            await correct(service, source, policy, actor)
    assert not adapter.calls
    assert (
        await repository.get_claim_by_source_request(
            source_review_request_id=source.request.review_request_id
        )
        is None
    )


@pytest.mark.asyncio
async def test_correction_denies_wrong_curator_and_permission_before_claim() -> None:
    denied = RecordingCorrectionPermissionAuthorizer(deny=True)
    service, repository, source, policy, actor, adapter, *_ = await correction_fixture(
        authorizer=denied
    )
    with pytest.raises(OperationalKnowledgeCorrectionError, match="permission_denied"):
        await correct(service, source, policy, actor)
    assert not adapter.calls

    service, repository, source, policy, actor, adapter, *_ = await correction_fixture()
    wrong = replace(actor, subject_id="subject.synthetic-unaccountable-curator")
    with pytest.raises(OperationalKnowledgeCorrectionError, match="source_not_found"):
        await correct(service, source, policy, wrong)
    assert not adapter.calls
    assert (
        await repository.get_claim_by_source_request(
            source_review_request_id=source.request.review_request_id
        )
        is None
    )


@pytest.mark.asyncio
async def test_correction_claim_survives_adapter_and_audit_failure() -> None:
    service, repository, source, policy, actor, *_ = await correction_fixture()
    service._adapter = UnavailableOperationalKnowledgeCorrectionAdapter()
    with pytest.raises(OperationalKnowledgeCorrectionError, match="unavailable"):
        await correct(service, source, policy, actor)
    assert (
        await repository.get_claim_by_source_request(
            source_review_request_id=source.request.review_request_id
        )
        is not None
    )
    with pytest.raises(OperationalKnowledgeCorrectionError, match="claimed_outcome_uncertain"):
        await correct(service, source, policy, actor)

    failing_audit = FailSecondAuditSink()
    service, repository, source, policy, actor, adapter, *_ = await correction_fixture(
        audit_sink=failing_audit
    )
    with pytest.raises(RuntimeError, match="audit unavailable"):
        await correct(service, source, policy, actor)
    assert not adapter.calls
    assert (
        await repository.get_claim_by_source_request(
            source_review_request_id=source.request.review_request_id
        )
        is not None
    )


@pytest.mark.asyncio
async def test_correction_atomically_excludes_conflicting_second_request() -> None:
    adapter = BlockingCorrectionAdapter()
    service, _, source, policy, actor, *_ = await correction_fixture(adapter=adapter)
    first = asyncio.create_task(correct(service, source, policy, actor))
    await adapter.started.wait()
    with pytest.raises(OperationalKnowledgeCorrectionError, match="idempotency_conflict"):
        await correct(
            service,
            source,
            policy,
            actor,
            idempotency_key="knowledge-correction-002",
        )
    adapter.release.set()
    record = await first
    assert record.review_resubmitted and len(adapter.calls) == 1


@pytest.mark.asyncio
async def test_correction_postgres_mapping_is_metadata_only() -> None:
    service, repository, source, policy, actor, *_ = await correction_fixture()
    record = await correct(service, source, policy, actor)
    claim = await repository.get_claim_by_source_request(
        source_review_request_id=source.request.review_request_id
    )
    assert claim is not None
    raw_claim = service._normalize(asdict(claim))
    raw_record = service._normalize(asdict(record))
    assert isinstance(raw_claim, dict) and isinstance(raw_record, dict)
    assert PostgreSQLOperationalKnowledgeCorrectionRepository._claim_to_domain(raw_claim) == claim
    assert (
        PostgreSQLOperationalKnowledgeCorrectionRepository._record_to_domain(raw_record) == record
    )
    serialized = str(raw_record)
    for forbidden in ("corrected_content", "correction_patch", "finding_summary"):
        assert forbidden not in serialized


def test_correction_api_schema_forbids_caller_selected_authority() -> None:
    valid = {
        "source_review_request_digest": "a" * 64,
        "source_decision_ids": ("decision.domain", "decision.security"),
        "source_decision_digests": ("b" * 64, "c" * 64),
        "correction_submission_id": "trusted-correction-submission.synthetic-001",
        "correction_submission_digest": "d" * 64,
        "correction_policy_id": "correction-policy.synthetic",
        "correction_policy_digest": "e" * 64,
        "purpose": "Create a corrected immutable draft and review generation.",
        "acknowledged_exact_change_requirements_addressed": True,
        "acknowledged_new_immutable_review_generation": True,
        "acknowledged_no_approval_or_operational_authority": True,
    }
    OperationalKnowledgeCorrectionInput.model_validate(valid)
    for field, value in (
        ("corrected_content", "secret"),
        ("track_code", "review-track.domain"),
        ("knowledge_approved", True),
        ("publication", True),
        ("execution_authorized", True),
    ):
        with pytest.raises(ValidationError):
            OperationalKnowledgeCorrectionInput.model_validate({**valid, field: value})


@pytest.mark.asyncio
async def test_correction_api_requires_csrf_and_returns_minimized_metadata(
    tmp_path: Path,
) -> None:
    service, _, source, policy, actor, *_ = await correction_fixture()
    ordered = tuple(sorted(source.decisions, key=lambda item: item.track_code))
    payload: dict[str, object] = {
        "schema_version": "atlas.operational-knowledge-correction-input.v1",
        "source_review_request_digest": source.request.canonical_digest,
        "source_decision_ids": [ordered[0].decision_id, ordered[1].decision_id],
        "source_decision_digests": [
            ordered[0].canonical_digest,
            ordered[1].canonical_digest,
        ],
        "correction_submission_id": "trusted-correction-submission.synthetic-001",
        "correction_submission_digest": service._digest("trusted-correction-submission-001"),
        "correction_policy_id": policy.policy_id,
        "correction_policy_digest": policy.canonical_digest,
        "purpose": "Create a corrected immutable draft and a fresh independent review generation.",
        "acknowledged_exact_change_requirements_addressed": True,
        "acknowledged_new_immutable_review_generation": True,
        "acknowledged_no_approval_or_operational_authority": True,
    }
    app_settings = settings(
        development_subject_id=actor.subject_id,
        mcp_builder_generation_root=tmp_path / "mcp-builder-generations",
    )
    endpoint = f"/api/v1/knowledge/review-requests/{source.request.review_request_id}/corrections"
    with TestClient(
        create_app(
            app_settings,
            identity_provider=BasicTestIdentityProvider(actor),
            operational_knowledge_correction_service=service,
        )
    ) as client:
        login_response = login(client)
        denied = client.post(
            endpoint,
            json=payload,
            headers={"Idempotency-Key": "correction-api-denied"},
        )
        forbidden = client.post(
            endpoint,
            json={**payload, "corrected_content": "must never enter the ordinary API"},
            headers={
                "Idempotency-Key": "correction-api-forbidden",
                "X-CSRF-Token": login_response.headers["X-CSRF-Token"],
            },
        )
        created = client.post(
            endpoint,
            json=payload,
            headers={
                "Idempotency-Key": "correction-api-created",
                "X-CSRF-Token": login_response.headers["X-CSRF-Token"],
            },
        )
        assert created.status_code == 201, created.text
        correction_id = created.json()["data"]["correction_id"]
        read = client.get(f"{endpoint}/{correction_id}")

    assert denied.status_code == 403 and forbidden.status_code == 422
    assert read.status_code == 200
    assert created.headers["Cache-Control"].startswith("no-store")
    assert read.headers["Cache-Control"].startswith("no-store")
    data = created.json()["data"]
    assert data["review_generation"] == 2
    assert data["review_resubmitted"] is True
    assert data["knowledge_approved"] is False
    assert data["retrieval_published"] is False
    for hidden in (
        "corrected_content",
        "correction_patch",
        "new_draft_artifact_id",
        "new_manifest_artifact_id",
        "corrected_by_subject_digest",
        "browser_session_binding_digest",
        "request_binding_digest",
        "idempotency_digest",
    ):
        assert hidden not in data
