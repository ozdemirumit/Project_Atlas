from __future__ import annotations

from dataclasses import asdict, replace
from datetime import UTC, datetime, timedelta

import pytest
from pydantic import ValidationError
from test_package_acquisition import CollectingAuditSink
from test_protected_model_invocation import create_invocation, invocation_fixture
from test_target_session import development_target_session_operator

from atlas.api.protected_draft_adjudication_schemas import (
    ProtectedDraftAdjudicationInput,
    ProtectedDraftAdjudicationResultData,
)
from atlas.modules.ai.adapters.protected_draft_adjudication_memory import (
    InMemoryProtectedDraftAdjudicationPolicySource,
    MemoryProtectedDraftAdjudicationRepository,
)
from atlas.modules.ai.adapters.protected_draft_adjudication_postgres import (
    PostgreSQLProtectedDraftAdjudicationRepository,
)
from atlas.modules.ai.adapters.protected_draft_adjudication_synthetic import (
    SyntheticTrustedProtectedDraftAdjudicator,
    UnavailableTrustedProtectedDraftAdjudicator,
)
from atlas.modules.ai.application.protected_draft_adjudication import (
    GovernedProtectedDraftAdjudicationService,
    build_development_protected_draft_adjudication_policy,
)
from atlas.modules.ai.application.protected_draft_adjudication_ports import (
    ProtectedDraftAdjudicationError,
)
from atlas.modules.ai.application.protected_model_invocation import (
    GovernedProtectedModelInvocationService,
)
from atlas.modules.ai.domain.protected_draft_adjudication import (
    ProtectedDraftAdjudicationPolicySnapshot,
    ProtectedDraftAdjudicationResult,
)
from atlas.modules.ai.domain.protected_model_invocation import ProtectedModelInvocationResult
from atlas.modules.identity.domain.models import AssuranceLevel, AuthenticatedSubject, SubjectKind


class RecordingAdjudicationPermissionAuthorizer:
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
            raise ProtectedDraftAdjudicationError("protected_draft_adjudication_permission_denied")


async def adjudication_fixture(
    *, deny: bool = False, unavailable: bool = False
) -> tuple[
    GovernedProtectedDraftAdjudicationService,
    MemoryProtectedDraftAdjudicationRepository,
    ProtectedModelInvocationResult,
    ProtectedDraftAdjudicationPolicySnapshot,
    AuthenticatedSubject,
    SyntheticTrustedProtectedDraftAdjudicator | UnavailableTrustedProtectedDraftAdjudicator,
    RecordingAdjudicationPermissionAuthorizer,
    CollectingAuditSink,
]:
    (
        invocation_service,
        _,
        context,
        invocation_policy,
        actor,
        _,
        _,
        audit,
    ) = await invocation_fixture()
    invocation = await create_invocation(invocation_service, context, invocation_policy, actor)
    policy = build_development_protected_draft_adjudication_policy(
        organization_id=invocation.record.organization_id,
        environment_id=invocation.record.environment_id,
        issued_at=invocation.record.invoked_at - timedelta(hours=1),
        expires_at=invocation.record.invoked_at + timedelta(days=1),
    )
    adjudicator = (
        UnavailableTrustedProtectedDraftAdjudicator()
        if unavailable
        else SyntheticTrustedProtectedDraftAdjudicator(clock=lambda: invocation.record.invoked_at)
    )
    permission = RecordingAdjudicationPermissionAuthorizer(deny=deny)
    repository = MemoryProtectedDraftAdjudicationRepository()
    service = GovernedProtectedDraftAdjudicationService(
        repository=repository,
        invocation_source=invocation_service,
        context_source=invocation_service._context_source,
        context_vault=invocation_service._context_vault,
        policy_source=InMemoryProtectedDraftAdjudicationPolicySource((policy,)),
        permission_authorizer=permission,
        adjudicator=adjudicator,
        audit_sink=audit,
        environment_id=invocation.record.environment_id,
        clock=lambda: invocation.record.invoked_at,
    )
    return service, repository, invocation, policy, actor, adjudicator, permission, audit


async def create_adjudication(
    service: GovernedProtectedDraftAdjudicationService,
    invocation: ProtectedModelInvocationResult,
    policy: ProtectedDraftAdjudicationPolicySnapshot,
    actor: AuthenticatedSubject,
) -> ProtectedDraftAdjudicationResult:
    return await service.create(
        actor=actor,
        invocation_id=invocation.record.invocation_id,
        invocation_digest=invocation.record.canonical_digest,
        adjudication_policy_id=policy.policy_id,
        adjudication_policy_digest=policy.canonical_digest,
        purpose=invocation.record.purpose,
        draft_untrusted_acknowledged=True,
        no_content_presentation_acknowledged=True,
        no_answer_or_operational_authority_acknowledged=True,
        browser_session_id="session_protected_knowledge_retrieval_001",
        idempotency_key="protected-draft-adjudication-001",
        correlation_id="cor_protected_draft_adjudication",
    )


def _signed_adjudication_policy(
    service: GovernedProtectedDraftAdjudicationService,
    policy: ProtectedDraftAdjudicationPolicySnapshot,
    required_assurance_level: AssuranceLevel,
) -> ProtectedDraftAdjudicationPolicySnapshot:
    updated = replace(
        policy,
        required_assurance_level=required_assurance_level,
        canonical_digest="0" * 64,
    )
    return replace(
        updated,
        canonical_digest=service._digest(service._payload(updated)),
    )


