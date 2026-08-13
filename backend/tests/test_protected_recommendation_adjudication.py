from __future__ import annotations

from dataclasses import asdict, replace
from datetime import UTC, datetime, timedelta

import pytest
from pydantic import ValidationError
from test_protected_candidate_risk_recovery import completion_fixture, create_completion

from atlas.api.protected_recommendation_adjudication_schemas import (
    ProtectedRecommendationAdjudicationInput,
    ProtectedRecommendationAdjudicationResultData,
)
from atlas.modules.ai.adapters.protected_recommendation_adjudication_memory import (
    InMemoryProtectedRecommendationAdjudicationPolicySource,
    MemoryProtectedRecommendationAdjudicationRepository,
)
from atlas.modules.ai.adapters.protected_recommendation_adjudication_postgres import (
    PostgreSQLProtectedRecommendationAdjudicationRepository,
)
from atlas.modules.ai.adapters.protected_recommendation_adjudication_synthetic import (
    SyntheticTrustedProtectedRecommendationAdjudicator,
    UnavailableTrustedProtectedRecommendationAdjudicator,
)
from atlas.modules.ai.application.protected_model_invocation import (
    GovernedProtectedModelInvocationService,
)
from atlas.modules.ai.application.protected_recommendation_adjudication import (
    GovernedProtectedRecommendationAdjudicationService,
    build_development_protected_recommendation_adjudication_policy,
)
from atlas.modules.ai.application.protected_recommendation_adjudication_ports import (
    ProtectedRecommendationAdjudicationError,
)
from atlas.modules.ai.domain.protected_candidate_risk_recovery_completion import (
    ProtectedCandidateRiskRecoveryResult,
)
from atlas.modules.ai.domain.protected_recommendation_adjudication import (
    ProtectedRecommendationAdjudicationPolicySnapshot,
    ProtectedRecommendationAdjudicationResult,
)
from atlas.modules.identity.domain.models import (
    AssuranceLevel,
    AuthenticatedSubject,
    AuthenticationMethod,
    SubjectKind,
)

BROWSER_SESSION_ID = "session_protected_knowledge_retrieval_001"


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
            raise ProtectedRecommendationAdjudicationError(
                "protected_recommendation_adjudication_permission_denied"
            )


async def adjudication_fixture(
    *,
    deny: bool = False,
    unavailable: bool = False,
    required_assurance_level: AssuranceLevel = AssuranceLevel.SINGLE_FACTOR,
) -> tuple[
    GovernedProtectedRecommendationAdjudicationService,
    MemoryProtectedRecommendationAdjudicationRepository,
    ProtectedCandidateRiskRecoveryResult,
    ProtectedRecommendationAdjudicationPolicySnapshot,
    AuthenticatedSubject,
    SyntheticTrustedProtectedRecommendationAdjudicator
    | UnavailableTrustedProtectedRecommendationAdjudicator,
    RecordingAdjudicationPermissionAuthorizer,
]:
    completion_service, _, impact, completion_policy, actor, *_ = await completion_fixture()
    completion = await create_completion(
        completion_service,
        impact,
        completion_policy,
        actor,
    )
    policy = build_development_protected_recommendation_adjudication_policy(
        organization_id=completion.record.organization_id,
        environment_id=completion.record.environment_id,
        issued_at=completion.record.completed_at - timedelta(hours=1),
        expires_at=completion.record.completed_at + timedelta(days=1),
    )
    unsigned_policy = replace(
        policy,
        required_assurance_level=required_assurance_level,
        canonical_digest="0" * 64,
    )
    policy = replace(
        unsigned_policy,
        canonical_digest=GovernedProtectedModelInvocationService._digest(
            GovernedProtectedModelInvocationService._payload(unsigned_policy)
        ),
    )
    adjudicator = (
        UnavailableTrustedProtectedRecommendationAdjudicator()
        if unavailable
        else SyntheticTrustedProtectedRecommendationAdjudicator()
    )
    permission = RecordingAdjudicationPermissionAuthorizer(deny=deny)
    repository = MemoryProtectedRecommendationAdjudicationRepository()
    service = GovernedProtectedRecommendationAdjudicationService(
        repository=repository,
        completion_source=completion_service,
        policy_source=InMemoryProtectedRecommendationAdjudicationPolicySource((policy,)),
        permission_authorizer=permission,
        adjudicator=adjudicator,
        audit_sink=completion_service._audit_sink,
        environment_id=completion.record.environment_id,
        clock=lambda: completion.record.completed_at,
    )
    return service, repository, completion, policy, actor, adjudicator, permission


