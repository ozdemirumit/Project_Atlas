from __future__ import annotations

import asyncio
from dataclasses import asdict, replace
from datetime import timedelta

import pytest
from test_package_acquisition import CollectingAuditSink
from test_protected_inspection import (
    domain_reviewer,
    lease_domain_inspection,
    protected_inspection_fixture,
)

from atlas.modules.identity.domain.models import AuthenticatedSubject
from atlas.modules.knowledge.adapters.protected_content_memory import (
    InMemoryOperationalKnowledgeProtectedContentPolicySource,
    InMemoryOperationalKnowledgeProtectedContentRepository,
)
from atlas.modules.knowledge.adapters.protected_content_postgres import (
    PostgreSQLOperationalKnowledgeProtectedContentRepository,
)
from atlas.modules.knowledge.adapters.protected_content_synthetic import (
    SyntheticOperationalKnowledgeProtectedContentPresenter,
    UnavailableOperationalKnowledgeProtectedContentPresenter,
)
from atlas.modules.knowledge.application.protected_content import (
    OperationalKnowledgeProtectedContentService,
    build_development_operational_knowledge_protected_content_policy,
)
from atlas.modules.knowledge.application.protected_content_ports import (
    OperationalKnowledgeProtectedContentError,
    OperationalKnowledgeProtectedContentPresenter,
    OperationalKnowledgeProtectedContentUncertainError,
)
from atlas.modules.knowledge.domain.protected_content import (
    OperationalKnowledgeProtectedContentGrant,
    OperationalKnowledgeProtectedContentInstruction,
    OperationalKnowledgeProtectedContentPolicySnapshot,
    OperationalKnowledgeProtectedContentPresenterGrant,
)
from atlas.modules.knowledge.domain.protected_inspection import (
    OperationalKnowledgeProtectedInspectionRecord,
)


class RecordingProtectedContentPermissionAuthorizer:
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
            raise OperationalKnowledgeProtectedContentError(
                "operational_knowledge_protected_content_permission_denied"
            )


class BlockingProtectedContentPresenter(SyntheticOperationalKnowledgeProtectedContentPresenter):
    def __init__(self) -> None:
        super().__init__()
        self.started = asyncio.Event()
        self.release = asyncio.Event()

    async def present(
        self, instruction: OperationalKnowledgeProtectedContentInstruction
    ) -> OperationalKnowledgeProtectedContentPresenterGrant:
        self.started.set()
        await self.release.wait()
        self._clock = lambda: instruction.expires_at - timedelta(minutes=5)
        return await super().present(instruction)


class AlteredProtectedContentPresenter(SyntheticOperationalKnowledgeProtectedContentPresenter):
    async def present(
        self, instruction: OperationalKnowledgeProtectedContentInstruction
    ) -> OperationalKnowledgeProtectedContentPresenterGrant:
        self._clock = lambda: instruction.expires_at - timedelta(minutes=5)
        grant = await super().present(instruction)
        altered = replace(grant.receipt, track_code="review-track.security")
        altered = replace(
            altered,
            canonical_digest=OperationalKnowledgeProtectedContentService._receipt_digest(altered),
        )
        return OperationalKnowledgeProtectedContentPresenterGrant(
            receipt=altered, content=grant.content
        )


async def protected_content_fixture(
    *,
    presenter: OperationalKnowledgeProtectedContentPresenter | None = None,
    authorizer: RecordingProtectedContentPermissionAuthorizer | None = None,
    clock_offset: timedelta = timedelta(),
) -> tuple[
    OperationalKnowledgeProtectedContentService,
    InMemoryOperationalKnowledgeProtectedContentRepository,
    OperationalKnowledgeProtectedInspectionRecord,
    str,
    OperationalKnowledgeProtectedContentPolicySnapshot,
    RecordingProtectedContentPermissionAuthorizer,
    CollectingAuditSink,
]:
    inspection_service, _, assignment, inspection_policy, *_ = await protected_inspection_fixture()
    lease = await lease_domain_inspection(inspection_service, assignment, inspection_policy)
    policy = build_development_operational_knowledge_protected_content_policy(
        organization_id=assignment.organization_id,
        environment_id=assignment.environment_id,
        issued_at=assignment.created_at - timedelta(hours=1),
        expires_at=assignment.created_at + timedelta(days=1),
    )
    repository = InMemoryOperationalKnowledgeProtectedContentRepository()
    permission_authorizer = authorizer or RecordingProtectedContentPermissionAuthorizer()
    audit = CollectingAuditSink()
    service = OperationalKnowledgeProtectedContentService(
        repository=repository,
        source=inspection_service,
        policy_source=InMemoryOperationalKnowledgeProtectedContentPolicySource((policy,)),
        permission_authorizer=permission_authorizer,
        presenter=presenter
        or SyntheticOperationalKnowledgeProtectedContentPresenter(
            clock=lambda: assignment.created_at + clock_offset
        ),
        audit_sink=audit,
        environment_id=assignment.environment_id,
        clock=lambda: assignment.created_at + clock_offset,
    )
    assert lease.lease_secret is not None
    return (
        service,
        repository,
        lease.record,
        lease.lease_secret,
        policy,
        permission_authorizer,
        audit,
    )


