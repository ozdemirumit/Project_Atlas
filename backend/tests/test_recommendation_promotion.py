from __future__ import annotations

from dataclasses import asdict, replace
from datetime import timedelta

import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError
from test_protected_recommendation_adjudication import BROWSER_SESSION_ID
from test_protected_recommendation_presentation import (
    create_presentation,
    presentation_fixture,
)

from atlas.api.app import create_app
from atlas.api.recommendation_promotion_schemas import (
    RecommendationPromotionInput,
    RecommendationPromotionResultData,
)
from atlas.core.config import Settings
from atlas.modules.ai.application.protected_model_invocation import (
    GovernedProtectedModelInvocationService,
)
from atlas.modules.identity.domain.models import AuthenticatedSubject
from atlas.modules.recommendations.adapters.promotion_memory import (
    InMemoryRecommendationPromotionPolicySource,
    MemoryRecommendationPromotionRepository,
)
from atlas.modules.recommendations.adapters.promotion_postgres import (
    PostgreSQLRecommendationPromotionRepository,
)
from atlas.modules.recommendations.adapters.promotion_synthetic import (
    SyntheticTrustedRecommendationPromoter,
    UnavailableTrustedRecommendationPromoter,
)
from atlas.modules.recommendations.application.promotion import (
    GovernedRecommendationPromotionService,
    build_development_recommendation_promotion_policy,
)
from atlas.modules.recommendations.application.promotion_ports import (
    RecommendationPromotionError,
)
from atlas.modules.recommendations.domain.promotion import (
    RecommendationPromotionPolicySnapshot,
    RecommendationPromotionResult,
)


class RecordingPromotionPermissionAuthorizer:
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
            raise RecommendationPromotionError("recommendation_promotion_permission_denied")


class TamperingPromotionPromoter(SyntheticTrustedRecommendationPromoter):
    def __init__(self, field: str) -> None:
        self._field = field

    async def promote(self, *args: object, **kwargs: object):  # type: ignore[no-untyped-def]
        receipt, artifact = await super().promote(*args, **kwargs)  # type: ignore[arg-type]
        if self._field == "promotion_receipt_digest":
            artifact = replace(artifact, promotion_receipt_digest="e" * 64)
        else:
            artifact = replace(artifact, source_binding_digest="e" * 64)
        artifact = replace(
            artifact,
            canonical_digest=GovernedRecommendationPromotionService._artifact_digest(artifact),
        )
        return receipt, artifact


async def promotion_fixture(
    *, deny: bool = False, unavailable: bool = False
) -> tuple[
    GovernedRecommendationPromotionService,
    MemoryRecommendationPromotionRepository,
    object,
    RecommendationPromotionPolicySnapshot,
    AuthenticatedSubject,
    RecordingPromotionPermissionAuthorizer,
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
    policy = build_development_recommendation_promotion_policy(
        organization_id=presentation.record.organization_id,
        environment_id=presentation.record.environment_id,
        issued_at=presentation.record.presented_at - timedelta(hours=1),
        expires_at=presentation.record.presented_at + timedelta(days=1),
    )
    permission = RecordingPromotionPermissionAuthorizer(deny=deny)
    repository = MemoryRecommendationPromotionRepository()
    promoter = (
        UnavailableTrustedRecommendationPromoter()
        if unavailable
        else SyntheticTrustedRecommendationPromoter()
    )
    service = GovernedRecommendationPromotionService(
        repository=repository,
        presentation_source=presentation_service,
        policy_source=InMemoryRecommendationPromotionPolicySource((policy,)),
        permission_authorizer=permission,
        promoter=promoter,
        audit_sink=presentation_service._audit_sink,
        environment_id=presentation.record.environment_id,
        clock=lambda: presentation.record.presented_at,
    )
    return service, repository, presentation, policy, actor, permission


async def create_promotion(
    service: GovernedRecommendationPromotionService,
    presentation: object,
    policy: RecommendationPromotionPolicySnapshot,
    actor: AuthenticatedSubject,
) -> RecommendationPromotionResult:
    record = presentation.record  # type: ignore[attr-defined]
    return await service.create(
        actor=actor,
        presentation_id=record.presentation_id,
        presentation_digest=record.canonical_digest,
        promotion_policy_id=policy.policy_id,
        promotion_policy_digest=policy.canonical_digest,
        purpose=record.purpose,
        draft_only_acknowledged=True,
        no_review_or_approval_acknowledged=True,
        no_operational_authority_acknowledged=True,
        browser_session_id=BROWSER_SESSION_ID,
        idempotency_key="recommendation-promotion-001",
        correlation_id="cor_recommendation_promotion",
    )


@pytest.mark.asyncio
async def test_promotion_creates_draft_and_exact_replay() -> None:
    service, _, presentation, policy, actor, permission = await promotion_fixture()
    result = await create_promotion(service, presentation, policy, actor)
    repeated = await create_promotion(service, presentation, policy, actor)
    replay = await service.get(
        actor=actor,
        recommendation_id=result.artifact.recommendation_id,
        browser_session_id=BROWSER_SESSION_ID,
        correlation_id="cor_recommendation_promotion_read",
    )

    artifact = result.artifact
    assert artifact.state == "draft"
    assert artifact.outcome == presentation.recommendation.outcome  # type: ignore[attr-defined]
    assert artifact.options == presentation.recommendation.options  # type: ignore[attr-defined]
    assert artifact.recommendation_promoted
    assert not artifact.recommendation_ready_for_review
    assert not artifact.human_review_completed
    assert not artifact.recommendation_approved
    assert not artifact.workflow_created
    assert not artifact.itsm_record_created
    assert not artifact.execution_authorized
    assert not artifact.deployment_authorized
    assert not artifact.infrastructure_mutated
    assert repeated.artifact.reused and replay.artifact.reused
    assert len(permission.calls) == 4


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("outcome", "role"),
    (("tie", "tied"), ("no_support", "unsupported")),
)
async def test_promoted_artifact_preserves_nonpreferred_outcome_roles(
    outcome: str, role: str
) -> None:
    service, _, presentation, policy, actor, _ = await promotion_fixture()
    result = await create_promotion(service, presentation, policy, actor)
    options = tuple(replace(option, role=role) for option in result.artifact.options)

    artifact = replace(
        result.artifact,
        outcome=outcome,
        options=options,
        canonical_digest="f" * 64,
    )

    assert artifact.outcome == outcome
    assert all(option.role == role for option in artifact.options)
    with pytest.raises(ValueError, match="invalid promoted recommendation artifact"):
        replace(artifact, options=result.artifact.options)


