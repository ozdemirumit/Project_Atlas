from __future__ import annotations

from dataclasses import asdict, replace
from datetime import UTC, datetime, timedelta

import pytest
from pydantic import ValidationError
from test_protected_answer_presentation import create_presentation, presentation_fixture

from atlas.api.protected_recommendation_candidate_schemas import (
    ProtectedRecommendationCandidateInput,
    ProtectedRecommendationCandidateResultData,
)
from atlas.modules.ai.adapters.protected_recommendation_candidate_memory import (
    InMemoryProtectedRecommendationCandidatePolicySource,
    MemoryProtectedRecommendationCandidateRepository,
)
from atlas.modules.ai.adapters.protected_recommendation_candidate_postgres import (
    PostgreSQLProtectedRecommendationCandidateRepository,
)
from atlas.modules.ai.adapters.protected_recommendation_candidate_synthetic import (
    SyntheticTrustedProtectedRecommendationCandidateGenerator,
    UnavailableTrustedProtectedRecommendationCandidateGenerator,
)
from atlas.modules.ai.application.protected_model_invocation import (
    GovernedProtectedModelInvocationService,
)
from atlas.modules.ai.application.protected_recommendation_candidate_generation import (
    GovernedProtectedRecommendationCandidateService,
    build_development_protected_recommendation_candidate_policy,
)
from atlas.modules.ai.application.protected_recommendation_candidate_generation_ports import (
    ProtectedRecommendationCandidateError,
)
from atlas.modules.ai.domain.protected_answer_presentation import (
    ProtectedAnswerPresentationResult,
)
from atlas.modules.ai.domain.protected_recommendation_candidate_generation import (
    ProtectedRecommendationCandidatePolicySnapshot,
    ProtectedRecommendationCandidateResult,
)
from atlas.modules.identity.domain.models import (
    AssuranceLevel,
    AuthenticatedSubject,
    AuthenticationMethod,
    SubjectKind,
)


class RecordingCandidatePermissionAuthorizer:
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
            raise ProtectedRecommendationCandidateError(
                "protected_recommendation_candidate_permission_denied"
            )


async def candidate_fixture(
    *,
    deny: bool = False,
    unavailable: bool = False,
    required_assurance_level: AssuranceLevel = AssuranceLevel.SINGLE_FACTOR,
) -> tuple[
    GovernedProtectedRecommendationCandidateService,
    MemoryProtectedRecommendationCandidateRepository,
    ProtectedAnswerPresentationResult,
    ProtectedRecommendationCandidatePolicySnapshot,
    AuthenticatedSubject,
    SyntheticTrustedProtectedRecommendationCandidateGenerator
    | UnavailableTrustedProtectedRecommendationCandidateGenerator,
    RecordingCandidatePermissionAuthorizer,
]:
    (
        presentation_service,
        _,
        adjudication,
        presentation_policy,
        actor,
        *_,
    ) = await presentation_fixture()
    presentation = await create_presentation(
        presentation_service, adjudication, presentation_policy, actor
    )
    policy = build_development_protected_recommendation_candidate_policy(
        organization_id=presentation.record.organization_id,
        environment_id=presentation.record.environment_id,
        issued_at=presentation.record.presented_at - timedelta(hours=1),
        expires_at=presentation.record.presented_at + timedelta(days=1),
    )
    policy = replace(policy, required_assurance_level=required_assurance_level)
    policy = replace(
        policy,
        canonical_digest=GovernedProtectedModelInvocationService._digest(
            GovernedProtectedModelInvocationService._payload(policy)
        ),
    )
    generator = (
        UnavailableTrustedProtectedRecommendationCandidateGenerator()
        if unavailable
        else SyntheticTrustedProtectedRecommendationCandidateGenerator()
    )
    permission = RecordingCandidatePermissionAuthorizer(deny=deny)
    repository = MemoryProtectedRecommendationCandidateRepository()
    service = GovernedProtectedRecommendationCandidateService(
        repository=repository,
        presentation_source=presentation_service,
        policy_source=InMemoryProtectedRecommendationCandidatePolicySource((policy,)),
        permission_authorizer=permission,
        generator=generator,
        audit_sink=presentation_service._audit_sink,
        environment_id=presentation.record.environment_id,
        clock=lambda: presentation.record.presented_at,
    )
    return service, repository, presentation, policy, actor, generator, permission