async def present_content(
    service: OperationalKnowledgeProtectedContentService,
    lease: OperationalKnowledgeProtectedInspectionRecord,
    lease_secret: str,
    policy: OperationalKnowledgeProtectedContentPolicySnapshot,
    *,
    actor: AuthenticatedSubject | None = None,
    secret: str | None = None,
    idempotency_key: str = "knowledge-protected-content-001",
) -> OperationalKnowledgeProtectedContentGrant:
    return await service.create(
        actor=actor or domain_reviewer(),
        source_lease_id=lease.lease_id,
        source_lease_digest=lease.canonical_digest,
        presentation_policy_id=policy.policy_id,
        presentation_policy_digest=policy.canonical_digest,
        purpose="Inspect the exact assigned-track snapshot inside a read-only boundary.",
        sensitive_read_only_acknowledged=True,
        browser_session_id="session_knowledge_inspection_001",
        lease_secrets={"review-track.domain": secret or lease_secret},
        idempotency_key=idempotency_key,
        correlation_id="cor_knowledge_protected_content",
    )


@pytest.mark.asyncio
async def test_protected_content_is_bounded_plain_text_and_idempotent() -> None:
    (
        service,
        repository,
        lease,
        secret,
        policy,
        authorizer,
        audit,
    ) = await protected_content_fixture()
    grant = await present_content(service, lease, secret, policy)
    repeated = await present_content(service, lease, secret, policy)

    assert grant.content.startswith("Operational knowledge review snapshot")
    assert grant.record.presented_content_digest == repeated.record.presented_content_digest
    assert repeated.record.reused
    assert grant.record.content_disclosed and grant.record.redaction_applied
    assert not grant.record.domain_review_completed
    assert not grant.record.knowledge_approved
    assert not grant.record.execution_authorized
    assert "content" not in asdict(grant.record)
    persisted = await repository.get(presentation_id=grant.record.presentation_id)
    assert persisted == grant.record
    assert authorizer.calls == [
        (grant.record.organization_id, grant.record.environment_id),
        (grant.record.organization_id, grant.record.environment_id),
    ]
    assert [record.result_code for record in audit.records] == [
        "operational_knowledge_protected_content_requested",
        "operational_knowledge_protected_content_claimed",
        "operational_knowledge_protected_content_presented",
        "operational_knowledge_protected_content_read",
    ]


@pytest.mark.asyncio
async def test_protected_content_rejects_wrong_cookie_before_claim() -> None:
    service, repository, lease, secret, policy, *_ = await protected_content_fixture()

    with pytest.raises(OperationalKnowledgeProtectedContentError, match="source_not_found"):
        await present_content(service, lease, secret, policy, secret="wrong-lease-secret")

    assert await repository.get_claim_by_source_lease(source_lease_id=lease.lease_id) is None


@pytest.mark.asyncio
async def test_protected_content_permission_denial_happens_before_claim() -> None:
    authorizer = RecordingProtectedContentPermissionAuthorizer(deny=True)
    service, repository, lease, secret, policy, *_ = await protected_content_fixture(
        authorizer=authorizer
    )

    with pytest.raises(OperationalKnowledgeProtectedContentError, match="permission_denied"):
        await present_content(service, lease, secret, policy)

    assert await repository.get_claim_by_source_lease(source_lease_id=lease.lease_id) is None


