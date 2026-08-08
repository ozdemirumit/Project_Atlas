from __future__ import annotations

import json
from dataclasses import asdict, replace
from datetime import datetime

from atlas.modules.ai.application.protected_candidate_risk_recovery_completion_ports import (
    ProtectedCandidateRiskRecoveryError,
)
from atlas.modules.ai.application.protected_model_invocation import (
    GovernedProtectedModelInvocationService,
)
from atlas.modules.ai.domain.protected_candidate_impact_enrichment import (
    ProtectedCandidateImpactReport,
)
from atlas.modules.ai.domain.protected_candidate_risk_recovery_completion import (
    ProtectedCandidateDurationEstimate,
    ProtectedCandidateInterruptionEstimate,
    ProtectedCandidateRecoveryAssessment,
    ProtectedCandidateRiskDimension,
    ProtectedCandidateRiskRecoveryEntry,
    ProtectedCandidateRiskRecoveryInstruction,
    ProtectedCandidateRiskRecoveryReceipt,
    ProtectedCandidateRiskRecoveryRecord,
    ProtectedCandidateRiskRecoveryReport,
    ProtectedOperationalEvidenceItem,
    ProtectedOperationalEvidenceSnapshot,
)
from atlas.modules.ai.domain.protected_recommendation_candidate_generation import (
    ProtectedRecommendationCandidate,
    ProtectedRecommendationCandidateSet,
)

RISK_ORDER = {"low": 0, "moderate": 1, "high": 2, "critical": 3, "unknown": 4}


def build_development_operational_evidence_snapshot(
    *,
    organization_id: str,
    environment_id: str,
    generated_at: datetime,
    expires_at: datetime,
) -> ProtectedOperationalEvidenceSnapshot:
    digest = GovernedProtectedModelInvocationService._digest
    payload = GovernedProtectedModelInvocationService._payload
    definitions = (
        (
            "evidence.capability.read-only",
            "capability-semantics",
            "declared",
            "capability.c1-read-only",
            "no-infrastructure-mutation",
            1,
        ),
        (
            "evidence.runtime.health",
            "runtime-health",
            "observed",
            "asset.storage.lab.b28",
            "warning-observed-system-serving",
            1,
        ),
        (
            "evidence.redundancy.current",
            "redundancy",
            "observed",
            "asset.storage.lab.b28",
            "dual-controller-paths-observed",
            1,
        ),
        (
            "evidence.vendor.procedure",
            "vendor-procedure",
            "declared",
            "vendor.hitachi.opscenter",
            "read-and-support-package-applicable",
            1,
        ),
        (
            "evidence.duration.history",
            "historical-duration",
            "historical",
            "capability.c1-read-only",
            "bounded-read-and-review-ranges",
            12,
        ),
        (
            "evidence.service.criticality",
            "service-criticality",
            "declared",
            "service.erp",
            "business-critical-no-change-preferred",
            1,
        ),
        (
            "evidence.data.protection",
            "data-protection",
            "observed",
            "asset.storage.lab.b28",
            "current-protection-observed-no-write-authority",
            1,
        ),
        (
            "evidence.recovery.baseline",
            "recovery",
            "simulated",
            "capability.c1-read-only",
            "stop-read-preserve-prior-state",
            3,
        ),
    )
    items: list[ProtectedOperationalEvidenceItem] = []
    for evidence_id, kind, assertion, scope, value, sample_count in definitions:
        item = ProtectedOperationalEvidenceItem(
            evidence_id=evidence_id,
            evidence_kind=kind,
            assertion_kind=assertion,
            subject_scope=scope,
            value=value,
            evidence_references=(f"reference.{evidence_id}",),
            sample_count=sample_count,
            observed_at=generated_at,
            expires_at=expires_at,
            canonical_digest="0" * 64,
        )
        items.append(replace(item, canonical_digest=digest(payload(item))))
    snapshot = ProtectedOperationalEvidenceSnapshot(
        snapshot_id="snapshot.operational-evidence.lab.001",
        schema_version="atlas.protected-operational-evidence-snapshot.v1",
        version=1,
        organization_id=organization_id,
        environment_id=environment_id,
        source_id="protected-operational-evidence-source.synthetic",
        classification="classification.internal",
        freshness="fresh",
        completeness="bounded-complete",
        items=tuple(items),
        gaps=(
            "No production failover exercise is represented by the synthetic evidence snapshot.",
        ),
        unknowns=(
            "Production workload variance remains unknown outside the bounded evidence ranges.",
        ),
        coverage_digest=digest(tuple(item.canonical_digest for item in items)),
        generated_at=generated_at,
        expires_at=expires_at,
        canonical_digest="0" * 64,
    )
    return replace(snapshot, canonical_digest=digest(payload(snapshot)))