async def create_candidates(
    service: GovernedProtectedRecommendationCandidateService,
    presentation: ProtectedAnswerPresentationResult,
    policy: ProtectedRecommendationCandidatePolicySnapshot,
    actor: AuthenticatedSubject,
) -> ProtectedRecommendationCandidateResult:
    return await service.create(
        actor=actor,
        presentation_id=presentation.record.presentation_id,
        presentation_digest=presentation.record.canonical_digest,
        generation_policy_id=policy.policy_id,
        generation_policy_digest=policy.canonical_digest,
        purpose=presentation.record.purpose,
        incomplete_candidates_acknowledged=True,
        impact_and_recovery_unverified_acknowledged=True,
        no_recommendation_or_operational_authority_acknowledged=True,
        browser_session_id="session_protected_knowledge_retrieval_001",
        idempotency_key="protected-recommendation-candidate-001",
        correlation_id="cor_protected_recommendation_candidate",
    )


@pytest.mark.asyncio
async def test_candidate_set_is_private_bounded_and_idempotent() -> None:
    service, _, presentation, policy, actor, generator, permission = await candidate_fixture()
    result = await create_candidates(service, presentation, policy, actor)
    repeated = await create_candidates(service, presentation, policy, actor)
    replay = await service.get(
        actor=actor,
        candidate_set_id=result.record.candidate_set_id,
        browser_session_id="session_protected_knowledge_retrieval_001",
        correlation_id="cor_protected_recommendation_candidate_read",
    )

    assert result.record.candidate_count == 3
    assert result.record.candidate_categories == policy.required_categories
    assert result.record.recommendation_candidates_generated
    assert not result.record.recommendation_complete
    assert not result.record.recommendation_presented
    assert not result.record.execution_authorized
    assert repeated.record.reused and replay.record.reused
    assert isinstance(generator, SyntheticTrustedProtectedRecommendationCandidateGenerator)
    assert len(generator.calls) == 1
    assert len(permission.calls) == 3


@pytest.mark.asyncio
async def test_default_policy_allows_development_authentication() -> None:
    service, _, presentation, policy, actor, *_ = await candidate_fixture()
    development_actor = replace(
        actor,
        authentication_method=AuthenticationMethod.DEVELOPMENT,
        assurance_level=AssuranceLevel.DEVELOPMENT,
    )

    result = await create_candidates(service, presentation, policy, development_actor)

    assert result.record.recommendation_candidates_generated
    assert policy.required_assurance_level is AssuranceLevel.SINGLE_FACTOR


@pytest.mark.asyncio
async def test_explicit_stronger_policy_rejects_development_authentication() -> None:
    service, _, presentation, policy, actor, *_ = await candidate_fixture(
        required_assurance_level=AssuranceLevel.MULTI_FACTOR
    )
    development_actor = replace(
        actor,
        authentication_method=AuthenticationMethod.DEVELOPMENT,
        assurance_level=AssuranceLevel.DEVELOPMENT,
    )

    with pytest.raises(ProtectedRecommendationCandidateError, match="assurance_required"):
        await create_candidates(service, presentation, policy, development_actor)


@pytest.mark.asyncio
async def test_non_human_actor_is_rejected() -> None:
    service, _, presentation, policy, actor, *_ = await candidate_fixture()

    with pytest.raises(ProtectedRecommendationCandidateError, match="human_required"):
        await create_candidates(
            service,
            presentation,
            policy,
            replace(actor, kind=SubjectKind.SERVICE),
        )


def test_policy_accepts_only_supported_assurance_levels() -> None:
    issued_at = datetime(2026, 1, 1, tzinfo=UTC)
    policy = build_development_protected_recommendation_candidate_policy(
        organization_id="organization.test",
        environment_id="environment.test",
        issued_at=issued_at,
        expires_at=issued_at + timedelta(days=1),
    )

    for level in (
        AssuranceLevel.SINGLE_FACTOR,
        AssuranceLevel.MULTI_FACTOR,
        AssuranceLevel.HARDWARE_BACKED,
    ):
        assert replace(policy, required_assurance_level=level).required_assurance_level is level
    with pytest.raises(ValueError, match="policy is invalid"):
        replace(policy, required_assurance_level=AssuranceLevel.DEVELOPMENT)


