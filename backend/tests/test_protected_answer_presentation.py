from __future__ import annotations

from dataclasses import asdict
from datetime import timedelta

import pytest
from pydantic import ValidationError
from test_protected_draft_adjudication import adjudication_fixture, create_adjudication

from atlas.api.protected_answer_presentation_schemas import (
    ProtectedAnswerPresentationInput,
    ProtectedAnswerPresentationResultData,
)
from atlas.modules.ai.adapters.protected_answer_presentation_memory import (
    InMemoryProtectedAnswerPresentationPolicySource,
    MemoryProtectedAnswerPresentationRepository,
)
from atlas.modules.ai.adapters.protected_answer_presentation_postgres import (
    PostgreSQLProtectedAnswerPresentationRepository,
)
from atlas.modules.ai.adapters.protected_answer_presentation_synthetic import (
    SyntheticTrustedProtectedAnswerPresenter,
    UnavailableTrustedProtectedAnswerPresenter,
)
from atlas.modules.ai.application.protected_answer_presentation import (
    GovernedProtectedAnswerPresentationService,
    build_development_protected_answer_presentation_policy,
)
from atlas.modules.ai.application.protected_answer_presentation_ports import (
    ProtectedAnswerPresentationError,
)
from atlas.modules.ai.application.protected_model_invocation import (
    GovernedProtectedModelInvocationService,
)
from atlas.modules.ai.domain.protected_answer_presentation import (
    ProtectedAnswerPresentationPolicySnapshot,
    ProtectedAnswerPresentationResult,
)
from atlas.modules.ai.domain.protected_draft_adjudication import (
    ProtectedDraftAdjudicationResult,
)
from atlas.modules.identity.domain.models import AuthenticatedSubject


class RecordingPresentationPermissionAuthorizer:
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
            raise ProtectedAnswerPresentationError(
                "protected_answer_presentation_permission_denied"
            )


async def presentation_fixture(
    *, deny: bool = False, unavailable: bool = False
) -> tuple[
    GovernedProtectedAnswerPresentationService,
    MemoryProtectedAnswerPresentationRepository,
    ProtectedDraftAdjudicationResult,
    ProtectedAnswerPresentationPolicySnapshot,
    AuthenticatedSubject,
    SyntheticTrustedProtectedAnswerPresenter | UnavailableTrustedProtectedAnswerPresenter,
    RecordingPresentationPermissionAuthorizer,
]:
    (
        adjudication_service,
        _,
        invocation,
        adjudication_policy,
        actor,
        *_,
    ) = await adjudication_fixture()
    adjudication = await create_adjudication(
        adjudication_service, invocation, adjudication_policy, actor
    )
    policy = build_development_protected_answer_presentation_policy(
        organization_id=adjudication.record.organization_id,
        environment_id=adjudication.record.environment_id,
        issued_at=adjudication.record.adjudicated_at - timedelta(hours=1),
        expires_at=adjudication.record.adjudicated_at + timedelta(days=1),
    )
    presenter = (
        UnavailableTrustedProtectedAnswerPresenter()
        if unavailable
        else SyntheticTrustedProtectedAnswerPresenter()
    )
    permission = RecordingPresentationPermissionAuthorizer(deny=deny)
    repository = MemoryProtectedAnswerPresentationRepository()
    service = GovernedProtectedAnswerPresentationService(
        repository=repository,
        adjudication_source=adjudication_service,
        policy_source=InMemoryProtectedAnswerPresentationPolicySource((policy,)),
        permission_authorizer=permission,
        presenter=presenter,
        audit_sink=adjudication_service._audit_sink,
        environment_id=adjudication.record.environment_id,
        clock=lambda: adjudication.record.adjudicated_at,
    )
    return service, repository, adjudication, policy, actor, presenter, permission


