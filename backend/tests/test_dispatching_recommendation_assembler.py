from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import cast

from atlas.modules.rca.domain.models import (
    ConfirmationLevel,
    HumanReview,
    ImpactScope,
    IncidentReference,
    ProvisionalCauseStatement,
    RcaCase,
    RcaCaseState,
    RcaSeverity,
    ReviewStatus,
)
from atlas.modules.recommendations.adapters.dispatching import DispatchingRecommendationAssembler
from atlas.modules.recommendations.domain.models import (
    RecommendationArtifact,
    RecommendationRequest,
)

NOW = datetime(2026, 8, 28, 12, 0, tzinfo=UTC)


def _case(data_profile: str) -> RcaCase:
    return RcaCase(
        case_id="rca_test",
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
        target_id="asset.storage.test",
        window_start=NOW - timedelta(hours=1),
        window_end=NOW,
        fault_families=(),
        symptoms=(),
        impact_scope=ImpactScope(
            affected_entities=(),
            possibly_affected_services=(),
            explicitly_unaffected_entities=("asset.storage.test",),
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
        data_profile=data_profile,
        root_cause_confirmed=False,
        safety_notice="Decision support only.",
    )


def _request() -> RecommendationRequest:
    return RecommendationRequest(
        source_case_id="rca_test",
        source_case_version=1,
        target_id="asset.storage.test",
        decision_question="test",
        accountable_audience="Storage Operations",
        horizon="test",
        constraints=(),
        maximum_capability_class="C1",
        max_options=5,
    )


class StubAssembler:
    def __init__(self) -> None:
        self.sentinel = cast(RecommendationArtifact, object())
        self.calls = 0

    def build(
        self, request: RecommendationRequest, source_case: RcaCase, **kwargs: object
    ) -> RecommendationArtifact:
        del request, source_case, kwargs
        self.calls += 1
        return self.sentinel


def test_dispatches_by_source_case_data_profile() -> None:
    hitachi = StubAssembler()
    huawei = StubAssembler()
    default = StubAssembler()
    assembler = DispatchingRecommendationAssembler(
        assemblers_by_data_profile={
            "configured_hitachi_read_only": hitachi,
            "configured_huawei_dorado_read_only": huawei,
        },
        default=default,
    )

    result = assembler.build(
        _request(),
        _case("configured_huawei_dorado_read_only"),
        requested_by="subject.development.operator",
        organization_id="organization.atlas.local",
        environment_id="environment.development",
        site_id="site.local",
        created_at=NOW,
        version=1,
        prior_version_id=None,
    )

    assert result is huawei.sentinel
    assert huawei.calls == 1
    assert hitachi.calls == 0
    assert default.calls == 0


def test_falls_back_to_default_for_an_unrecognized_data_profile() -> None:
    hitachi = StubAssembler()
    default = StubAssembler()
    assembler = DispatchingRecommendationAssembler(
        assemblers_by_data_profile={"configured_hitachi_read_only": hitachi},
        default=default,
    )

    result = assembler.build(
        _request(),
        _case("synthetic_lab"),
        requested_by="subject.development.operator",
        organization_id="organization.atlas.local",
        environment_id="environment.development",
        site_id="site.local",
        created_at=NOW,
        version=1,
        prior_version_id=None,
    )

    assert result is default.sentinel
    assert default.calls == 1
    assert hitachi.calls == 0