@pytest.mark.asyncio
async def test_protected_content_rejects_wrong_assignee_and_expired_lease_before_claim() -> None:
    service, repository, lease, secret, policy, *_ = await protected_content_fixture()
    with pytest.raises(OperationalKnowledgeProtectedContentError, match="source_not_found"):
        await present_content(
            service,
            lease,
            secret,
            policy,
            actor=replace(domain_reviewer(), subject_id="subject.synthetic-unassigned-reviewer"),
        )
    assert await repository.get_claim_by_source_lease(source_lease_id=lease.lease_id) is None

    (
        expired_service,
        expired_repository,
        expired_lease,
        expired_secret,
        expired_policy,
        *_,
    ) = await protected_content_fixture(clock_offset=timedelta(minutes=11))
    with pytest.raises(OperationalKnowledgeProtectedContentError, match="source_invalid"):
        await present_content(expired_service, expired_lease, expired_secret, expired_policy)
    assert (
        await expired_repository.get_claim_by_source_lease(source_lease_id=expired_lease.lease_id)
        is None
    )


@pytest.mark.asyncio
async def test_protected_content_atomically_rejects_concurrent_second_claim() -> None:
    presenter = BlockingProtectedContentPresenter()
    service, repository, lease, secret, policy, *_ = await protected_content_fixture(
        presenter=presenter
    )
    first = asyncio.create_task(present_content(service, lease, secret, policy))
    await presenter.started.wait()
    with pytest.raises(OperationalKnowledgeProtectedContentError, match="idempotency_conflict"):
        await present_content(
            service,
            lease,
            secret,
            policy,
            idempotency_key="knowledge-protected-content-002",
        )
    presenter.release.set()
    grant = await first
    assert await repository.get(presentation_id=grant.record.presentation_id) == grant.record


@pytest.mark.asyncio
async def test_protected_content_rejects_altered_receipt_and_preserves_claim() -> None:
    presenter = AlteredProtectedContentPresenter()
    service, repository, lease, secret, policy, *_ = await protected_content_fixture(
        presenter=presenter
    )
    with pytest.raises(OperationalKnowledgeProtectedContentUncertainError, match="receipt_invalid"):
        await present_content(service, lease, secret, policy)
    assert await repository.get_claim_by_source_lease(source_lease_id=lease.lease_id) is not None
    assert await repository.get_by_source_lease(source_lease_id=lease.lease_id) is None


@pytest.mark.asyncio
async def test_protected_content_get_replays_only_identical_active_snapshot() -> None:
    service, _, lease, secret, policy, *_ = await protected_content_fixture()
    grant = await present_content(service, lease, secret, policy)
    replay = await service.get(
        actor=domain_reviewer(),
        source_lease_id=lease.lease_id,
        presentation_id=grant.record.presentation_id,
        browser_session_id="session_knowledge_inspection_001",
        lease_secrets={"review-track.domain": secret},
        correlation_id="cor_knowledge_protected_content_replay",
    )
    assert replay.record.reused
    assert replay.content == grant.content
    assert replay.record.presented_content_digest == grant.record.presented_content_digest


@pytest.mark.asyncio
async def test_failed_first_presentation_stays_claimed_and_is_not_retried() -> None:
    service, repository, lease, secret, policy, *_, audit = await protected_content_fixture(
        presenter=UnavailableOperationalKnowledgeProtectedContentPresenter()
    )

    with pytest.raises(OperationalKnowledgeProtectedContentError, match="presenter_unavailable"):
        await present_content(service, lease, secret, policy)
    assert await repository.get_claim_by_source_lease(source_lease_id=lease.lease_id) is not None
    with pytest.raises(OperationalKnowledgeProtectedContentError, match="already_claimed"):
        await present_content(service, lease, secret, policy)
    assert audit.records[-1].result_code == "operational_knowledge_protected_content_failed"


@pytest.mark.asyncio
async def test_protected_content_postgres_mapping_contains_metadata_only() -> None:
    service, repository, lease, secret, policy, *_ = await protected_content_fixture()
    grant = await present_content(service, lease, secret, policy)
    claim = await repository.get_claim_by_source_lease(source_lease_id=lease.lease_id)
    assert claim is not None

    raw_claim = OperationalKnowledgeProtectedContentService._normalize(asdict(claim))
    raw_record = OperationalKnowledgeProtectedContentService._normalize(asdict(grant.record))
    assert (
        PostgreSQLOperationalKnowledgeProtectedContentRepository._claim_to_domain(raw_claim)
        == claim
    )
    assert (
        PostgreSQLOperationalKnowledgeProtectedContentRepository._record_to_domain(raw_record)
        == grant.record
    )
    assert "content" not in raw_claim
    assert "content" not in raw_record
