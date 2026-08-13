from __future__ import annotations

from dataclasses import asdict, replace
from datetime import UTC, datetime, timedelta

import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError
from test_protected_recommendation_adjudication import (
    BROWSER_SESSION_ID,
    adjudication_fixture,
    create_adjudication,
)

from atlas.api.app import create_app
from atlas.api.protected_recommendation_presentation_schemas import (
    ProtectedRecommendationPresentationInput,
    ProtectedRecommendationPresentationResultData,
)
from atlas.core.config import Settings
from atlas.modules.ai.adapters.protected_recommendation_presentation_memory import (
    InMemoryProtectedRecommendationPresentationPolicySource,
    MemoryProtectedRecommendationPresentationRepository,
)
from atlas.modules.ai.adapters.protected_recommendation_presentation_postgres import (
    PostgreSQLProtectedRecommendationPresentationRepository,
)
from atlas.modules.ai.adapters.protected_recommendation_presentation_synthetic import (
    SyntheticTrustedProtectedRecommendationPresenter,
    UnavailableTrustedProtectedRecommendationPresenter,
)
from atlas.modules.ai.application.protected_model_invocation import (
    GovernedProtectedModelInvocationService,
)
from atlas.modules.ai.application.protected_recommendation_presentation import (
    GovernedProtectedRecommendationPresentationService,
    build_development_protected_recommendation_presentation_policy,
)
from atlas.modules.ai.application.protected_recommendation_presentation_ports import (
    ProtectedRecommendationPresentationError,
)
from atlas.modules.ai.domain.protected_recommendation_adjudication import (
    ProtectedRecommendationAdjudicationResult,
)
from atlas.modules.ai.domain.protected_recommendation_presentation import (
    ProtectedRecommendationPresentationPolicySnapshot,
    ProtectedRecommendationPresentationResult,
)
from atlas.modules.identity.domain.models import (
    AssuranceLevel,
    AuthenticatedSubject,
    AuthenticationMethod,
    SubjectKind,
)


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
            raise ProtectedRecommendationPresentationError(
                "protected_recommendation_presentation_permission_denied"
            )