async def create_adjudication(
    service: GovernedProtectedRecommendationAdjudicationService,
    completion: ProtectedCandidateRiskRecoveryResult,
    policy: ProtectedRecommendationAdjudicationPolicySnapshot,
    actor: AuthenticatedSubject,
) -> ProtectedRecommendationAdjudicationResult:
    return await service.create(
        actor=actor,
        completion_id=completion.record.completion_id,
        completion_digest=completion.record.canonical_digest,
        adjudication_policy_id=policy.policy_id,
        adjudication_policy_digest=policy.canonical_digest,
        purpose=completion.record.purpose,
        preference_not_approval_acknowledged=True,
        tie_or_no_support_acknowledged=True,
        no_presentation_or_operational_authority_acknowledged=True,
        browser_session_id=BROWSER_SESSION_ID,
        idempotency_key="protected-recommendation-adjudication-001",
        correlation_id="cor_protected_recommendation_adjudication",
    )


@pytest.mark.asyncio
async def test_adjudication_is_private_bounded_and_idempotent() -> None:
    service, _, completion, policy, actor, adjudicator, permission = await adjudication_fixture()
    result = await create_adjudication(service, completion, policy, actor)
    repeated = await create_adjudication(service, completion, policy, actor)
    replay = await service.get(
        actor=actor,
        adjudication_id=result.record.adjudication_id,
        browser_session_id=BROWSER_SESSION_ID,
        correlation_id="cor_protected_recommendation_adjudication_read",
    )

    assert result.record.candidate_count == 3
    assert result.record.dimension_count == 9
    assert result.record.eligible_count == 3
    assert result.record.excluded_count == 0
    assert result.record.preferred_count == 1
    assert result.record.alternative_count == 2
    assert not result.record.tie
    assert not result.record.no_supportable_candidate
    assert result.record.maximum_risk == "moderate"
    assert result.record.interruption_possible_count == 0
    assert result.record.recovery_feasible_count == 3
    assert result.record.recommendation_complete
    assert not result.record.recommendation_presented
    assert not result.record.recommendation_ready_for_review
    assert not result.record.recommendation_approved
    assert not result.record.workflow_created
    assert not result.record.execution_authorized
    assert not result.record.deployment_authorized
    assert not result.record.infrastructure_mutated
    assert repeated.record.reused and replay.record.reused
    assert isinstance(adjudicator, SyntheticTrustedProtectedRecommendationAdjudicator)
    assert len(adjudicator.calls) == 1
    assert len(permission.calls) == 4


@pytest.mark.asyncio
async def test_development_human_satisfies_default_adjudication_policy() -> None:
    service, _, completion, policy, actor, *_ = await adjudication_fixture()
    development_actor = replace(
        actor,
        authentication_method=AuthenticationMethod.DEVELOPMENT,
        assurance_level=AssuranceLevel.DEVELOPMENT,
    )

    result = await create_adjudication(service, completion, policy, development_actor)

    assert result.record.adjudication_policy_digest == policy.canonical_digest


@pytest.mark.asyncio
async def test_explicit_stronger_adjudication_policy_rejects_development_assurance() -> None:
    service, repository, completion, policy, actor, *_, permission = await adjudication_fixture(
        required_assurance_level=AssuranceLevel.HARDWARE_BACKED
    )
    development_actor = replace(
        actor,
        authentication_method=AuthenticationMethod.DEVELOPMENT,
        assurance_level=AssuranceLevel.DEVELOPMENT,
    )

    with pytest.raises(
        ProtectedRecommendationAdjudicationError,
        match="protected_recommendation_adjudication_assurance_required",
    ):
        await create_adjudication(service, completion, policy, development_actor)

    assert not permission.calls
    assert not repository._claims


@pytest.mark.asyncio
async def test_adjudication_rejects_non_human_subject() -> None:
    service, repository, completion, policy, actor, *_ = await adjudication_fixture()
    service_actor = replace(actor, kind=SubjectKind.SERVICE)

    with pytest.raises(
        ProtectedRecommendationAdjudicationError,
        match="protected_recommendation_adjudication_human_required",
    ):
        await create_adjudication(service, completion, policy, service_actor)

    assert not repository._claims


@pytest.mark.parametrize(
    "required_assurance_level",
    (
        AssuranceLevel.SINGLE_FACTOR,
        AssuranceLevel.MULTI_FACTOR,
        AssuranceLevel.HARDWARE_BACKED,
    ),
)
def test_adjudication_policy_supports_explicit_assurance_levels(
    required_assurance_level: AssuranceLevel,
) -> None:
    issued_at = datetime.now(UTC)
    base_policy = build_development_protected_recommendation_adjudication_policy(
        organization_id="org.atlas",
        environment_id="env.lab",
        issued_at=issued_at,
        expires_at=issued_at + timedelta(hours=1),
    )
    unsigned_policy = replace(
        base_policy,
        required_assurance_level=required_assurance_level,
        canonical_digest="0" * 64,
    )
    policy = replace(
        unsigned_policy,
        canonical_digest=GovernedProtectedModelInvocationService._digest(
            GovernedProtectedModelInvocationService._payload(unsigned_policy)
        ),
    )

    assert policy.required_assurance_level is required_assurance_level
    assert policy.canonical_digest == GovernedProtectedModelInvocationService._digest(
        GovernedProtectedModelInvocationService._payload(policy)
    )


