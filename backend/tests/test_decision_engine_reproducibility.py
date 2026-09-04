from __future__ import annotations

import pytest

from atlas.modules.decision_engine.domain.record import DecisionSupersessionState
from atlas.modules.decision_engine.domain.reproducibility import (
    ReproducibilityManifest,
    VersionTrigger,
    can_use_as_current_approval_packet,
    exact_model_output_reproduction_is_promised,
    requires_new_decision_version,
    user_annotation_can_rewrite_original_evidence,
)


def manifest(**overrides: object) -> ReproducibilityManifest:
    defaults: dict[str, object] = {
        "evidence_package_reference": "decision-evidence-package.example:v1",
        "decision_request_reference": "decision-request.example",
        "request_schema_version": "decision-record.v1",
        "rule_and_configuration_versions": ("rule.v1",),
        "graph_snapshot_reference": "graph-snapshot.example",
        "agent_identity": "decision-agent.v1",
        "prompt_identity": None,
        "model_identity": "model.v3",
        "endpoint_identity": None,
        "retrieval_trace_reference": None,
        "policy_input_reference": "policy-decision-request.example",
        "policy_result_reference": "policy-decision.example",
    }
    defaults.update(overrides)
    return ReproducibilityManifest(**defaults)  # type: ignore[arg-type]


def test_a_well_formed_manifest_constructs_cleanly() -> None:
    example = manifest()
    assert example.model_identity == "model.v3"


def test_rejects_blank_evidence_package_reference() -> None:
    with pytest.raises(ValueError, match="evidence package reference"):
        manifest(evidence_package_reference="   ")


def test_rejects_blank_decision_request_reference() -> None:
    with pytest.raises(ValueError, match="decision request reference"):
        manifest(decision_request_reference="   ")


def test_rejects_blank_request_schema_version() -> None:
    with pytest.raises(ValueError, match="request schema version"):
        manifest(request_schema_version="   ")


def test_exact_model_output_reproduction_is_never_promised() -> None:
    assert exact_model_output_reproduction_is_promised() is False


def test_requires_new_decision_version_true_for_any_trigger() -> None:
    assert requires_new_decision_version(frozenset({VersionTrigger.NEW_EVIDENCE_PACKAGE})) is True


def test_requires_new_decision_version_false_for_no_triggers() -> None:
    assert requires_new_decision_version(frozenset()) is False


def test_user_annotation_can_never_rewrite_original_evidence() -> None:
    assert user_annotation_can_rewrite_original_evidence() is False


def test_can_use_as_current_approval_packet_true_for_current() -> None:
    assert (
        can_use_as_current_approval_packet(supersession_state=DecisionSupersessionState.CURRENT)
        is True
    )


def test_can_use_as_current_approval_packet_false_for_expired() -> None:
    assert (
        can_use_as_current_approval_packet(supersession_state=DecisionSupersessionState.EXPIRED)
        is False
    )


def test_can_use_as_current_approval_packet_false_for_superseded() -> None:
    assert (
        can_use_as_current_approval_packet(supersession_state=DecisionSupersessionState.SUPERSEDED)
        is False
    )