@pytest.mark.asyncio
async def test_persisted_record_excludes_candidate_content() -> None:
    service, _, presentation, policy, actor, generator, _ = await candidate_fixture()
    result = await create_candidates(service, presentation, policy, actor)
    persisted = GovernedProtectedModelInvocationService._normalize(asdict(result.record))
    assert isinstance(persisted, dict)
    serialized = str(persisted).lower()
    assert "repeat the approved" not in serialized
    assert "prepare an evidence-bound" not in serialized
    assert "conceptual_action" not in serialized
    assert "assumptions" not in serialized
    assert "evidence_gaps" not in serialized
    assert isinstance(generator, SyntheticTrustedProtectedRecommendationCandidateGenerator)
    assert result.record.candidate_set_id in generator._vault


@pytest.mark.asyncio
async def test_postgres_record_round_trip_is_metadata_only() -> None:
    service, _, presentation, policy, actor, *_ = await candidate_fixture()
    result = await create_candidates(service, presentation, policy, actor)
    payload = GovernedProtectedModelInvocationService._normalize(asdict(result.record))
    assert isinstance(payload, dict)
    restored = PostgreSQLProtectedRecommendationCandidateRepository._record_to_domain(payload)
    assert restored == result.record


@pytest.mark.asyncio
async def test_api_result_hides_private_bindings_and_candidate_content() -> None:
    service, _, presentation, policy, actor, *_ = await candidate_fixture()
    result = await create_candidates(service, presentation, policy, actor)
    response = ProtectedRecommendationCandidateResultData.from_domain(result).model_dump()
    candidate_set = response["candidate_set"]
    for private in (
        "claim_id",
        "consumer_subject_digest",
        "browser_session_binding_digest",
        "generation_authorization_digest",
        "context_package_digest",
        "title",
        "steps",
        "assumptions",
        "unknowns",
    ):
        assert private not in candidate_set
    assert candidate_set["candidate_count"] == 3
    assert candidate_set["recommendation_candidates_generated"] is True
    assert candidate_set["service_impact_analyzed"] is False


@pytest.mark.asyncio
async def test_permission_denial_happens_before_claim_and_source_rehydration() -> None:
    (
        service,
        repository,
        presentation,
        policy,
        actor,
        generator,
        permission,
    ) = await candidate_fixture(deny=True)
    with pytest.raises(
        ProtectedRecommendationCandidateError,
        match="protected_recommendation_candidate_permission_denied",
    ):
        await create_candidates(service, presentation, policy, actor)
    assert permission.calls
    assert not repository._claims
    assert isinstance(generator, SyntheticTrustedProtectedRecommendationCandidateGenerator)
    assert not generator.calls


@pytest.mark.asyncio
async def test_unavailable_production_boundary_leaves_claim_without_record() -> None:
    service, repository, presentation, policy, actor, generator, _ = await candidate_fixture(
        unavailable=True
    )
    with pytest.raises(
        ProtectedRecommendationCandidateError,
        match="protected_recommendation_candidate_generator_unavailable",
    ):
        await create_candidates(service, presentation, policy, actor)
    assert repository._claims
    assert not repository._records
    assert isinstance(generator, UnavailableTrustedProtectedRecommendationCandidateGenerator)


@pytest.mark.asyncio
async def test_wrong_browser_binding_is_hidden() -> None:
    service, _, presentation, policy, actor, *_ = await candidate_fixture()
    result = await create_candidates(service, presentation, policy, actor)
    with pytest.raises(
        ProtectedRecommendationCandidateError,
        match="protected_recommendation_candidate_not_found",
    ):
        await service.get(
            actor=actor,
            candidate_set_id=result.record.candidate_set_id,
            browser_session_id="session_wrong_browser_binding_001",
            correlation_id="cor_protected_recommendation_candidate_wrong_browser",
        )


def test_input_schema_forbids_caller_shaped_candidates() -> None:
    payload = {
        "presentation_digest": "a" * 64,
        "generation_policy_id": "protected-recommendation-candidate-policy.development",
        "generation_policy_digest": "b" * 64,
        "purpose": "Generate bounded candidates from exact evidence.",
        "acknowledged_candidates_are_incomplete": True,
        "acknowledged_impact_and_recovery_are_unverified": True,
        "acknowledged_no_recommendation_or_operational_authority": True,
        "candidates": [{"title": "caller controlled"}],
    }
    with pytest.raises(ValidationError):
        ProtectedRecommendationCandidateInput.model_validate(payload)