@pytest.mark.asyncio
async def test_persisted_adjudication_excludes_candidate_specific_content() -> None:
    service, _, completion, policy, actor, adjudicator, _ = await adjudication_fixture()
    result = await create_adjudication(service, completion, policy, actor)
    persisted = GovernedProtectedModelInvocationService._normalize(asdict(result.record))
    assert isinstance(persisted, dict)
    serialized = str(persisted).lower()
    for private in (
        "repeat the approved read-only health observation",
        "recommendation-category.investigate",
        "candidate-1",
        "policy-eligibility",
        "preference_rationale",
        "exclusion_reasons",
    ):
        assert private not in serialized
    assert isinstance(adjudicator, SyntheticTrustedProtectedRecommendationAdjudicator)
    assert result.record.adjudication_id in adjudicator._vault


@pytest.mark.asyncio
async def test_postgres_adjudication_record_round_trip_is_metadata_only() -> None:
    service, _, completion, policy, actor, *_ = await adjudication_fixture()
    result = await create_adjudication(service, completion, policy, actor)
    payload = GovernedProtectedModelInvocationService._normalize(asdict(result.record))
    assert isinstance(payload, dict)
    restored = PostgreSQLProtectedRecommendationAdjudicationRepository._record_to_domain(payload)
    assert restored == result.record


@pytest.mark.asyncio
async def test_api_result_hides_protected_comparison_content_and_bindings() -> None:
    service, _, completion, policy, actor, *_ = await adjudication_fixture()
    result = await create_adjudication(service, completion, policy, actor)
    response = ProtectedRecommendationAdjudicationResultData.from_domain(result).model_dump()
    record = response["adjudication"]
    manifest = response["manifest"]
    for private in (
        "claim_id",
        "consumer_subject_digest",
        "browser_session_binding_digest",
        "adjudication_authorization_digest",
        "protected_report_digest",
        "candidate_entries",
        "candidate_id",
        "preferred_candidate_id",
        "category",
        "dimensions",
        "comparison_values",
        "exclusion_reasons",
        "preference_rationale",
    ):
        assert private not in record
        assert private not in manifest
    assert record["recommendation_complete"] is True
    assert record["recommendation_presented"] is False
    assert manifest["preferred_count"] == 1


@pytest.mark.asyncio
async def test_permission_denial_precedes_claim_and_source_rehydration() -> None:
    (
        service,
        repository,
        completion,
        policy,
        actor,
        adjudicator,
        permission,
    ) = await adjudication_fixture(deny=True)
    with pytest.raises(
        ProtectedRecommendationAdjudicationError,
        match="protected_recommendation_adjudication_permission_denied",
    ):
        await create_adjudication(service, completion, policy, actor)
    assert permission.calls
    assert not repository._claims
    assert isinstance(adjudicator, SyntheticTrustedProtectedRecommendationAdjudicator)
    assert not adjudicator.calls


@pytest.mark.asyncio
async def test_unavailable_production_boundary_leaves_claim_without_record() -> None:
    service, repository, completion, policy, actor, adjudicator, _ = await adjudication_fixture(
        unavailable=True
    )
    with pytest.raises(
        ProtectedRecommendationAdjudicationError,
        match="protected_recommendation_adjudicator_unavailable",
    ):
        await create_adjudication(service, completion, policy, actor)
    assert repository._claims
    assert not repository._records
    assert isinstance(adjudicator, UnavailableTrustedProtectedRecommendationAdjudicator)


def test_input_schema_forbids_caller_shaped_preference() -> None:
    payload = {
        "completion_digest": "a" * 64,
        "adjudication_policy_id": "protected-recommendation-adjudication-policy.development",
        "adjudication_policy_digest": "b" * 64,
        "purpose": "Adjudicate the exact protected recommendation candidates safely.",
        "acknowledged_preference_is_not_approval": True,
        "acknowledged_tie_or_no_support_is_valid": True,
        "acknowledged_no_presentation_or_operational_authority": True,
        "preferred_candidate_id": "candidate-1",
        "score": 100,
        "ranking": ["candidate-1"],
    }
    with pytest.raises(ValidationError):
        ProtectedRecommendationAdjudicationInput.model_validate(payload)
