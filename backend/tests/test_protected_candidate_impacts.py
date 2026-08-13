from __future__ import annotations

from dataclasses import asdict, replace
from datetime import UTC, datetime, timedelta

import pytest
from pydantic import ValidationError
from test_protected_recommendation_candidates import candidate_fixture, create_candidates

from atlas.api.protected_candidate_impact_schemas import (
    ProtectedCandidateImpactInput,
    ProtectedCandidateImpactResultData,
)
from atlas.modules.ai.adapters.protected_candidate_impact_memory import (
    InMemoryProtectedCandidateImpactPolicySource,
    MemoryProtectedCandidateImpactRepository,
)
from atlas.modules.ai.adapters.protected_candidate_impact_postgres import (
    PostgreSQLProtectedCandidateImpactRepository,
)
from atlas.modules.ai.adapters.protected_candidate_impact_synthetic import (
    SyntheticTrustedProtectedCandidateImpactAnalyzer,
    UnavailableTrustedProtectedCandidateImpactAnalyzer,
)
from atlas.modules.ai.application.protected_candidate_impact_enrichment import (
    GovernedProtectedCandidateImpactService,
    build_development_protected_candidate_impact_policy,
)
from atlas.modules.ai.application.protected_candidate_impact_enrichment_ports import (
    ProtectedCandidateImpactError,
)
from atlas.modules.ai.application.protected_model_invocation import (
    GovernedProtectedModelInvocationService,
)
from atlas.modules.ai.domain.protected_candidate_impact_enrichment import (
    ProtectedCandidateImpactPolicySnapshot,
    ProtectedCandidateImpactResult,
)
from atlas.modules.ai.domain.protected_recommendation_candidate_generation import (
    ProtectedRecommendationCandidateResult,
)
from atlas.modules.graph.adapters.synthetic import build_synthetic_graph_snapshot
from atlas.modules.graph.application.engine import InMemoryGraphImpactAnalyzer
from atlas.modules.identity.domain.models import (
    AssuranceLevel,
    AuthenticatedSubject,
    AuthenticationMethod,
    SubjectKind,
)


class RecordingImpactPermissionAuthorizer:
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
            raise ProtectedCandidateImpactError("protected_candidate_impact_permission_denied")


async def impact_fixture(
    *,
    deny: bool = False,
    unavailable: bool = False,
    required_assurance_level: AssuranceLevel = AssuranceLevel.SINGLE_FACTOR,
) -> tuple[
    GovernedProtectedCandidateImpactService,
    MemoryProtectedCandidateImpactRepository,
    ProtectedRecommendationCandidateResult,
    ProtectedCandidateImpactPolicySnapshot,
    AuthenticatedSubject,
    SyntheticTrustedProtectedCandidateImpactAnalyzer
    | UnavailableTrustedProtectedCandidateImpactAnalyzer,
    RecordingImpactPermissionAuthorizer,
]:
    candidate_service, _, presentation, candidate_policy, actor, *_ = await candidate_fixture()
    candidates = await create_candidates(candidate_service, presentation, candidate_policy, actor)
    policy = build_development_protected_candidate_impact_policy(
        organization_id=candidates.record.organization_id,
        environment_id=candidates.record.environment_id,
        issued_at=candidates.record.generated_at - timedelta(hours=1),
        expires_at=candidates.record.generated_at + timedelta(days=1),
    )
    policy = replace(policy, required_assurance_level=required_assurance_level)
    policy = replace(
        policy,
        canonical_digest=GovernedProtectedModelInvocationService._digest(
            GovernedProtectedModelInvocationService._payload(policy)
        ),
    )
    analyzer = (
        UnavailableTrustedProtectedCandidateImpactAnalyzer()
        if unavailable
        else SyntheticTrustedProtectedCandidateImpactAnalyzer()
    )
    permission = RecordingImpactPermissionAuthorizer(deny=deny)
    repository = MemoryProtectedCandidateImpactRepository()
    service = GovernedProtectedCandidateImpactService(
        repository=repository,
        candidate_source=candidate_service,
        policy_source=InMemoryProtectedCandidateImpactPolicySource((policy,)),
        permission_authorizer=permission,
        graph_analyzer=InMemoryGraphImpactAnalyzer(
            snapshot=build_synthetic_graph_snapshot(
                organization_id=candidates.record.organization_id,
                environment=candidates.record.environment_id.removeprefix("environment."),
            )
        ),
        analyzer=analyzer,
        audit_sink=candidate_service._audit_sink,
        environment_id=candidates.record.environment_id,
        clock=lambda: candidates.record.generated_at,
    )
    return service, repository, candidates, policy, actor, analyzer, permission


