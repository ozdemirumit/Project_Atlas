from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest

from atlas.modules.explainability.domain.investigation_presentation import (
    ClockQuality,
    DiagnosticCheckResult,
    EvidenceFilterCriteria,
    InvestigationAnnotation,
    InvestigationAnnotationKind,
    InvestigationPresentation,
    RelatedArtifact,
    RelatedArtifactKind,
    TimelineEntry,
    TopologyImpact,
    VersionComparison,
    filter_evidence_for_investigation,
)
from atlas.modules.explainability.domain.models import EvidenceLink, ExplanationClaim
from atlas.modules.guardrails.domain.reasoning_guardrails import ClaimType, ConfidenceLevel

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


def claim(**overrides: object) -> ExplanationClaim:
    defaults: dict[str, object] = {
        "claim_id": "explanation-claim.example",
        "claim_type": ClaimType.FACT,
        "statement": "The controller reports a degraded status.",
        "confidence": ConfidenceLevel.HIGH,
        "evidence_references": ("evidence.example",),
        "contradicting_evidence_references": (),
    }
    defaults.update(overrides)
    return ExplanationClaim(**defaults)  # type: ignore[arg-type]


def test_timeline_entry_rejects_naive_datetime() -> None:
    with pytest.raises(ValueError, match="timezone-aware"):
        TimelineEntry(
            occurred_at=NOW.replace(tzinfo=None),
            source="syslog",
            clock_quality=ClockQuality.SYNCHRONIZED,
            description="Controller B logged a degraded event.",
        )


def test_topology_impact_rejects_a_target_marked_both_affected_and_unaffected() -> None:
    with pytest.raises(ValueError, match="cannot be both"):
        TopologyImpact(affected_target_ids=("target.a",), unaffected_target_ids=("target.a",))


def test_topology_impact_allows_disjoint_sets() -> None:
    impact = TopologyImpact(affected_target_ids=("target.a",), unaffected_target_ids=("target.b",))
    assert impact.affected_target_ids == ("target.a",)


def test_diagnostic_check_result_requires_a_summary() -> None:
    with pytest.raises(ValueError, match="summary"):
        DiagnosticCheckResult(check_id="diagnostic-check.example", passed=True, summary="   ")


def test_version_comparison_requires_both_versions() -> None:
    with pytest.raises(ValueError, match="both a previous and current version"):
        VersionComparison(
            artifact_id="rca-finding.example",
            previous_version="1",
            current_version="   ",
            human_corrections=(),
        )


def test_related_artifact_requires_a_summary() -> None:
    with pytest.raises(ValueError, match="summary"):
        RelatedArtifact(
            kind=RelatedArtifactKind.INCIDENT, artifact_id="incident.example", summary="   "
        )


def test_filter_evidence_by_source() -> None:
    links = (
        evidence_link(reference="evidence.a", source="health-check.example"),
        evidence_link(reference="evidence.b", source="syslog.example"),
    )
    filtered = filter_evidence_for_investigation(
        links, (), criteria=EvidenceFilterCriteria(source="syslog.example")
    )
    assert [link.reference for link in filtered] == ["evidence.b"]


def test_filter_evidence_by_target() -> None:
    links = (
        evidence_link(reference="evidence.a", target_id="target.a"),
        evidence_link(reference="evidence.b", target_id="target.b"),
    )
    filtered = filter_evidence_for_investigation(
        links, (), criteria=EvidenceFilterCriteria(target_id="target.b")
    )
    assert [link.reference for link in filtered] == ["evidence.b"]


def test_filter_evidence_by_time_window() -> None:
    links = (
        evidence_link(reference="evidence.a", observed_at=NOW - timedelta(hours=2)),
        evidence_link(reference="evidence.b", observed_at=NOW),
    )
    filtered = filter_evidence_for_investigation(
        links, (), criteria=EvidenceFilterCriteria(observed_after=NOW - timedelta(hours=1))
    )
    assert [link.reference for link in filtered] == ["evidence.b"]


