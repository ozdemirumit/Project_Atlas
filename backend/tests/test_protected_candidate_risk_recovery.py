from __future__ import annotations

from dataclasses import asdict, replace
from datetime import UTC, datetime, timedelta

import pytest
from pydantic import ValidationError
from test_protected_candidate_impacts import create_impact, impact_fixture

from atlas.api.protected_candidate_risk_recovery_schemas import (
    ProtectedCandidateRiskRecoveryInput,
    ProtectedCandidateRiskRecoveryResultData,
)
from atlas.modules.ai.adapters.protected_candidate_risk_recovery_memory import (
    InMemoryProtectedCandidateRiskRecoveryPolicySource,
    InMemoryProtectedOperationalEvidenceSource,
    MemoryProtectedCandidateRiskRecoveryRepository,
)
from atlas.modules.ai.adapters.protected_candidate_risk_recovery_postgres import (
    PostgreSQLProtectedCandidateRiskRecoveryRepository,
)
from atlas.modules.ai.adapters.protected_candidate_risk_recovery_synthetic import (
    SyntheticTrustedProtectedCandidateRiskRecoveryAssessor,
    UnavailableTrustedProtectedCandidateRiskRecoveryAssessor,
    build_development_operational_evidence_snapshot,
)
from atlas.modules.ai.application.protected_candidate_risk_recovery_completion import (
    GovernedProtectedCandidateRiskRecoveryService,
    build_development_protected_candidate_risk_recovery_policy,
)
from atlas.modules.ai.application.protected_candidate_risk_recovery_completion_ports import (
    ProtectedCandidateRiskRecoveryError,
)
from atlas.modules.ai.application.protected_model_invocation import (
    GovernedProtectedModelInvocationService,
)
from atlas.modules.ai.domain.protected_candidate_impact_enrichment import (
    ProtectedCandidateImpactResult,
)
from atlas.modules.ai.domain.protected_candidate_risk_recovery_completion import (
    ProtectedCandidateRiskRecoveryPolicySnapshot,
    ProtectedCandidateRiskRecoveryResult,
)
from atlas.modules.identity.domain.models import (
    AssuranceLevel,
    AuthenticatedSubject,
    AuthenticationMethod,
    SubjectKind,
)


class RecordingRiskRecoveryPermissionAuthorizer:
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
            raise ProtectedCandidateRiskRecoveryError(
                "protected_candidate_risk_recovery_permission_denied"
            )