async def create_impact(
    service: GovernedProtectedCandidateImpactService,
    candidates: ProtectedRecommendationCandidateResult,
    policy: ProtectedCandidateImpactPolicySnapshot,
    actor: AuthenticatedSubject,
) -> ProtectedCandidateImpactResult:
    return await service.create(
        actor=actor,
        candidate_set_id=candidates.record.candidate_set_id,
        candidate_set_digest=candidates.record.candidate_content_digest,
        impact_policy_id=policy.policy_id,
        impact_policy_digest=policy.canonical_digest,
        purpose=candidates.record.purpose,
        reachability_not_outage_acknowledged=True,
        impact_provisional_acknowledged=True,
        no_recommendation_or_operational_authority_acknowledged=True,
        browser_session_id="session_protected_knowledge_retrieval_001",
        idempotency_key="protected-candidate-impact-001",
        correlation_id="cor_protected_candidate_impact",
    )


@pytest.mark.asyncio
async def test_impact_is_private_bounded_and_idempotent() -> None:
    service, _, candidates, policy, actor, analyzer, permission = await impact_fixture()
    result = await create_impact(service, candidates, policy, actor)
    repeated = await create_impact(service, candidates, policy, actor)
    replay = await service.get(
        actor=actor,
        impact_analysis_id=result.record.impact_analysis_id,
        browser_session_id="session_protected_knowledge_retrieval_001",
        correlation_id="cor_protected_candidate_impact_read",
    )

    assert result.record.candidate_count == 3
    assert result.record.path_count == 5
    assert result.record.modeled_entity_count == 6
    assert result.record.technical_service_count == 1
    assert result.record.business_service_count == 1
    assert result.record.gap_count == 3
    assert result.record.unknown_count == 2
    assert result.record.service_impact_analyzed
    assert not result.record.outage_confirmed
    assert not result.record.impact_complete
    assert not result.record.recommendation_complete
    assert not result.record.execution_authorized
    assert repeated.record.reused and replay.record.reused
    assert isinstance(analyzer, SyntheticTrustedProtectedCandidateImpactAnalyzer)
    assert len(analyzer.calls) == 1
    assert len(permission.calls) == 4


@pytest.mark.asyncio
async def test_default_policy_allows_development_authentication() -> None:
    service, _, candidates, policy, actor, *_ = await impact_fixture()
    development_actor = replace(
        actor,
        authentication_method=AuthenticationMethod.DEVELOPMENT,
        assurance_level=AssuranceLevel.DEVELOPMENT,
    )

    result = await create_impact(service, candidates, policy, development_actor)

    assert result.record.service_impact_analyzed
    assert policy.required_assurance_level is AssuranceLevel.SINGLE_FACTOR


@pytest.mark.asyncio
async def test_explicit_stronger_policy_rejects_development_authentication() -> None:
    service, _, candidates, policy, actor, *_ = await impact_fixture(
        required_assurance_level=AssuranceLevel.MULTI_FACTOR
    )
    development_actor = replace(
        actor,
        authentication_method=AuthenticationMethod.DEVELOPMENT,
        assurance_level=AssuranceLevel.DEVELOPMENT,
    )

    with pytest.raises(ProtectedCandidateImpactError, match="assurance_required"):
        await create_impact(service, candidates, policy, development_actor)


@pytest.mark.asyncio
async def test_non_human_actor_is_rejected() -> None:
    service, _, candidates, policy, actor, *_ = await impact_fixture()

    with pytest.raises(ProtectedCandidateImpactError, match="human_required"):
        await create_impact(
            service,
            candidates,
            policy,
            replace(actor, kind=SubjectKind.SERVICE),
        )