async def create_presentation(
    service: GovernedProtectedAnswerPresentationService,
    adjudication: ProtectedDraftAdjudicationResult,
    policy: ProtectedAnswerPresentationPolicySnapshot,
    actor: AuthenticatedSubject,
) -> ProtectedAnswerPresentationResult:
    return await service.create(
        actor=actor,
        adjudication_id=adjudication.record.adjudication_id,
        adjudication_digest=adjudication.record.canonical_digest,
        presentation_policy_id=policy.policy_id,
        presentation_policy_digest=policy.canonical_digest,
        purpose=adjudication.record.purpose,
        decision_support_acknowledged=True,
        citations_and_unknowns_acknowledged=True,
        no_recommendation_or_operational_authority_acknowledged=True,
        browser_session_id="session_protected_knowledge_retrieval_001",
        idempotency_key="protected-answer-presentation-001",
        correlation_id="cor_protected_answer_presentation",
    )


@pytest.mark.asyncio
async def test_presentation_is_bounded_private_and_idempotent() -> None:
    service, _, adjudication, policy, actor, presenter, permission = await presentation_fixture()
    result = await create_presentation(service, adjudication, policy, actor)
    repeated = await create_presentation(service, adjudication, policy, actor)
    replay = await service.get(
        actor=actor,
        presentation_id=result.record.presentation_id,
        browser_session_id="session_protected_knowledge_retrieval_001",
        correlation_id="cor_protected_answer_presentation_read",
    )
    assert result.answer.summary
    assert result.answer.citation_references and result.answer.unknowns
    assert result.record.answer_presented and not result.record.recommendation_generated
    assert repeated.record.reused and replay.record.reused
    assert repeated.answer == replay.answer == result.answer
    assert isinstance(presenter, SyntheticTrustedProtectedAnswerPresenter)
    assert len(permission.calls) == 3
    persisted = GovernedProtectedModelInvocationService._normalize(asdict(result.record))
    assert isinstance(persisted, dict)
    for private in ("summary", "citation_references", "unknowns"):
        assert private not in persisted
    restored = PostgreSQLProtectedAnswerPresentationRepository._record_to_domain(persisted)
    assert restored == result.record
    response = ProtectedAnswerPresentationResultData.from_domain(result).model_dump()
    assert response["answer"]["summary"] == result.answer.summary
    for private in (
        "claim_id",
        "consumer_subject_digest",
        "browser_session_binding_digest",
        "presentation_authorization_digest",
        "context_package_digest",
    ):
        assert private not in response["presentation"]


@pytest.mark.asyncio
async def test_presentation_denial_precedes_claim() -> None:
    service, repository, adjudication, policy, actor, presenter, _ = await presentation_fixture(
        deny=True
    )
    with pytest.raises(ProtectedAnswerPresentationError, match="permission_denied"):
        await create_presentation(service, adjudication, policy, actor)
    assert not repository._claims
    assert isinstance(presenter, SyntheticTrustedProtectedAnswerPresenter)
    assert not presenter.calls


@pytest.mark.asyncio
async def test_presentation_production_boundary_fails_closed() -> None:
    service, repository, adjudication, policy, actor, presenter, _ = await presentation_fixture(
        unavailable=True
    )
    with pytest.raises(ProtectedAnswerPresentationError, match="presenter_unavailable"):
        await create_presentation(service, adjudication, policy, actor)
    assert repository._claims and not repository._records
    assert isinstance(presenter, UnavailableTrustedProtectedAnswerPresenter)


def test_presentation_input_is_strict() -> None:
    with pytest.raises(ValidationError):
        ProtectedAnswerPresentationInput.model_validate(
            {
                "adjudication_digest": "a" * 64,
                "presentation_policy_id": "protected-answer-presentation-policy.development",
                "presentation_policy_digest": "b" * 64,
                "purpose": "Analyze approved evidence for a read-only investigation.",
                "acknowledged_bounded_decision_support": True,
                "acknowledged_citations_and_unknowns_are_material": True,
                "acknowledged_no_recommendation_or_operational_authority": True,
                "summary": "caller-supplied answer",
            }
        )
