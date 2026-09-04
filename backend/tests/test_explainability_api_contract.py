from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest

from atlas.modules.explainability.domain.api_contract import (
    ApiExplanationContract,
    build_api_explanation_contract,
)
from atlas.modules.explainability.domain.confidence import ConfidenceExplanation
from atlas.modules.explainability.domain.models import (
    AudienceProfile,
    EvidenceLink,
    Explanation,
    ExplanationChannel,
    ExplanationDetailLevel,
)
from atlas.modules.explainability.domain.policy_denial import explain_policy_denial
from atlas.modules.guardrails.domain.reasoning_guardrails import ConfidenceLevel
from atlas.modules.policy_engine.domain.models import PolicyDecision, PolicyDecisionOutcome

NOW = datetime(2026, 9, 4, 12, 0, tzinfo=UTC)


def evidence_link(**overrides: object) -> EvidenceLink:
    defaults: dict[str, object] = {
        "reference": "evidence.example",
        "source": "health-check.example",
        "version": "1",
        "target_id": "target.example",
        "observed_at": NOW,
        "authority": "vendor-documented",
        "applicability": "storage.health",
    }
    defaults.update(overrides)
    return EvidenceLink(**defaults)  # type: ignore[arg-type]


def explanation(**overrides: object) -> Explanation:
    defaults: dict[str, object] = {
        "explanation_id": "explanation.example",
        "version": 1,
        "created_at": NOW,
        "freshness_boundary": NOW + timedelta(hours=1),
        "source_artifact_ids": ("rca-finding.example",),
        "source_artifact_versions": ("1",),
        "audience": AudienceProfile.INFRASTRUCTURE_ENGINEER,
        "channel": ExplanationChannel.API,
        "detail_level": ExplanationDetailLevel.L2_TECHNICAL,
        "summary": "Controller B reports a degraded status.",
        "claims": (),
        "evidence_links": (evidence_link(),),
        "unknowns": ("Whether the firmware bug also affects controller A.",),
        "alternatives": ("Replace controller B outright.",),
        "recommended_next_step": "Review controller B diagnostics.",
        "redacted": False,
    }
    defaults.update(overrides)
    return Explanation(**defaults)  # type: ignore[arg-type]


def confidence(**overrides: object) -> ConfidenceExplanation:
    defaults: dict[str, object] = {
        "category": ConfidenceLevel.HIGH,
        "category_definition": "High confidence: multiple independent, current signals agree.",
        "supporting_factors": ("Matches a known, resolved fault pattern.",),
        "limiting_factors": (),
        "remaining_alternatives": (),
        "missing_or_conflicting_evidence": (),
        "what_would_change_the_category": "A repeat occurrence after the fix would lower it.",
        "is_confirmed": False,
        "domain_criteria_met": False,
    }
    defaults.update(overrides)
    return ConfidenceExplanation(**defaults)  # type: ignore[arg-type]


def decision(**overrides: object) -> PolicyDecision:
    defaults: dict[str, object] = {
        "decision_id": "decision.example",
        "decided_at": NOW,
        "outcome": PolicyDecisionOutcome.REQUIRE_APPROVAL,
        "reasons": (),
        "decision_request_id": "decision-request.example",
        "correlation_id": "correlation.example",
        "actor_id": "actor.example",
        "operation_id": "operation.restart-controller",
        "non_overridable_rule_references": (),
        "evaluated_policy_set_versions": (),
        "additional_conditions": (),
    }
    defaults.update(overrides)
    return PolicyDecision(**defaults)  # type: ignore[arg-type]


def test_build_api_explanation_contract_carries_typed_claims_and_evidence() -> None:
    contract = build_api_explanation_contract(
        explanation(),
        confidence=confidence(),
        risk_impact=None,
        policy=None,
        required_human_review=False,
    )
    assert contract.explanation_id == "explanation.example"
    assert contract.explanation_version == 1
    assert contract.evidence_links[0].reference == "evidence.example"
    assert contract.alternatives == ("Replace controller B outright.",)
    assert contract.unknowns == ("Whether the firmware bug also affects controller A.",)


def test_build_api_explanation_contract_carries_source_artifact_versions() -> None:
    contract = build_api_explanation_contract(
        explanation(),
        confidence=confidence(),
        risk_impact=None,
        policy=None,
        required_human_review=False,
    )
    assert contract.source_artifact_ids == ("rca-finding.example",)
    assert contract.source_artifact_versions == ("1",)


def test_build_api_explanation_contract_carries_a_typed_policy_outcome_not_prose() -> None:
    policy = explain_policy_denial(
        decision(),
        requested_operation="restart controller B",
        is_eligible_for_detailed_view=False,
    )
    contract = build_api_explanation_contract(
        explanation(),
        confidence=confidence(),
        risk_impact=None,
        policy=policy,
        required_human_review=True,
    )
    assert contract.policy is not None
    assert contract.policy.outcome is PolicyDecisionOutcome.REQUIRE_APPROVAL
    assert contract.required_human_review is True


def test_build_api_explanation_contract_rejects_a_non_api_explanation() -> None:
    with pytest.raises(ValueError, match="API-channel"):
        build_api_explanation_contract(
            explanation(channel=ExplanationChannel.CHAT),
            confidence=confidence(),
            risk_impact=None,
            policy=None,
            required_human_review=False,
        )


def _contract(**overrides: object) -> ApiExplanationContract:
    base = build_api_explanation_contract(
        explanation(),
        confidence=confidence(),
        risk_impact=None,
        policy=None,
        required_human_review=False,
    )
    defaults: dict[str, object] = {
        "explanation_id": base.explanation_id,
        "explanation_version": base.explanation_version,
        "claims": base.claims,
        "evidence_links": base.evidence_links,
        "confidence": base.confidence,
        "alternatives": base.alternatives,
        "unknowns": base.unknowns,
        "risk_impact": base.risk_impact,
        "policy": base.policy,
        "required_human_review": base.required_human_review,
        "source_artifact_ids": base.source_artifact_ids,
        "source_artifact_versions": base.source_artifact_versions,
    }
    defaults.update(overrides)
    return ApiExplanationContract(**defaults)  # type: ignore[arg-type]


def test_rejects_non_positive_explanation_version() -> None:
    with pytest.raises(ValueError, match="positive explanation version"):
        _contract(explanation_version=0)


def test_rejects_mismatched_source_artifact_id_and_version_counts() -> None:
    with pytest.raises(ValueError, match="exactly one recorded version"):
        _contract(source_artifact_ids=("a", "b"), source_artifact_versions=("1",))
