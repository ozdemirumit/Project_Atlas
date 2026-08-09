from __future__ import annotations

from dataclasses import asdict, replace
from datetime import timedelta

import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError
from test_protected_recommendation_adjudication import BROWSER_SESSION_ID
from test_recommendation_promotion import create_promotion, promotion_fixture

from atlas.api.app import create_app
from atlas.api.recommendation_readiness_schemas import (
    RecommendationReadinessInput,
    RecommendationReadinessResultData,
)
from atlas.core.config import Settings
from atlas.modules.ai.application.protected_model_invocation import (
    GovernedProtectedModelInvocationService,
)
from atlas.modules.identity.domain.models import AuthenticatedSubject
from atlas.modules.recommendations.adapters.readiness_memory import (
    InMemoryRecommendationReadinessPolicySource,
    MemoryRecommendationReadinessRepository,
)
from atlas.modules.recommendations.adapters.readiness_postgres import (
    PostgreSQLRecommendationReadinessRepository,
)
from atlas.modules.recommendations.adapters.readiness_synthetic import (
    SyntheticTrustedRecommendationReadinessEvaluator,
    UnavailableTrustedRecommendationReadinessEvaluator,
)
from atlas.modules.recommendations.application.readiness import (
    GovernedRecommendationReadinessService,
    build_development_recommendation_readiness_policy,
)
from atlas.modules.recommendations.application.readiness_ports import (
    RecommendationReadinessError,
)
from atlas.modules.recommendations.domain.promotion import RecommendationPromotionResult
from atlas.modules.recommendations.domain.readiness import (
    RecommendationReadinessPolicySnapshot,
    RecommendationReadinessResult,
)


class RecordingReadinessPermissionAuthorizer:
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
            raise RecommendationReadinessError("recommendation_readiness_permission_denied")


class TamperingReadinessEvaluator(SyntheticTrustedRecommendationReadinessEvaluator):
    def __init__(self, field: str) -> None:
        self._field = field

    async def evaluate(self, *args: object, **kwargs: object):  # type: ignore[no-untyped-def]
        receipt, assessment = await super().evaluate(*args, **kwargs)  # type: ignore[arg-type]
        if self._field == "source_binding_digest":
            receipt = replace(receipt, source_binding_digest="e" * 64)
        elif self._field == "assessment_digest":
            receipt = replace(receipt, assessment_digest="e" * 64)
        else:
            assessment = replace(assessment, readiness_receipt_digest="e" * 64)
        if self._field in {"source_binding_digest", "assessment_digest"}:
            receipt = replace(
                receipt,
                canonical_digest=GovernedProtectedModelInvocationService._digest(
                    GovernedProtectedModelInvocationService._payload(
                        replace(receipt, canonical_digest="0" * 64)
                    )
                ),
            )
        return receipt, assessment


async def readiness_fixture(
    *, deny: bool = False, unavailable: bool = False
) -> tuple[
    GovernedRecommendationReadinessService,
    MemoryRecommendationReadinessRepository,
    RecommendationReadinessPolicySnapshot,
    RecommendationPromotionResult,
    AuthenticatedSubject,
    RecordingReadinessPermissionAuthorizer,
]:
    promotion_service, _, presentation, promotion_policy, actor, _ = await promotion_fixture()
    promotion = await create_promotion(promotion_service, presentation, promotion_policy, actor)
    policy = build_development_recommendation_readiness_policy(
        organization_id=promotion.artifact.organization_id,
        environment_id=promotion.artifact.environment_id,
        issued_at=promotion.artifact.promoted_at - timedelta(hours=1),
        expires_at=promotion.artifact.promoted_at + timedelta(days=1),
    )
    permission = RecordingReadinessPermissionAuthorizer(deny=deny)
    repository = MemoryRecommendationReadinessRepository()
    evaluator = (
        UnavailableTrustedRecommendationReadinessEvaluator()
        if unavailable
        else SyntheticTrustedRecommendationReadinessEvaluator()
    )
    service = GovernedRecommendationReadinessService(
        repository=repository,
        promotion_source=promotion_service,
        policy_source=InMemoryRecommendationReadinessPolicySource((policy,)),
        permission_authorizer=permission,
        evaluator=evaluator,
        audit_sink=promotion_service._audit_sink,
        environment_id=promotion.artifact.environment_id,
        clock=lambda: promotion.artifact.promoted_at,
    )
    return service, repository, policy, promotion, actor, permission


async def create_readiness(
    service: GovernedRecommendationReadinessService,
    policy: RecommendationReadinessPolicySnapshot,
    promotion: RecommendationPromotionResult,
    actor: AuthenticatedSubject,
) -> RecommendationReadinessResult:
    artifact = promotion.artifact
    return await service.create(
        actor=actor,
        recommendation_id=artifact.recommendation_id,
        recommendation_digest=artifact.canonical_digest,
        readiness_policy_id=policy.policy_id,
        readiness_policy_digest=policy.canonical_digest,
        purpose=artifact.purpose,
        readiness_is_not_review_acknowledged=True,
        blocked_requires_new_version_acknowledged=True,
        no_operational_authority_acknowledged=True,
        browser_session_id=BROWSER_SESSION_ID,
        idempotency_key="recommendation-readiness-001",
        correlation_id="cor_recommendation_readiness",
    )