async def completion_fixture(
    *,
    deny: bool = False,
    unavailable: bool = False,
    required_assurance_level: AssuranceLevel = AssuranceLevel.SINGLE_FACTOR,
) -> tuple[
    GovernedProtectedCandidateRiskRecoveryService,
    MemoryProtectedCandidateRiskRecoveryRepository,
    ProtectedCandidateImpactResult,
    ProtectedCandidateRiskRecoveryPolicySnapshot,
    AuthenticatedSubject,
    SyntheticTrustedProtectedCandidateRiskRecoveryAssessor
    | UnavailableTrustedProtectedCandidateRiskRecoveryAssessor,
    RecordingRiskRecoveryPermissionAuthorizer,
]:
    impact_service, _, candidates, impact_policy, actor, *_ = await impact_fixture()
    impact = await create_impact(impact_service, candidates, impact_policy, actor)
    policy = build_development_protected_candidate_risk_recovery_policy(
        organization_id=impact.record.organization_id,
        environment_id=impact.record.environment_id,
        issued_at=impact.record.analyzed_at - timedelta(hours=1),
        expires_at=impact.record.analyzed_at + timedelta(days=1),
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
    evidence = build_development_operational_evidence_snapshot(
        organization_id=impact.record.organization_id,
        environment_id=impact.record.environment_id,
        generated_at=impact.record.analyzed_at - timedelta(minutes=1),
        expires_at=impact.record.analyzed_at + timedelta(days=1),
    )
    assessor = (
        UnavailableTrustedProtectedCandidateRiskRecoveryAssessor()
        if unavailable
        else SyntheticTrustedProtectedCandidateRiskRecoveryAssessor()
    )
    permission = RecordingRiskRecoveryPermissionAuthorizer(deny=deny)
    repository = MemoryProtectedCandidateRiskRecoveryRepository()
    service = GovernedProtectedCandidateRiskRecoveryService(
        repository=repository,
        impact_source=impact_service,
        policy_source=InMemoryProtectedCandidateRiskRecoveryPolicySource((policy,)),
        evidence_source=InMemoryProtectedOperationalEvidenceSource((evidence,)),
        permission_authorizer=permission,
        assessor=assessor,
        audit_sink=impact_service._audit_sink,
        environment_id=impact.record.environment_id,
        clock=lambda: impact.record.analyzed_at,
    )
    return service, repository, impact, policy, actor, assessor, permission


async def create_completion(
    service: GovernedProtectedCandidateRiskRecoveryService,
    impact: ProtectedCandidateImpactResult,
    policy: ProtectedCandidateRiskRecoveryPolicySnapshot,
    actor: AuthenticatedSubject,
) -> ProtectedCandidateRiskRecoveryResult:
    return await service.create(
        actor=actor,
        impact_analysis_id=impact.record.impact_analysis_id,
        impact_digest=impact.record.canonical_digest,
        completion_policy_id=policy.policy_id,
        completion_policy_digest=policy.canonical_digest,
        purpose=impact.record.purpose,
        estimates_not_guarantees_acknowledged=True,
        unknowns_cannot_lower_risk_acknowledged=True,
        no_preference_or_operational_authority_acknowledged=True,
        browser_session_id="session_protected_knowledge_retrieval_001",
        idempotency_key="protected-candidate-risk-recovery-001",
        correlation_id="cor_protected_candidate_risk_recovery",
    )


@pytest.mark.asyncio
async def test_completion_is_private_bounded_and_idempotent() -> None:
    service, _, impact, policy, actor, assessor, permission = await completion_fixture()
    result = await create_completion(service, impact, policy, actor)
    repeated = await create_completion(service, impact, policy, actor)
    replay = await service.get(
        actor=actor,
        completion_id=result.record.completion_id,
        browser_session_id="session_protected_knowledge_retrieval_001",
        correlation_id="cor_protected_candidate_risk_recovery_read",
    )

    assert result.record.candidate_count == 3
    assert result.record.evidence_item_count == 8
    assert result.record.moderate_risk_count == 3
    assert result.record.maximum_risk == "moderate"
    assert result.record.interruption_possible_count == 0
    assert result.record.recovery_feasible_count == 3
    assert result.record.work_minimum_minutes == 0
    assert result.record.work_maximum_minutes == 240
    assert result.record.impact_complete
    assert result.record.risk_completed
    assert result.record.duration_established
    assert result.record.interruption_established
    assert result.record.recovery_completed
    assert not result.record.outage_confirmed
    assert not result.record.recommendation_complete
    assert not result.record.execution_authorized
    assert repeated.record.reused and replay.record.reused
    assert isinstance(assessor, SyntheticTrustedProtectedCandidateRiskRecoveryAssessor)
    assert len(assessor.calls) == 1
    assert len(permission.calls) == 4


@pytest.mark.asyncio
async def test_development_human_satisfies_default_completion_policy() -> None:
    service, _, impact, policy, actor, *_ = await completion_fixture()
    development_actor = replace(
        actor,
        authentication_method=AuthenticationMethod.DEVELOPMENT,
        assurance_level=AssuranceLevel.DEVELOPMENT,
    )

    result = await create_completion(service, impact, policy, development_actor)

    assert result.record.completion_policy_digest == policy.canonical_digest


@pytest.mark.asyncio
async def test_explicit_stronger_completion_policy_rejects_development_assurance() -> None:
    service, repository, impact, policy, actor, *_, permission = await completion_fixture(
        required_assurance_level=AssuranceLevel.MULTI_FACTOR
    )
    development_actor = replace(
        actor,
        authentication_method=AuthenticationMethod.DEVELOPMENT,
        assurance_level=AssuranceLevel.DEVELOPMENT,
    )

    with pytest.raises(
        ProtectedCandidateRiskRecoveryError,
        match="protected_candidate_risk_recovery_assurance_required",
    ):
        await create_completion(service, impact, policy, development_actor)

    assert not permission.calls
    assert not repository._claims


@pytest.mark.asyncio
async def test_completion_rejects_non_human_subject() -> None:
    service, repository, impact, policy, actor, *_ = await completion_fixture()
    service_actor = replace(actor, kind=SubjectKind.SERVICE)

    with pytest.raises(
        ProtectedCandidateRiskRecoveryError,
        match="protected_candidate_risk_recovery_human_required",
    ):
        await create_completion(service, impact, policy, service_actor)

    assert not repository._claims


@pytest.mark.parametrize(
    "required_assurance_level",
    (
        AssuranceLevel.SINGLE_FACTOR,
        AssuranceLevel.MULTI_FACTOR,
        AssuranceLevel.HARDWARE_BACKED,
    ),
)
def test_completion_policy_supports_explicit_assurance_levels(
    required_assurance_level: AssuranceLevel,
) -> None:
    issued_at = datetime.now(UTC)
    base_policy = build_development_protected_candidate_risk_recovery_policy(
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
async def test_persisted_completion_excludes_candidate_specific_content() -> None:
    service, _, impact, policy, actor, assessor, _ = await completion_fixture()
    result = await create_completion(service, impact, policy, actor)
    persisted = GovernedProtectedModelInvocationService._normalize(asdict(result.record))
    assert isinstance(persisted, dict)
    serialized = str(persisted).lower()
    for private in (
        "repeat the approved read-only health observation",
        "entity.service.erp.application",
        "reference.evidence.runtime.health",
        "risk_dimensions",
        "trigger_conditions",
        "point_of_no_return",
        "candidate-1",
    ):
        assert private not in serialized
    assert isinstance(assessor, SyntheticTrustedProtectedCandidateRiskRecoveryAssessor)
    assert result.record.completion_id in assessor._vault


@pytest.mark.asyncio
async def test_postgres_completion_record_round_trip_is_metadata_only() -> None:
    service, _, impact, policy, actor, *_ = await completion_fixture()
    result = await create_completion(service, impact, policy, actor)
    payload = GovernedProtectedModelInvocationService._normalize(asdict(result.record))
    assert isinstance(payload, dict)
    restored = PostgreSQLProtectedCandidateRiskRecoveryRepository._record_to_domain(payload)
    assert restored == result.record


@pytest.mark.asyncio
async def test_api_result_hides_protected_completion_content_and_bindings() -> None:
    service, _, impact, policy, actor, *_ = await completion_fixture()
    result = await create_completion(service, impact, policy, actor)
    response = ProtectedCandidateRiskRecoveryResultData.from_domain(result).model_dump()
    record = response["completion"]
    manifest = response["manifest"]
    for private in (
        "claim_id",
        "consumer_subject_digest",
        "browser_session_binding_digest",
        "completion_authorization_digest",
        "protected_report_digest",
        "risk_dimensions",
        "candidate_entries",
        "evidence_references",
        "trigger_conditions",
        "recovery_strategy",
    ):
        assert private not in record
        assert private not in manifest
    assert record["risk_completed"] is True
    assert record["recommendation_complete"] is False
    assert manifest["candidate_count"] == 3


@pytest.mark.asyncio
async def test_permission_denial_precedes_claim_and_source_rehydration() -> None:
    service, repository, impact, policy, actor, assessor, permission = await completion_fixture(
        deny=True
    )
    with pytest.raises(
        ProtectedCandidateRiskRecoveryError,
        match="protected_candidate_risk_recovery_permission_denied",
    ):
        await create_completion(service, impact, policy, actor)
    assert permission.calls
    assert not repository._claims
    assert isinstance(assessor, SyntheticTrustedProtectedCandidateRiskRecoveryAssessor)
    assert not assessor.calls


@pytest.mark.asyncio
async def test_unavailable_production_boundary_leaves_claim_without_record() -> None:
    service, repository, impact, policy, actor, assessor, _ = await completion_fixture(
        unavailable=True
    )
    with pytest.raises(
        ProtectedCandidateRiskRecoveryError,
        match="protected_candidate_risk_recovery_assessor_unavailable",
    ):
        await create_completion(service, impact, policy, actor)
    assert repository._claims
    assert not repository._records
    assert isinstance(assessor, UnavailableTrustedProtectedCandidateRiskRecoveryAssessor)


def test_input_schema_forbids_caller_shaped_risk_and_recovery() -> None:
    payload = {
        "impact_digest": "a" * 64,
        "completion_policy_id": "protected-candidate-risk-recovery-policy.development",
        "completion_policy_digest": "b" * 64,
        "purpose": "Complete exact protected candidate risk and recovery evidence.",
        "acknowledged_estimates_are_not_guarantees": True,
        "acknowledged_unknowns_cannot_lower_risk": True,
        "acknowledged_no_preference_or_operational_authority": True,
        "risk": "low",
        "duration_minutes": 5,
        "rollback": "caller supplied",
    }
    with pytest.raises(ValidationError):
        ProtectedCandidateRiskRecoveryInput.model_validate(payload)