def test_filter_evidence_by_authority() -> None:
    links = (
        evidence_link(reference="evidence.a", authority="vendor-documented"),
        evidence_link(reference="evidence.b", authority="self-reported"),
    )
    filtered = filter_evidence_for_investigation(
        links, (), criteria=EvidenceFilterCriteria(authority="self-reported")
    )
    assert [link.reference for link in filtered] == ["evidence.b"]


def test_filter_evidence_by_conflict_includes_both_sides_of_a_contradiction() -> None:
    links = (
        evidence_link(reference="evidence.a"),
        evidence_link(reference="evidence.b"),
        evidence_link(reference="evidence.c"),
    )
    claims = (
        claim(
            evidence_references=("evidence.a",),
            contradicting_evidence_references=("evidence.b",),
        ),
    )
    filtered = filter_evidence_for_investigation(
        links, claims, criteria=EvidenceFilterCriteria(only_conflicting=True)
    )
    assert {link.reference for link in filtered} == {"evidence.a", "evidence.b"}


def test_filter_evidence_by_conflict_excludes_uncontested_claims() -> None:
    links = (evidence_link(reference="evidence.a"),)
    claims = (claim(evidence_references=("evidence.a",), contradicting_evidence_references=()),)
    filtered = filter_evidence_for_investigation(
        links, claims, criteria=EvidenceFilterCriteria(only_conflicting=True)
    )
    assert filtered == ()


def test_investigation_annotation_claim_challenge_requires_a_claim_id() -> None:
    with pytest.raises(ValueError, match="claim_id"):
        InvestigationAnnotation(
            annotation_id="investigation-annotation.example",
            kind=InvestigationAnnotationKind.CLAIM_CHALLENGE,
            claim_id=None,
            recorded_by="subject.reviewer",
            recorded_at=NOW,
            note="This claim seems wrong given the newer firmware advisory.",
        )


def test_investigation_annotation_mapping_issue_does_not_require_a_claim_id() -> None:
    annotation = InvestigationAnnotation(
        annotation_id="investigation-annotation.example",
        kind=InvestigationAnnotationKind.MAPPING_ISSUE,
        claim_id=None,
        recorded_by="subject.reviewer",
        recorded_at=NOW,
        note="This target appears mapped to the wrong site.",
    )
    assert annotation.claim_id is None


def test_investigation_annotation_requires_a_note() -> None:
    with pytest.raises(ValueError, match="note"):
        InvestigationAnnotation(
            annotation_id="investigation-annotation.example",
            kind=InvestigationAnnotationKind.EVIDENCE_ADDITION,
            claim_id=None,
            recorded_by="subject.reviewer",
            recorded_at=NOW,
            note="   ",
        )


def test_investigation_presentation_aggregates_its_parts() -> None:
    presentation = InvestigationPresentation(
        timeline=(
            TimelineEntry(
                occurred_at=NOW,
                source="syslog",
                clock_quality=ClockQuality.SYNCHRONIZED,
                description="Controller B logged a degraded event.",
            ),
        ),
        topology=TopologyImpact(
            affected_target_ids=("target.a",), unaffected_target_ids=("target.b",)
        ),
        claims=(claim(),),
        diagnostic_results=(
            DiagnosticCheckResult(
                check_id="diagnostic-check.example", passed=True, summary="Path healthy."
            ),
        ),
        version_comparisons=(
            VersionComparison(
                artifact_id="rca-finding.example",
                previous_version="1",
                current_version="2",
                human_corrections=(),
            ),
        ),
        related_artifacts=(
            RelatedArtifact(
                kind=RelatedArtifactKind.INCIDENT,
                artifact_id="incident.example",
                summary="Related incident from last quarter.",
            ),
        ),
        annotations=(),
    )
    assert len(presentation.timeline) == 1
    assert presentation.topology.affected_target_ids == ("target.a",)