@pytest.mark.asyncio
async def test_readiness_creates_ready_assessment_and_exact_replay() -> None:
    service, _, policy, promotion, actor, permission = await readiness_fixture()
    result = await create_readiness(service, policy, promotion, actor)
    repeated = await create_readiness(service, policy, promotion, actor)
    replay = await service.get(
        actor=actor,
        assessment_id=result.assessment.assessment_id,
        browser_session_id=BROWSER_SESSION_ID,
        correlation_id="cor_recommendation_readiness_read",
    )

    assessment = result.assessment
    assert assessment.evaluation_outcome == "ready"
    assert assessment.state == "ready_for_review"
    assert assessment.recommendation_ready_for_review
    assert assessment.passed_check_count == assessment.check_count
    assert not assessment.reason_codes
    assert not assessment.human_review_completed
    assert not assessment.recommendation_approved
    assert not assessment.workflow_created
    assert not assessment.itsm_record_created
    assert not assessment.execution_authorized
    assert not assessment.deployment_authorized
    assert not assessment.infrastructure_mutated
    assert repeated.assessment.reused and replay.assessment.reused
    assert len(permission.calls) == 4


@pytest.mark.asyncio
async def test_evaluator_blocks_incomplete_safety_content() -> None:
    _, _, _, promotion, _, _ = await readiness_fixture()
    first, *remaining = promotion.artifact.options
    checks = SyntheticTrustedRecommendationReadinessEvaluator._checks(
        replace(
            promotion.artifact,
            options=(replace(first, overall_risk=""), *remaining),
        )
    )
    assert checks["safety.risk-impact-recovery-present"] == (
        False,
        "safety-detail-incomplete",
    )


@pytest.mark.asyncio
async def test_readiness_response_exposes_safe_metadata_only() -> None:
    service, _, policy, promotion, actor, _ = await readiness_fixture()
    result = await create_readiness(service, policy, promotion, actor)
    response = RecommendationReadinessResultData.from_domain(result).model_dump()
    serialized = str(response).lower()
    for private in (
        "claim_id",
        "consumer_subject_digest",
        "browser_session_binding_digest",
        "readiness_receipt_digest",
        "readiness_authorization_digest",
        "source_artifact_digest",
        "source_binding_digest",
        "policy_digest",
        "tool_call",
        "<script",
    ):
        assert private not in serialized
    assert response["assessment"]["state"] == "ready_for_review"
    assert response["assessment"]["execution_authorized"] is False


@pytest.mark.asyncio
async def test_postgres_readiness_round_trip_preserves_assessment() -> None:
    service, _, policy, promotion, actor, _ = await readiness_fixture()
    result = await create_readiness(service, policy, promotion, actor)
    payload = GovernedProtectedModelInvocationService._normalize(asdict(result.assessment))
    assert isinstance(payload, dict)
    restored = PostgreSQLRecommendationReadinessRepository._assessment_to_domain(payload)
    assert restored == result.assessment


@pytest.mark.asyncio
async def test_permission_denial_happens_before_readiness_claim() -> None:
    service, repository, policy, promotion, actor, permission = await readiness_fixture(deny=True)
    with pytest.raises(RecommendationReadinessError, match="permission_denied"):
        await create_readiness(service, policy, promotion, actor)
    assert permission.calls
    assert not repository._claims
    assert not repository._assessments


@pytest.mark.asyncio
async def test_unavailable_evaluator_fails_closed() -> None:
    service, repository, policy, promotion, actor, _ = await readiness_fixture(unavailable=True)
    with pytest.raises(RecommendationReadinessError, match="evaluator_unavailable"):
        await create_readiness(service, policy, promotion, actor)
    assert repository._claims
    assert not repository._assessments


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "tampered_field",
    ("source_binding_digest", "assessment_digest", "readiness_receipt_digest"),
)
async def test_readiness_rejects_cross_binding_tampering(tampered_field: str) -> None:
    service, repository, policy, promotion, actor, _ = await readiness_fixture()
    service._evaluator = TamperingReadinessEvaluator(tampered_field)
    with pytest.raises(RecommendationReadinessError, match="receipt_invalid"):
        await create_readiness(service, policy, promotion, actor)
    assert repository._claims
    assert not repository._assessments


@pytest.mark.asyncio
async def test_exact_replay_rejects_tampered_readiness_claim() -> None:
    service, repository, policy, promotion, actor, _ = await readiness_fixture()
    await create_readiness(service, policy, promotion, actor)
    claim_id, claim = next(iter(repository._claims.items()))
    repository._claims[claim_id] = replace(
        claim, recommendation_id="recommendation.promoted.tampered"
    )
    with pytest.raises(RecommendationReadinessError, match="integrity_failed"):
        await create_readiness(service, policy, promotion, actor)


def test_input_schema_forbids_caller_shaped_readiness_or_authority() -> None:
    payload = {
        "recommendation_digest": "a" * 64,
        "readiness_policy_id": "recommendation-readiness-policy.development",
        "readiness_policy_digest": "b" * 64,
        "purpose": "Assess the exact recommendation for human review readiness.",
        "acknowledged_readiness_is_not_review": True,
        "acknowledged_blocked_requires_new_version": True,
        "acknowledged_no_operational_authority": True,
        "evaluation_outcome": "ready",
        "reviewer_id": "subject.reviewer",
        "approve": True,
        "command": "restart-controller",
    }
    with pytest.raises(ValidationError):
        RecommendationReadinessInput.model_validate(payload)


def test_openapi_registers_recommendation_readiness_routes() -> None:
    with TestClient(create_app(Settings(environment="test"))) as client:
        paths = client.get("/openapi.json").json()["paths"]
    assert "/api/v1/recommendations/{recommendation_id}/review-readiness-assessments" in paths
    assert (
        "/api/v1/recommendations/{recommendation_id}/review-readiness-assessments/"
        "{assessment_id}" in paths
    )
