from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest

from atlas.modules.decision_engine.domain.hypotheses import DecisionConfidenceCategory
from atlas.modules.decision_engine.domain.models import DecisionRequest
from atlas.modules.decision_engine.domain.record import (
    DecisionComponentVersions,
    DecisionRecord,
    DecisionReviewState,
    DecisionSupersessionState,
)

NOW = datetime(2026, 9, 4, 12, 0, tzinfo=UTC)


def request(**overrides: object) -> DecisionRequest:
    defaults: dict[str, object] = {
        "request_id": "decision-request.example",
        "workflow_id": "workflow.example",
        "requesting_identity": "subject.requester",
        "authorized_scope_reference": "authorization.example",
        "decision_type": "root_cause_diagnosis",
        "question": "Why did controller B degrade?",
        "target_ids": ("target.example",),
        "service_ids": ("service.file-shares",),
        "environment_id": "environment.production",
        "time_window_start": NOW - timedelta(hours=2),
        "time_window_end": NOW,
        "required_evidence_domains": ("health_check",),
        "required_output_schema": "decision-record.v1",
        "deadline": None,
        "required_freshness_seconds": 300,
        "applicable_domain": "storage",
        "applicable_product_versions": ("6.1.x",),
    }
    defaults.update(overrides)
    return DecisionRequest(**defaults)  # type: ignore[arg-type]


def record(**overrides: object) -> DecisionRecord:
    defaults: dict[str, object] = {
        "decision_id": "decision-record.example",
        "version": 1,
        "prior_version_id": None,
        "request": request(),
        "workflow_id": "workflow.example",
        "created_at": NOW,
        "valid_until": NOW + timedelta(hours=4),
        "target_ids": ("target.example",),
        "scope": "Single storage controller within organization.example.",
        "evidence_package_version": "decision-evidence-package.example:v1",
        "findings": (),
        "hypotheses": (),
        "confidence_category": DecisionConfidenceCategory.MEDIUM,
        "confidence_uncertainty_note": (
            "One independent evidence unit supports the leading hypothesis."
        ),
        "impact_assessment": None,
        "graph_freshness_statement": "Graph snapshot generated within the last five minutes.",
        "recommendation_candidates": (),
        "alternatives": (),
        "policy_handoffs": (),
        "required_approvals": (),
        "component_versions": DecisionComponentVersions(
            model_version="model.v3",
            rule_version="rule.v1",
            agent_version="decision-agent.v1",
            prompt_version=None,
            schema_version="decision-record.v1",
        ),
        "review_state": DecisionReviewState.UNREVIEWED,
        "supersession_state": DecisionSupersessionState.CURRENT,
        "superseded_by_decision_id": None,
    }
    defaults.update(overrides)
    return DecisionRecord(**defaults)  # type: ignore[arg-type]


def test_a_well_formed_record_constructs_cleanly() -> None:
    example = record()
    assert example.version == 1


def test_version_one_cannot_carry_a_prior_version_id() -> None:
    with pytest.raises(ValueError, match="cannot have a prior version"):
        record(version=1, prior_version_id="decision-record.prior")


def test_version_beyond_one_requires_a_prior_version_id() -> None:
    with pytest.raises(ValueError, match="requires prior_version_id"):
        record(version=2, prior_version_id=None)


def test_version_beyond_one_constructs_with_a_prior_version_id() -> None:
    example = record(version=2, prior_version_id="decision-record.example.v1")
    assert example.prior_version_id == "decision-record.example.v1"


def test_rejects_non_positive_version() -> None:
    with pytest.raises(ValueError, match="positive version"):
        record(version=0)


def test_rejects_naive_created_at() -> None:
    with pytest.raises(ValueError, match="timezone-aware"):
        record(created_at=NOW.replace(tzinfo=None))


def test_rejects_naive_valid_until() -> None:
    with pytest.raises(ValueError, match="timezone-aware"):
        record(valid_until=NOW.replace(tzinfo=None))


def test_valid_until_may_be_none() -> None:
    example = record(valid_until=None)
    assert example.valid_until is None


def test_rejects_blank_scope() -> None:
    with pytest.raises(ValueError, match="scope statement"):
        record(scope="   ")


def test_rejects_blank_graph_freshness_statement() -> None:
    with pytest.raises(ValueError, match="graph-freshness statement"):
        record(graph_freshness_statement="   ")


def test_superseded_state_requires_the_superseding_decision() -> None:
    with pytest.raises(ValueError, match="requires the decision that superseded it"):
        record(
            supersession_state=DecisionSupersessionState.SUPERSEDED,
            superseded_by_decision_id=None,
        )


def test_superseded_state_constructs_with_the_superseding_decision() -> None:
    example = record(
        supersession_state=DecisionSupersessionState.SUPERSEDED,
        superseded_by_decision_id="decision-record.next",
    )
    assert example.superseded_by_decision_id == "decision-record.next"


def test_current_state_cannot_carry_a_superseded_by_reference() -> None:
    with pytest.raises(ValueError, match="only meaningful for a SUPERSEDED"):
        record(
            supersession_state=DecisionSupersessionState.CURRENT,
            superseded_by_decision_id="decision-record.next",
        )


def test_record_is_frozen() -> None:
    example = record()
    with pytest.raises(AttributeError):
        example.version = 2  # type: ignore[misc]