@pytest.mark.asyncio
async def test_promotion_response_exposes_safe_content_only() -> None:
    service, _, presentation, policy, actor, _ = await promotion_fixture()
    result = await create_promotion(service, presentation, policy, actor)
    response = RecommendationPromotionResultData.from_domain(result).model_dump()
    serialized = str(response).lower()
    for private in (
        "consumer_subject_digest",
        "browser_session_binding_digest",
        "promotion_authorization_digest",
        "source_binding_digest",
        "promotion_receipt_digest",
        "capability_id",
        "entity_ids",
        "relationship_ids",
        "tool_call",
        "<script",
    ):
        assert private not in serialized
    assert response["recommendation"]["state"] == "draft"
    assert response["recommendation"]["execution_authorized"] is False


@pytest.mark.asyncio
async def test_postgres_promotion_round_trip_preserves_safe_artifact() -> None:
    service, _, presentation, policy, actor, _ = await promotion_fixture()
    result = await create_promotion(service, presentation, policy, actor)
    payload = GovernedProtectedModelInvocationService._normalize(asdict(result.artifact))
    assert isinstance(payload, dict)
    restored = PostgreSQLRecommendationPromotionRepository._artifact_to_domain(payload)
    assert restored == result.artifact


@pytest.mark.asyncio
async def test_permission_denial_happens_before_claim() -> None:
    service, repository, presentation, policy, actor, permission = await promotion_fixture(
        deny=True
    )
    with pytest.raises(RecommendationPromotionError, match="permission_denied"):
        await create_promotion(service, presentation, policy, actor)
    assert permission.calls
    assert not repository._claims
    assert not repository._artifacts


@pytest.mark.asyncio
async def test_unavailable_promoter_fails_closed() -> None:
    service, repository, presentation, policy, actor, _ = await promotion_fixture(unavailable=True)
    with pytest.raises(RecommendationPromotionError, match="promoter_unavailable"):
        await create_promotion(service, presentation, policy, actor)
    assert repository._claims
    assert not repository._artifacts


@pytest.mark.asyncio
@pytest.mark.parametrize("tampered_field", ("promotion_receipt_digest", "source_binding_digest"))
async def test_promotion_rejects_cross_binding_tampering(tampered_field: str) -> None:
    service, repository, presentation, policy, actor, _ = await promotion_fixture()
    service._promoter = TamperingPromotionPromoter(tampered_field)

    with pytest.raises(RecommendationPromotionError, match="receipt_invalid"):
        await create_promotion(service, presentation, policy, actor)

    assert repository._claims
    assert not repository._artifacts


@pytest.mark.asyncio
async def test_exact_replay_rejects_tampered_claim() -> None:
    service, repository, presentation, policy, actor, _ = await promotion_fixture()
    await create_promotion(service, presentation, policy, actor)
    claim_id, claim = next(iter(repository._claims.items()))
    repository._claims[claim_id] = replace(
        claim, recommendation_id="recommendation.promoted.tampered"
    )

    with pytest.raises(RecommendationPromotionError, match="integrity_failed"):
        await create_promotion(service, presentation, policy, actor)


def test_input_schema_forbids_caller_shaped_promotion() -> None:
    payload = {
        "presentation_digest": "a" * 64,
        "promotion_policy_id": "recommendation-promotion-policy.development",
        "promotion_policy_digest": "b" * 64,
        "purpose": "Promote the exact protected recommendation presentation.",
        "acknowledged_draft_only": True,
        "acknowledged_no_review_or_approval": True,
        "acknowledged_no_operational_authority": True,
        "outcome": "preferred",
        "candidate_id": "candidate-1",
        "command": "restart-controller",
        "approve": True,
    }
    with pytest.raises(ValidationError):
        RecommendationPromotionInput.model_validate(payload)


def test_openapi_registers_recommendation_promotion_routes() -> None:
    with TestClient(create_app(Settings(environment="test"))) as client:
        paths = client.get("/openapi.json").json()["paths"]
    assert "/api/v1/recommendation-presentations/{presentation_id}/promotions" in paths
    assert (
        "/api/v1/recommendation-presentations/{presentation_id}/promotions/{recommendation_id}"
        in paths
    )
