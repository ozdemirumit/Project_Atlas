from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest

from atlas.modules.rca.adapters.chained import ChainedRcaAssembler
from atlas.modules.rca.domain.models import (
    ConfirmationLevel,
    HumanReview,
    ImpactScope,
    IncidentReference,
    ProvisionalCauseStatement,
    RcaCase,
    RcaCaseState,
    RcaCreateRequest,
    RcaSeverity,
    ReviewStatus,
)

NOW = datetime(2026, 8, 28, 12, 0, tzinfo=UTC)


def _case(case_id: str, target_id: str) -> RcaCase:
    return RcaCase(
        case_id=case_id,
        version=1,
        prior_version_id=None,
        owner="Storage Operations",
        requested_by="subject.development.operator",
        state=RcaCaseState.INCONCLUSIVE,
        severity=RcaSeverity.UNKNOWN,
        created_at=NOW,
        updated_at=NOW,
        incident_references=(
            IncidentReference(
                reference_type="incident", reference_id="INC-1", authority="user-provided"
            ),
        ),
        user_report="test",
        expected_behavior="test",
        actual_behavior="test",
        organization_id="organization.atlas.local",
        environment_id="environment.development",
        site_id="site.local",
        target_id=target_id,
        window_start=NOW - timedelta(hours=1),
        window_end=NOW,
        fault_families=(),
        symptoms=(),
        impact_scope=ImpactScope(
            affected_entities=(),
            possibly_affected_services=(),
            explicitly_unaffected_entities=(target_id,),
            current_impact="none",
            business_criticality="unknown",
            impact_confirmed=False,
            limitations=(),
        ),
        source_investigation_artifact_id="investigation.rca.test",
        source_investigation_version=1,
        evidence=(),
        timeline=(),
        hypotheses=(),
        findings=(),
        assumptions=(),
        unknowns=(),
        conflicts=(),
        evidence_gaps=(),
        blocker="none",
        safest_next_step="none",
        provisional_statement=ProvisionalCauseStatement(
            statement="test",
            confirmation_level=ConfirmationLevel.INCONCLUSIVE,
            supporting_evidence=(),
            contradicting_evidence=(),
            residual_uncertainty=(),
            alternatives_not_ruled_out=(),
            prevention_or_verification_implication="none",
        ),
        human_review=HumanReview(
            status=ReviewStatus.PENDING,
            reviewer_id=None,
            reviewed_at=None,
            decision_reason=None,
            domain_confirmation_criterion=None,
        ),
        component_versions=("rca-case-contract.v1",),
        data_profile="configured_test_read_only",
        root_cause_confirmed=False,
        safety_notice="Decision support only.",
    )


def _request(target_id: str) -> RcaCreateRequest:
    return RcaCreateRequest(
        incident_id="INC-1",
        target_id=target_id,
        user_report="test",
        expected_behavior="test",
        actual_behavior="test",
        window_start=NOW - timedelta(hours=1),
        window_end=NOW,
        max_evidence_records=12,
    )


class StubAssembler:
    def __init__(self, *, recognized_target_id: str, case_id: str) -> None:
        self._recognized_target_id = recognized_target_id
        self._case_id = case_id
        self.calls = 0

    async def build(self, request: RcaCreateRequest, **kwargs: object) -> RcaCase:
        self.calls += 1
        if request.target_id != self._recognized_target_id:
            raise KeyError(request.target_id)
        return _case(self._case_id, request.target_id)


@pytest.mark.asyncio
async def test_returns_the_first_assembler_that_recognizes_the_target() -> None:
    first = StubAssembler(recognized_target_id="asset.storage.a", case_id="rca_a")
    second = StubAssembler(recognized_target_id="asset.storage.b", case_id="rca_b")
    chain = ChainedRcaAssembler(assemblers=(first, second))

    case = await chain.build(
        _request("asset.storage.b"),
        requested_by="subject.development.operator",
        organization_id="organization.atlas.local",
        environment_id="environment.development",
        site_id="site.local",
        created_at=NOW,
        version=1,
        prior_version_id=None,
    )

    assert case.case_id == "rca_b"
    assert first.calls == 1
    assert second.calls == 1


@pytest.mark.asyncio
async def test_raises_key_error_when_no_assembler_recognizes_the_target() -> None:
    first = StubAssembler(recognized_target_id="asset.storage.a", case_id="rca_a")
    second = StubAssembler(recognized_target_id="asset.storage.b", case_id="rca_b")
    chain = ChainedRcaAssembler(assemblers=(first, second))

    with pytest.raises(KeyError):
        await chain.build(
            _request("asset.storage.unknown"),
            requested_by="subject.development.operator",
            organization_id="organization.atlas.local",
            environment_id="environment.development",
            site_id="site.local",
            created_at=NOW,
            version=1,
            prior_version_id=None,
        )


def test_requires_at_least_one_assembler() -> None:
    with pytest.raises(ValueError, match="at least one assembler"):
        ChainedRcaAssembler(assemblers=())