def test_policy_accepts_only_supported_assurance_levels() -> None:
    issued_at = datetime(2026, 1, 1, tzinfo=UTC)
    policy = build_development_protected_candidate_impact_policy(
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
async def test_persisted_impact_record_excludes_protected_paths_and_entities() -> None:
    service, _, candidates, policy, actor, analyzer, _ = await impact_fixture()
    result = await create_impact(service, candidates, policy, actor)
    persisted = GovernedProtectedModelInvocationService._normalize(asdict(result.record))
    assert isinstance(persisted, dict)
    serialized = str(persisted).lower()
    for private in (
        "entity.volume.erp.prod",
        "entity.service.erp.application",
        "entity.business-service.erp",
        "relationship_ids",
        "evidence_references",
        "redundancy and failover state",
        "candidate-1",
    ):
        assert private not in serialized
    assert isinstance(analyzer, SyntheticTrustedProtectedCandidateImpactAnalyzer)
    assert result.record.impact_analysis_id in analyzer._vault


@pytest.mark.asyncio
async def test_postgres_impact_record_round_trip_is_metadata_only() -> None:
    service, _, candidates, policy, actor, *_ = await impact_fixture()
    result = await create_impact(service, candidates, policy, actor)
    payload = GovernedProtectedModelInvocationService._normalize(asdict(result.record))
    assert isinstance(payload, dict)
    restored = PostgreSQLProtectedCandidateImpactRepository._record_to_domain(payload)
    assert restored == result.record


@pytest.mark.asyncio
async def test_api_result_hides_protected_impact_content_and_bindings() -> None:
    service, _, candidates, policy, actor, *_ = await impact_fixture()
    result = await create_impact(service, candidates, policy, actor)
    response = ProtectedCandidateImpactResultData.from_domain(result).model_dump()
    record = response["impact_analysis"]
    manifest = response["manifest"]
    for private in (
        "claim_id",
        "consumer_subject_digest",
        "browser_session_binding_digest",
        "impact_authorization_digest",
        "protected_report_digest",
        "candidate_source_binding_digest",
        "paths",
        "entities",
        "services",
        "known_gaps",
        "unknowns",
        "evidence_references",
    ):
        assert private not in record
        assert private not in manifest
    assert record["service_impact_analyzed"] is True
    assert record["outage_confirmed"] is False
    assert manifest["path_count"] == 5


@pytest.mark.asyncio
async def test_permission_denial_happens_before_claim_and_candidate_rehydration() -> None:
    service, repository, candidates, policy, actor, analyzer, permission = await impact_fixture(
        deny=True
    )
    with pytest.raises(
        ProtectedCandidateImpactError, match="protected_candidate_impact_permission_denied"
    ):
        await create_impact(service, candidates, policy, actor)
    assert permission.calls
    assert not repository._claims
    assert isinstance(analyzer, SyntheticTrustedProtectedCandidateImpactAnalyzer)
    assert not analyzer.calls


@pytest.mark.asyncio
async def test_unavailable_production_boundary_leaves_claim_without_record() -> None:
    service, repository, candidates, policy, actor, analyzer, _ = await impact_fixture(
        unavailable=True
    )
    with pytest.raises(
        ProtectedCandidateImpactError, match="protected_candidate_impact_analyzer_unavailable"
    ):
        await create_impact(service, candidates, policy, actor)
    assert repository._claims
    assert not repository._records
    assert isinstance(analyzer, UnavailableTrustedProtectedCandidateImpactAnalyzer)


@pytest.mark.asyncio
async def test_wrong_browser_binding_is_hidden() -> None:
    service, _, candidates, policy, actor, *_ = await impact_fixture()
    result = await create_impact(service, candidates, policy, actor)
    with pytest.raises(ProtectedCandidateImpactError, match="protected_candidate_impact_not_found"):
        await service.get(
            actor=actor,
            impact_analysis_id=result.record.impact_analysis_id,
            browser_session_id="session_wrong_browser_binding_001",
            correlation_id="cor_protected_candidate_impact_wrong_browser",
        )


def test_input_schema_forbids_caller_shaped_graph_and_impact() -> None:
    payload = {
        "candidate_set_digest": "a" * 64,
        "impact_policy_id": "protected-candidate-impact-policy.development",
        "impact_policy_digest": "b" * 64,
        "purpose": "Enrich the exact protected candidates with graph context.",
        "acknowledged_reachability_is_not_outage_evidence": True,
        "acknowledged_impact_remains_provisional": True,
        "acknowledged_no_recommendation_or_operational_authority": True,
        "start_entity_id": "caller.target",
        "max_depth": 99,
        "impact": "confirmed",
    }
    with pytest.raises(ValidationError):
        ProtectedCandidateImpactInput.model_validate(payload)