def test_adjudication_policy_supports_governed_assurance_levels() -> None:
    now = datetime.now(UTC)
    policy = build_development_protected_draft_adjudication_policy(
        organization_id="org.atlas",
        environment_id="environment.development",
        issued_at=now,
        expires_at=now + timedelta(hours=1),
    )
    assert policy.required_assurance_level is AssuranceLevel.SINGLE_FACTOR
    for level in (
        AssuranceLevel.SINGLE_FACTOR,
        AssuranceLevel.MULTI_FACTOR,
        AssuranceLevel.HARDWARE_BACKED,
    ):
        assert replace(policy, required_assurance_level=level).required_assurance_level is level


@pytest.mark.asyncio
async def test_adjudication_requires_step_up_only_when_signed_policy_requests_it() -> None:
    (
        service,
        repository,
        invocation,
        policy,
        actor,
        adjudicator,
        permission,
        audit,
    ) = await adjudication_fixture()
    stronger = _signed_adjudication_policy(service, policy, AssuranceLevel.MULTI_FACTOR)
    service = GovernedProtectedDraftAdjudicationService(
        repository=repository,
        invocation_source=service._invocation_source,
        context_source=service._context_source,
        context_vault=service._context_vault,
        policy_source=InMemoryProtectedDraftAdjudicationPolicySource((stronger,)),
        permission_authorizer=permission,
        adjudicator=adjudicator,
        audit_sink=audit,
        environment_id=invocation.record.environment_id,
        clock=lambda: invocation.record.invoked_at,
    )
    actor = development_target_session_operator(actor.subject_id)
    with pytest.raises(ProtectedDraftAdjudicationError, match="policy_assurance_required"):
        await create_adjudication(service, invocation, stronger, actor)


@pytest.mark.asyncio
async def test_adjudication_rejects_non_human_actor() -> None:
    service, _, invocation, policy, actor, *_ = await adjudication_fixture()
    with pytest.raises(ProtectedDraftAdjudicationError, match="human_required"):
        await create_adjudication(
            service,
            invocation,
            policy,
            replace(actor, kind=SubjectKind.SERVICE),
        )


@pytest.mark.asyncio
async def test_adjudication_is_private_deterministic_and_idempotent() -> None:
    service, _, invocation, policy, actor, adjudicator, permission, _ = await adjudication_fixture()
    result = await create_adjudication(service, invocation, policy, actor)
    repeated = await create_adjudication(service, invocation, policy, actor)
    replay = await service.get(
        actor=actor,
        adjudication_id=result.record.adjudication_id,
        browser_session_id="session_protected_knowledge_retrieval_001",
        correlation_id="cor_protected_draft_adjudication_read",
    )
    assert result.record.outcome == "adjudication-outcome.eligible"
    assert result.record.model_draft_adjudicated and not result.record.answer_generated
    assert repeated.record.reused and replay.record.reused
    assert isinstance(adjudicator, SyntheticTrustedProtectedDraftAdjudicator)
    assert len(adjudicator.calls) == 1
    assert len(permission.calls) == 3
    persisted = GovernedProtectedModelInvocationService._normalize(asdict(result.record))
    assert isinstance(persisted, dict)
    restored = PostgreSQLProtectedDraftAdjudicationRepository._record_to_domain(persisted)
    assert restored == result.record
    response = ProtectedDraftAdjudicationResultData.from_domain(result).model_dump()
    for private in (
        "claim_id",
        "consumer_subject_digest",
        "browser_session_binding_digest",
        "adjudication_authorization_digest",
        "protected_report_reference",
        "protected_report_digest",
    ):
        assert private not in response["adjudication"]


@pytest.mark.asyncio
async def test_adjudication_denial_precedes_claim() -> None:
    service, repository, invocation, policy, actor, adjudicator, *_ = await adjudication_fixture(
        deny=True
    )
    with pytest.raises(ProtectedDraftAdjudicationError, match="permission_denied"):
        await create_adjudication(service, invocation, policy, actor)
    assert not repository._claims
    assert isinstance(adjudicator, SyntheticTrustedProtectedDraftAdjudicator)
    assert not adjudicator.calls


@pytest.mark.asyncio
async def test_adjudication_production_boundary_fails_closed() -> None:
    service, repository, invocation, policy, actor, adjudicator, *_ = await adjudication_fixture(
        unavailable=True
    )
    with pytest.raises(ProtectedDraftAdjudicationError, match="adjudicator_unavailable"):
        await create_adjudication(service, invocation, policy, actor)
    assert repository._claims and not repository._records
    assert isinstance(adjudicator, UnavailableTrustedProtectedDraftAdjudicator)


def test_adjudication_input_is_strict() -> None:
    with pytest.raises(ValidationError):
        ProtectedDraftAdjudicationInput.model_validate(
            {
                "invocation_digest": "a" * 64,
                "adjudication_policy_id": "protected-draft-adjudication-policy.development",
                "adjudication_policy_digest": "b" * 64,
                "purpose": "Analyze approved evidence for a read-only investigation.",
                "acknowledged_draft_is_untrusted": True,
                "acknowledged_no_content_presentation": True,
                "acknowledged_no_answer_or_operational_authority": True,
                "draft": "caller-supplied draft",
            }
        )