class SyntheticTrustedProtectedCandidateRiskRecoveryAssessor:
    def __init__(self) -> None:
        self.calls: list[ProtectedCandidateRiskRecoveryInstruction] = []
        self._vault: dict[
            str,
            tuple[ProtectedCandidateRiskRecoveryReceipt, ProtectedCandidateRiskRecoveryReport],
        ] = {}

    async def complete(
        self,
        instruction: ProtectedCandidateRiskRecoveryInstruction,
        candidate_set: ProtectedRecommendationCandidateSet,
        impact_report: ProtectedCandidateImpactReport,
        evidence_snapshot: ProtectedOperationalEvidenceSnapshot,
    ) -> tuple[ProtectedCandidateRiskRecoveryReceipt, ProtectedCandidateRiskRecoveryReport]:
        self.calls.append(instruction)
        digest = GovernedProtectedModelInvocationService._digest
        payload = GovernedProtectedModelInvocationService._payload
        if (
            candidate_set.candidate_set_id != instruction.candidate_set_id
            or candidate_set.canonical_digest != instruction.candidate_set_digest
            or impact_report.impact_analysis_id != instruction.impact_analysis_id
            or impact_report.canonical_digest != instruction.impact_digest
            or impact_report.candidate_set_digest != candidate_set.canonical_digest
            or evidence_snapshot.snapshot_id != instruction.evidence_snapshot_id
            or evidence_snapshot.canonical_digest != instruction.evidence_snapshot_digest
            or evidence_snapshot.canonical_digest != digest(payload(evidence_snapshot))
            or not evidence_snapshot.gaps
            or not evidence_snapshot.unknowns
        ):
            raise ProtectedCandidateRiskRecoveryError(
                "protected_candidate_risk_recovery_source_invalid"
            )
        impact_by_candidate = {entry.candidate_id: entry for entry in impact_report.entries}
        references = tuple(item.evidence_id for item in evidence_snapshot.items)
        entries: list[ProtectedCandidateRiskRecoveryEntry] = []
        for candidate in candidate_set.candidates:
            impact = impact_by_candidate.get(candidate.candidate_id)
            if impact is None or impact.candidate_digest != candidate.canonical_digest:
                raise ProtectedCandidateRiskRecoveryError(
                    "protected_candidate_risk_recovery_source_invalid"
                )
            entries.append(
                self._entry(
                    candidate,
                    impact.canonical_digest,
                    instruction.required_risk_dimensions,
                    references,
                    len(impact.known_gaps) + len(evidence_snapshot.gaps),
                    len(impact.unknowns) + len(evidence_snapshot.unknowns),
                )
            )

        encoded = json.dumps(
            GovernedProtectedModelInvocationService._normalize(
                [asdict(entry) for entry in entries]
            ),
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")
        if (
            len(entries) > instruction.maximum_candidate_count
            or len(evidence_snapshot.items) > instruction.maximum_evidence_item_count
            or sum(entry.gap_count for entry in entries) > instruction.maximum_gap_count
            or sum(entry.unknown_count for entry in entries) > instruction.maximum_unknown_count
            or max(entry.work_duration.maximum_minutes for entry in entries)
            > instruction.maximum_duration_minutes
            or len(encoded) > instruction.maximum_output_bytes
        ):
            raise ProtectedCandidateRiskRecoveryError(
                "protected_candidate_risk_recovery_content_invalid"
            )

        risk_counts = {
            level: sum(entry.overall_risk == level for entry in entries) for level in RISK_ORDER
        }
        maximum_risk = max((entry.overall_risk for entry in entries), key=RISK_ORDER.__getitem__)
        coverage_digest = digest(
            [
                tuple(entry.candidate_id for entry in entries),
                tuple(entry.impact_entry_digest for entry in entries),
                evidence_snapshot.coverage_digest,
            ]
        )
        risk_digest = digest(
            tuple(
                (
                    entry.candidate_id,
                    entry.overall_risk,
                    tuple(d.level for d in entry.risk_dimensions),
                )
                for entry in entries
            )
        )
        duration_digest = digest(tuple(asdict(entry.work_duration) for entry in entries))
        interruption_digest = digest(tuple(asdict(entry.interruption) for entry in entries))
        recovery_digest = digest(tuple(asdict(entry.recovery) for entry in entries))
        unknown_digest = digest(
            [
                tuple(entry.unknown_count for entry in entries),
                evidence_snapshot.unknowns,
            ]
        )
        safety_digest = digest(
            [instruction.safety_profile_digest, maximum_risk, "no-preference-no-authority"]
        )
        report = ProtectedCandidateRiskRecoveryReport(
            completion_id=instruction.completion_id,
            schema_version=instruction.required_report_schema,
            version=1,
            impact_analysis_id=instruction.impact_analysis_id,
            impact_digest=instruction.impact_digest,
            candidate_set_id=instruction.candidate_set_id,
            candidate_set_digest=instruction.candidate_set_digest,
            policy_digest=instruction.policy_digest,
            evidence_snapshot_id=instruction.evidence_snapshot_id,
            evidence_snapshot_digest=instruction.evidence_snapshot_digest,
            entries=tuple(entries),
            coverage_digest=coverage_digest,
            risk_digest=risk_digest,
            duration_digest=duration_digest,
            interruption_digest=interruption_digest,
            recovery_digest=recovery_digest,
            unknown_digest=unknown_digest,
            safety_digest=safety_digest,
            byte_count=len(encoded),
            completed_at=instruction.requested_at,
            expires_at=instruction.expires_at,
            canonical_digest="0" * 64,
        )
        report = replace(report, canonical_digest=digest(payload(report)))
        cleanup_digest = digest([instruction.completion_id, "cleanup-verified"])
        interruption_possible_count = sum(
            entry.interruption.worst_maximum_minutes > 0 for entry in entries
        )
        recovery_feasible_count = sum(entry.recovery.feasibility == "feasible" for entry in entries)
        recovery_unknown_count = sum(entry.recovery.feasibility == "unknown" for entry in entries)
        recovery_blocked_count = sum(entry.recovery.feasibility == "blocked" for entry in entries)
        receipt = ProtectedCandidateRiskRecoveryReceipt(
            completion_id=instruction.completion_id,
            schema_version="atlas.protected-candidate-risk-recovery-receipt.v1",
            version=1,
            assessor_id="protected-candidate-risk-recovery-assessor.synthetic",
            attested_by="subject.protected-candidate-risk-recovery-assessor-attestor",
            impact_analysis_id=instruction.impact_analysis_id,
            impact_digest=instruction.impact_digest,
            candidate_set_id=instruction.candidate_set_id,
            candidate_set_digest=instruction.candidate_set_digest,
            completion_authorization_digest=instruction.completion_authorization_digest,
            policy_digest=instruction.policy_digest,
            evidence_snapshot_id=instruction.evidence_snapshot_id,
            evidence_snapshot_digest=instruction.evidence_snapshot_digest,
            report_digest=report.canonical_digest,
            coverage_digest=coverage_digest,
            risk_digest=risk_digest,
            duration_digest=duration_digest,
            interruption_digest=interruption_digest,
            recovery_digest=recovery_digest,
            unknown_digest=unknown_digest,
            safety_digest=safety_digest,
            cleanup_digest=cleanup_digest,
            candidate_count=len(entries),
            evidence_item_count=len(evidence_snapshot.items),
            low_risk_count=risk_counts["low"],
            moderate_risk_count=risk_counts["moderate"],
            high_risk_count=risk_counts["high"],
            critical_risk_count=risk_counts["critical"],
            unknown_risk_count=risk_counts["unknown"],
            maximum_risk=maximum_risk,
            interruption_possible_count=interruption_possible_count,
            recovery_feasible_count=recovery_feasible_count,
            recovery_unknown_count=recovery_unknown_count,
            recovery_blocked_count=recovery_blocked_count,
            work_minimum_minutes=min(entry.work_duration.minimum_minutes for entry in entries),
            work_maximum_minutes=max(entry.work_duration.maximum_minutes for entry in entries),
            interruption_minimum_minutes=min(
                entry.interruption.expected_minimum_minutes for entry in entries
            ),
            interruption_maximum_minutes=max(
                entry.interruption.worst_maximum_minutes for entry in entries
            ),
            recovery_minimum_minutes=min(
                entry.recovery.duration.minimum_minutes for entry in entries
            ),
            recovery_maximum_minutes=max(
                entry.recovery.duration.maximum_minutes for entry in entries
            ),
            gap_count=sum(entry.gap_count for entry in entries),
            unknown_count=sum(entry.unknown_count for entry in entries),
            byte_count=len(encoded),
            completed_at=instruction.requested_at,
            expires_at=instruction.expires_at,
            source_verified=True,
            evidence_verified=True,
            complete_candidate_coverage_verified=True,
            conservative_risk_floor_verified=True,
            ranges_bounded_verified=True,
            recovery_coverage_verified=True,
            no_preference_assigned=True,
            no_model_used=True,
            cleanup_verified=True,
            signature_verified=True,
            canonical_digest="0" * 64,
        )
        receipt = replace(receipt, canonical_digest=digest(payload(receipt)))
        self._vault[instruction.completion_id] = (receipt, report)
        return receipt, report

    @staticmethod
    def _entry(
        candidate: ProtectedRecommendationCandidate,
        impact_entry_digest: str,
        required_dimensions: tuple[str, ...],
        evidence_references: tuple[str, ...],
        gap_count: int,
        unknown_count: int,
    ) -> ProtectedCandidateRiskRecoveryEntry:
        digest = GovernedProtectedModelInvocationService._digest
        payload = GovernedProtectedModelInvocationService._payload
        category = candidate.category
        if category == "recommendation-category.investigate":
            overall, duration = "moderate", (2, 5, "moderate")
        elif category == "recommendation-category.escalate":
            overall, duration = "moderate", (10, 30, "moderate")
        elif category == "recommendation-category.defer-no-action":
            overall, duration = "moderate", (0, 240, "low")
        else:
            overall, duration = "unknown", (0, 240, "unknown")
        dimensions: list[ProtectedCandidateRiskDimension] = []
        for dimension in required_dimensions:
            level = (
                "moderate"
                if dimension in {"operational-complexity", "evidence-uncertainty"}
                else "low"
            )
            if overall == "unknown" and dimension == "evidence-uncertainty":
                level = "unknown"
            item = ProtectedCandidateRiskDimension(
                dimension=dimension,
                level=level,
                rationale=(
                    "The policy table applies the conservative bounded evidence floor for this "
                    "conceptual C0/C1 candidate."
                ),
                evidence_references=evidence_references,
                canonical_digest="0" * 64,
            )
            dimensions.append(replace(item, canonical_digest=digest(payload(item))))
        work = ProtectedCandidateDurationEstimate(
            minimum_minutes=duration[0],
            maximum_minutes=duration[1],
            basis="Policy-selected historical ranges for the bounded conceptual candidate class.",
            confidence=duration[2],
            evidence_references=evidence_references,
            canonical_digest="0" * 64,
        )
        work = replace(work, canonical_digest=digest(payload(work)))
        interruption = ProtectedCandidateInterruptionEstimate(
            expected_mode="none-expected",
            worst_credible_mode="none-for-bounded-c0-c1",
            expected_minimum_minutes=0,
            expected_maximum_minutes=0,
            worst_minimum_minutes=0,
            worst_maximum_minutes=0,
            assumptions=("The candidate remains within the verified C0/C1 capability boundary.",),
            unknowns=("Conditions outside the exact evidence snapshot remain unknown.",),
            evidence_references=evidence_references,
            canonical_digest="0" * 64,
        )
        interruption = replace(interruption, canonical_digest=digest(payload(interruption)))
        recovery_duration = ProtectedCandidateDurationEstimate(
            minimum_minutes=0,
            maximum_minutes=5,
            basis="Stop the bounded read or handoff and preserve the prior observed state.",
            confidence="moderate",
            evidence_references=evidence_references,
            canonical_digest="0" * 64,
        )
        recovery_duration = replace(
            recovery_duration, canonical_digest=digest(payload(recovery_duration))
        )
        recovery = ProtectedCandidateRecoveryAssessment(
            strategy="stop-and-preserve-observed-state",
            feasibility="feasible",
            point_of_no_return="none-for-bounded-c0-c1",
            trigger_conditions=(
                "Stop when evidence diverges or any write authority is requested.",
            ),
            duration=recovery_duration,
            data_implications="No data mutation is authorized by this protected completion stage.",
            verification_criteria=("Verify no infrastructure mutation and retain audit evidence.",),
            gaps=("Production recovery behavior is not established by synthetic evidence.",),
            evidence_references=evidence_references,
            canonical_digest="0" * 64,
        )
        recovery = replace(recovery, canonical_digest=digest(payload(recovery)))
        entry = ProtectedCandidateRiskRecoveryEntry(
            candidate_id=candidate.candidate_id,
            candidate_digest=candidate.canonical_digest,
            impact_entry_digest=impact_entry_digest,
            risk_dimensions=tuple(dimensions),
            overall_risk=overall,
            work_duration=work,
            interruption=interruption,
            recovery=recovery,
            assumption_count=len(candidate.assumptions) + 1,
            conflict_count=len(candidate.contradicting_citation_references),
            gap_count=gap_count + len(candidate.evidence_gaps),
            unknown_count=unknown_count + len(candidate.unknowns),
            canonical_digest="0" * 64,
        )
        return replace(entry, canonical_digest=digest(payload(entry)))

    async def rehydrate(
        self,
        *,
        record: ProtectedCandidateRiskRecoveryRecord,
        completion_authorization_digest: str,
        candidate_set: ProtectedRecommendationCandidateSet,
        impact_report: ProtectedCandidateImpactReport,
        evidence_snapshot: ProtectedOperationalEvidenceSnapshot,
    ) -> tuple[ProtectedCandidateRiskRecoveryReceipt, ProtectedCandidateRiskRecoveryReport]:
        stored = self._vault.get(record.completion_id)
        if stored is None:
            raise ProtectedCandidateRiskRecoveryError(
                "protected_candidate_risk_recovery_content_unavailable"
            )
        receipt, report = stored
        digest = GovernedProtectedModelInvocationService._digest
        payload = GovernedProtectedModelInvocationService._payload
        if (
            completion_authorization_digest != record.completion_authorization_digest
            or candidate_set.canonical_digest != record.candidate_set_digest
            or impact_report.canonical_digest != report.impact_digest
            or evidence_snapshot.canonical_digest != record.evidence_snapshot_digest
            or evidence_snapshot.canonical_digest != digest(payload(evidence_snapshot))
            or report.canonical_digest != record.protected_report_digest
            or receipt.canonical_digest != record.completion_receipt_digest
        ):
            raise ProtectedCandidateRiskRecoveryError(
                "protected_candidate_risk_recovery_integrity_failed"
            )
        return receipt, report


class UnavailableTrustedProtectedCandidateRiskRecoveryAssessor:
    async def complete(
        self,
        instruction: ProtectedCandidateRiskRecoveryInstruction,
        candidate_set: ProtectedRecommendationCandidateSet,
        impact_report: ProtectedCandidateImpactReport,
        evidence_snapshot: ProtectedOperationalEvidenceSnapshot,
    ) -> tuple[ProtectedCandidateRiskRecoveryReceipt, ProtectedCandidateRiskRecoveryReport]:
        del instruction, candidate_set, impact_report, evidence_snapshot
        raise ProtectedCandidateRiskRecoveryError(
            "protected_candidate_risk_recovery_assessor_unavailable"
        )

    async def rehydrate(
        self,
        *,
        record: ProtectedCandidateRiskRecoveryRecord,
        completion_authorization_digest: str,
        candidate_set: ProtectedRecommendationCandidateSet,
        impact_report: ProtectedCandidateImpactReport,
        evidence_snapshot: ProtectedOperationalEvidenceSnapshot,
    ) -> tuple[ProtectedCandidateRiskRecoveryReceipt, ProtectedCandidateRiskRecoveryReport]:
        del record, completion_authorization_digest, candidate_set, impact_report, evidence_snapshot
        raise ProtectedCandidateRiskRecoveryError(
            "protected_candidate_risk_recovery_content_unavailable"
        )