async def presentation_fixture(
    *,
    deny: bool = False,
    unavailable: bool = False,
    required_assurance_level: AssuranceLevel = AssuranceLevel.SINGLE_FACTOR,
) -> tuple[
    GovernedProtectedRecommendationPresentationService,
    MemoryProtectedRecommendationPresentationRepository,
    ProtectedRecommendationAdjudicationResult,
    ProtectedRecommendationPresentationPolicySnapshot,
    AuthenticatedSubject,
    SyntheticTrustedProtectedRecommendationPresenter
    | UnavailableTrustedProtectedRecommendationPresenter,
    RecordingPresentationPermissionAuthorizer,
]:
    (
        adjudication_service,
        _,
        completion,
        adjudication_policy,
        actor,
        *_,
    ) = await adjudication_fixture()
    adjudication = await create_adjudication(
        adjudication_service, completion, adjudication_policy, actor
    )
    policy = build_development_protected_recommendation_presentation_policy(
        organization_id=adjudication.record.organization_id,
        environment_id=adjudication.record.environment_id,
        issued_at=adjudication.record.adjudicated_at - timedelta(hours=1),
        expires_at=adjudication.record.adjudicated_at + timedelta(days=1),
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
    presenter = (
        UnavailableTrustedProtectedRecommendationPresenter()
        if unavailable
        else SyntheticTrustedProtectedRecommendationPresenter()
    )
    permission = RecordingPresentationPermissionAuthorizer(deny=deny)
    repository = MemoryProtectedRecommendationPresentationRepository()
    service = GovernedProtectedRecommendationPresentationService(
        repository=repository,
        adjudication_source=adjudication_service,
        policy_source=InMemoryProtectedRecommendationPresentationPolicySource((policy,)),
        permission_authorizer=permission,
        presenter=presenter,
        audit_sink=adjudication_service._audit_sink,
        environment_id=adjudication.record.environment_id,
        clock=lambda: adjudication.record.adjudicated_at,
    )
    return service, repository, adjudication, policy, actor, presenter, permission


async def create_presentation(
    service: GovernedProtectedRecommendationPresentationService,
    adjudication: ProtectedRecommendationAdjudicationResult,
    policy: ProtectedRecommendationPresentationPolicySnapshot,
    actor: AuthenticatedSubject,
) -> ProtectedRecommendationPresentationResult:
    return await service.create(
        actor=actor,
        adjudication_id=adjudication.record.adjudication_id,
        adjudication_digest=adjudication.record.canonical_digest,
        presentation_policy_id=policy.policy_id,
        presentation_policy_digest=policy.canonical_digest,
        purpose=adjudication.record.purpose,
        decision_support_only_acknowledged=True,
        tie_or_no_support_acknowledged=True,
        no_operational_authority_acknowledged=True,
        browser_session_id=BROWSER_SESSION_ID,
        idempotency_key="protected-recommendation-presentation-001",
        correlation_id="cor_protected_recommendation_presentation",
    )


@pytest.mark.asyncio
async def test_presentation_is_inert_bounded_and_idempotent() -> None:
    service, _, adjudication, policy, actor, presenter, permission = await presentation_fixture()
    result = await create_presentation(service, adjudication, policy, actor)
    repeated = await create_presentation(service, adjudication, policy, actor)
    replay = await service.get(
        actor=actor,
        presentation_id=result.record.presentation_id,
        browser_session_id=BROWSER_SESSION_ID,
        correlation_id="cor_protected_recommendation_presentation_read",
    )

    assert result.recommendation.outcome == "preferred"
    assert len(result.recommendation.options) == 3
    assert sum(option.role == "preferred" for option in result.recommendation.options) == 1
    assert result.record.recommendation_presented
    assert not result.record.recommendation_ready_for_review
    assert not result.record.recommendation_approved
    assert not result.record.workflow_created
    assert not result.record.execution_authorized
    assert not result.record.deployment_authorized
    assert not result.record.infrastructure_mutated
    assert repeated.record.reused and replay.record.reused
    assert isinstance(presenter, SyntheticTrustedProtectedRecommendationPresenter)
    assert len(presenter.calls) == 1
    assert result.record.presentation_id in presenter._vault
    assert len(permission.calls) == 4


@pytest.mark.asyncio
async def test_development_human_satisfies_default_presentation_policy() -> None:
    service, _, adjudication, policy, actor, *_ = await presentation_fixture()
    development_actor = replace(
        actor,
        authentication_method=AuthenticationMethod.DEVELOPMENT,
        assurance_level=AssuranceLevel.DEVELOPMENT,
    )

    result = await create_presentation(service, adjudication, policy, development_actor)

    assert result.record.presentation_policy_digest == policy.canonical_digest


@pytest.mark.asyncio
async def test_explicit_stronger_presentation_policy_rejects_development_assurance() -> None:
    service, repository, adjudication, policy, actor, *_, permission = await presentation_fixture(
        required_assurance_level=AssuranceLevel.MULTI_FACTOR
    )
    development_actor = replace(
        actor,
        authentication_method=AuthenticationMethod.DEVELOPMENT,
        assurance_level=AssuranceLevel.DEVELOPMENT,
    )

    with pytest.raises(
        ProtectedRecommendationPresentationError,
        match="protected_recommendation_presentation_assurance_required",
    ):
        await create_presentation(service, adjudication, policy, development_actor)

    assert not permission.calls
    assert not repository._claims


@pytest.mark.asyncio
async def test_presentation_rejects_non_human_subject() -> None:
    service, repository, adjudication, policy, actor, *_ = await presentation_fixture()
    service_actor = replace(actor, kind=SubjectKind.SERVICE)

    with pytest.raises(
        ProtectedRecommendationPresentationError,
        match="protected_recommendation_presentation_human_required",
    ):
        await create_presentation(service, adjudication, policy, service_actor)

    assert not repository._claims


@pytest.mark.parametrize(
    "required_assurance_level",
    (
        AssuranceLevel.SINGLE_FACTOR,
        AssuranceLevel.MULTI_FACTOR,
        AssuranceLevel.HARDWARE_BACKED,
    ),
)
def test_presentation_policy_supports_explicit_assurance_levels(
    required_assurance_level: AssuranceLevel,
) -> None:
    issued_at = datetime.now(UTC)
    base_policy = build_development_protected_recommendation_presentation_policy(
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
async def test_presentation_exposes_safe_decision_support_fields_only() -> None:
    service, _, adjudication, policy, actor, *_ = await presentation_fixture()
    result = await create_presentation(service, adjudication, policy, actor)
    response = ProtectedRecommendationPresentationResultData.from_domain(result).model_dump()
    serialized = str(response).lower()
    for private in (
        "candidate_id",
        "capability_id",
        "entity_ids",
        "relationship_ids",
        "browser_session_binding_digest",
        "consumer_subject_digest",
        "presentation_authorization_digest",
        "source_binding_digest",
        "rendering_digest",
        "cleanup_digest",
        "tool_call",
        "<script",
    ):
        assert private not in serialized
    option = response["recommendation"]["options"][0]
    assert option["overall_risk"] in {"low", "moderate", "high", "critical", "unknown"}
    assert option["work_maximum_minutes"] >= option["work_minimum_minutes"]
    assert option["recovery_maximum_minutes"] >= option["recovery_minimum_minutes"]
    assert response["presentation"]["media_type"] == "text/plain"


@pytest.mark.asyncio
async def test_persisted_presentation_is_metadata_only() -> None:
    service, _, adjudication, policy, actor, *_ = await presentation_fixture()
    result = await create_presentation(service, adjudication, policy, actor)
    persisted = GovernedProtectedModelInvocationService._normalize(asdict(result.record))
    serialized = str(persisted).lower()
    for private in (
        "repeat the approved read-only health observation",
        "recommendation-category.investigate",
        "candidate-1",
        "conceptual_action",
        "evidence_references",
    ):
        assert private not in serialized


@pytest.mark.asyncio
async def test_postgres_presentation_record_round_trip_is_metadata_only() -> None:
    service, _, adjudication, policy, actor, *_ = await presentation_fixture()
    result = await create_presentation(service, adjudication, policy, actor)
    payload = GovernedProtectedModelInvocationService._normalize(asdict(result.record))
    assert isinstance(payload, dict)
    restored = PostgreSQLProtectedRecommendationPresentationRepository._record_to_domain(payload)
    assert restored == result.record


@pytest.mark.asyncio
async def test_presenter_preserves_tie_without_selecting_an_option() -> None:
    service, _, adjudication, policy, actor, presenter, _ = await presentation_fixture()
    await create_presentation(service, adjudication, policy, actor)
    assert isinstance(presenter, SyntheticTrustedProtectedRecommendationPresenter)
    instruction = presenter.calls[0]
    bundle = await service._adjudication_source.rehydrate_for_presentation(
        actor=actor,
        adjudication_id=adjudication.record.adjudication_id,
        browser_session_id=BROWSER_SESSION_ID,
        correlation_id="cor_tie_source",
    )
    report, candidates, impacts, completions = bundle[1], bundle[3], bundle[4], bundle[5]
    first = replace(report.entries[0], preference_state="alternative")
    second = replace(
        report.entries[1],
        dimensions=first.dimensions,
        unknown_count=first.unknown_count,
        preference_state="alternative",
    )
    third = replace(report.entries[2], preference_state="alternative")
    tied_report = replace(
        report,
        entries=(first, second, third),
        preferred_count=0,
        alternative_count=3,
        tie=True,
    )
    _, recommendation = await presenter.present(
        instruction, tied_report, candidates, impacts, completions
    )
    assert recommendation.outcome == "tie"
    assert len(recommendation.options) == 2
    assert all(option.role == "tied" for option in recommendation.options)
    assert not any(option.role == "preferred" for option in recommendation.options)


@pytest.mark.asyncio
async def test_presenter_preserves_no_support_and_surfaces_evidence_needs() -> None:
    service, _, adjudication, policy, actor, presenter, _ = await presentation_fixture()
    await create_presentation(service, adjudication, policy, actor)
    assert isinstance(presenter, SyntheticTrustedProtectedRecommendationPresenter)
    instruction = presenter.calls[0]
    bundle = await service._adjudication_source.rehydrate_for_presentation(
        actor=actor,
        adjudication_id=adjudication.record.adjudication_id,
        browser_session_id=BROWSER_SESSION_ID,
        correlation_id="cor_no_support_source",
    )
    report, candidates, impacts, completions = bundle[1], bundle[3], bundle[4], bundle[5]
    entries = tuple(
        replace(
            entry,
            eligible=False,
            exclusion_reasons=("recovery-not-supportable",),
            preference_state="ineligible",
        )
        for entry in report.entries
    )
    unsupported_report = replace(
        report,
        entries=entries,
        eligible_count=0,
        excluded_count=3,
        preferred_count=0,
        alternative_count=0,
        tie=False,
        no_supportable_candidate=True,
    )
    _, recommendation = await presenter.present(
        instruction, unsupported_report, candidates, impacts, completions
    )
    assert recommendation.outcome == "no_support"
    assert all(option.role == "unsupported" for option in recommendation.options)
    assert all(option.support_reasons for option in recommendation.options)
    assert recommendation.evidence_needs


@pytest.mark.asyncio
async def test_permission_denial_precedes_claim() -> None:
    (
        service,
        repository,
        adjudication,
        policy,
        actor,
        presenter,
        permission,
    ) = await presentation_fixture(deny=True)
    with pytest.raises(
        ProtectedRecommendationPresentationError,
        match="protected_recommendation_presentation_permission_denied",
    ):
        await create_presentation(service, adjudication, policy, actor)
    assert permission.calls
    assert not repository._claims
    assert isinstance(presenter, SyntheticTrustedProtectedRecommendationPresenter)
    assert not presenter.calls


@pytest.mark.asyncio
async def test_unavailable_presenter_fails_closed() -> None:
    service, repository, adjudication, policy, actor, presenter, _ = await presentation_fixture(
        unavailable=True
    )
    with pytest.raises(
        ProtectedRecommendationPresentationError,
        match="protected_recommendation_presentation_presenter_unavailable",
    ):
        await create_presentation(service, adjudication, policy, actor)
    assert repository._claims
    assert not repository._records
    assert isinstance(presenter, UnavailableTrustedProtectedRecommendationPresenter)


@pytest.mark.asyncio
async def test_replay_fails_closed_when_protected_vault_content_is_missing() -> None:
    service, _, adjudication, policy, actor, presenter, _ = await presentation_fixture()
    result = await create_presentation(service, adjudication, policy, actor)
    assert isinstance(presenter, SyntheticTrustedProtectedRecommendationPresenter)
    presenter._vault.clear()
    with pytest.raises(
        ProtectedRecommendationPresentationError,
        match="protected_recommendation_presentation_content_unavailable",
    ):
        await service.get(
            actor=actor,
            presentation_id=result.record.presentation_id,
            browser_session_id=BROWSER_SESSION_ID,
            correlation_id="cor_missing_presentation_vault",
        )


def test_input_schema_forbids_caller_shaped_recommendation() -> None:
    payload = {
        "adjudication_digest": "a" * 64,
        "presentation_policy_id": "protected-recommendation-presentation-policy.development",
        "presentation_policy_digest": "b" * 64,
        "purpose": "Present the exact protected recommendation safely.",
        "acknowledged_decision_support_only": True,
        "acknowledged_tie_or_no_support_is_valid": True,
        "acknowledged_no_operational_authority": True,
        "candidate_id": "candidate-1",
        "command": "restart-controller",
        "preferred": True,
    }
    with pytest.raises(ValidationError):
        ProtectedRecommendationPresentationInput.model_validate(payload)


def test_openapi_registers_protected_recommendation_presentation_routes() -> None:
    with TestClient(create_app(Settings(environment="test"))) as client:
        paths = client.get("/openapi.json").json()["paths"]
    assert "/api/v1/ai/recommendation-adjudications/{adjudication_id}/presentations" in paths
    assert (
        "/api/v1/ai/recommendation-adjudications/{adjudication_id}/presentations/"
        "{presentation_id}" in paths
    )
