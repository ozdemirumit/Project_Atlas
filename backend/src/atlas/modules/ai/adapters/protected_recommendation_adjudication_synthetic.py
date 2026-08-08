from __future__ import annotations

import json
from dataclasses import asdict, replace

from atlas.modules.ai.application.protected_model_invocation import (
    GovernedProtectedModelInvocationService,
)
from atlas.modules.ai.application.protected_recommendation_adjudication_ports import (
    ProtectedRecommendationAdjudicationError,
)
from atlas.modules.ai.domain.protected_candidate_impact_enrichment import (
    ProtectedCandidateImpactReport,
)
from atlas.modules.ai.domain.protected_candidate_risk_recovery_completion import (
    ProtectedCandidateRiskRecoveryEntry,
    ProtectedCandidateRiskRecoveryReport,
    ProtectedOperationalEvidenceSnapshot,
)
from atlas.modules.ai.domain.protected_recommendation_adjudication import (
    ProtectedRecommendationAdjudicationEntry,
    ProtectedRecommendationAdjudicationInstruction,
    ProtectedRecommendationAdjudicationReceipt,
    ProtectedRecommendationAdjudicationRecord,
    ProtectedRecommendationAdjudicationReport,
    ProtectedRecommendationComparisonDimension,
)
from atlas.modules.ai.domain.protected_recommendation_candidate_generation import (
    ProtectedRecommendationCandidate,
    ProtectedRecommendationCandidateSet,
)

RISK_ORDER = {"low": 0, "moderate": 1, "high": 2, "critical": 3, "unknown": 4}
CAPABILITY_ORDER = {"C0": 0, "C1": 1, "C2": 2, "C3": 3, "C4": 4, "C5": 5}


class SyntheticTrustedProtectedRecommendationAdjudicator:
    def __init__(self) -> None:
        self.calls: list[ProtectedRecommendationAdjudicationInstruction] = []
        self._vault: dict[
            str,
            tuple[
                ProtectedRecommendationAdjudicationReceipt,
                ProtectedRecommendationAdjudicationReport,
            ],
        ] = {}

    async def adjudicate(
        self,
        instruction: ProtectedRecommendationAdjudicationInstruction,
        candidate_set: ProtectedRecommendationCandidateSet,
        impact_report: ProtectedCandidateImpactReport,
        completion_report: ProtectedCandidateRiskRecoveryReport,
        evidence_snapshot: ProtectedOperationalEvidenceSnapshot,
    ) -> tuple[
        ProtectedRecommendationAdjudicationReceipt,
        ProtectedRecommendationAdjudicationReport,
    ]:
        self.calls.append(instruction)
        digest = GovernedProtectedModelInvocationService._digest
        payload = GovernedProtectedModelInvocationService._payload
        if (
            candidate_set.candidate_set_id != instruction.candidate_set_id
            or candidate_set.canonical_digest != instruction.candidate_set_digest
            or completion_report.completion_id != instruction.completion_id
            or completion_report.canonical_digest != instruction.completion_digest
            or completion_report.candidate_set_digest != candidate_set.canonical_digest
            or impact_report.candidate_set_digest != candidate_set.canonical_digest
            or evidence_snapshot.snapshot_id != completion_report.evidence_snapshot_id
            or evidence_snapshot.canonical_digest != completion_report.evidence_snapshot_digest
            or any(
                item.canonical_digest != digest(payload(item)) for item in evidence_snapshot.items
            )
        ):
            raise ProtectedRecommendationAdjudicationError(
                "protected_recommendation_adjudication_source_invalid"
            )
        completion_by_candidate = {entry.candidate_id: entry for entry in completion_report.entries}
        drafts: list[
            tuple[
                ProtectedRecommendationCandidate,
                ProtectedCandidateRiskRecoveryEntry,
                bool,
                tuple[str, ...],
                tuple[ProtectedRecommendationComparisonDimension, ...],
                tuple[int, ...],
            ]
        ] = []
        for candidate in candidate_set.candidates:
            completion = completion_by_candidate.get(candidate.candidate_id)
            if completion is None or completion.candidate_digest != candidate.canonical_digest:
                raise ProtectedRecommendationAdjudicationError(
                    "protected_recommendation_adjudication_source_invalid"
                )
            capability = max(
                (step.capability_class for step in candidate.steps),
                key=CAPABILITY_ORDER.__getitem__,
            )
            exclusion_reasons: list[str] = []
            if candidate.category not in instruction.allowed_categories:
                exclusion_reasons.append("category-not-allowed")
            if (
                CAPABILITY_ORDER[capability]
                > CAPABILITY_ORDER[instruction.maximum_capability_class]
            ):
                exclusion_reasons.append("capability-ceiling-exceeded")
            if completion.recovery.feasibility not in {"feasible", "not_required"}:
                exclusion_reasons.append("recovery-not-supportable")
            eligible = not exclusion_reasons
            evidence_value = {
                "recommendation-category.investigate": "high",
                "recommendation-category.escalate": "moderate",
                "recommendation-category.defer-no-action": "bounded",
            }.get(candidate.category, "unknown")
            values = {
                "policy-eligibility": "eligible" if eligible else "ineligible",
                "evidence-applicability": candidate.confidence,
                "risk-and-uncertainty": completion.overall_risk,
                "capability-class": capability,
                "interruption": str(completion.interruption.worst_maximum_minutes),
                "recovery-and-reversibility": completion.recovery.feasibility,
                "work-duration": str(completion.work_duration.maximum_minutes),
                "evidence-value": evidence_value,
                "category-precedence": str(
                    instruction.category_precedence.index(candidate.category)
                    if candidate.category in instruction.category_precedence
                    else len(instruction.category_precedence)
                ),
            }
            comparison_dimensions: list[ProtectedRecommendationComparisonDimension] = []
            for precedence, name in enumerate(instruction.required_dimensions, start=1):
                dimension = ProtectedRecommendationComparisonDimension(
                    dimension=name,
                    precedence=precedence,
                    value=values[name],
                    rationale=(
                        "The signed deterministic policy evaluated this typed protected value at "
                        "its declared precedence."
                    ),
                    canonical_digest="0" * 64,
                )
                comparison_dimensions.append(
                    replace(dimension, canonical_digest=digest(payload(dimension)))
                )
            preference_key = (
                instruction.category_precedence.index(candidate.category)
                if candidate.category in instruction.category_precedence
                else len(instruction.category_precedence),
                RISK_ORDER[completion.overall_risk],
                CAPABILITY_ORDER[capability],
                completion.interruption.worst_maximum_minutes,
                completion.work_duration.maximum_minutes,
                completion.unknown_count,
            )
            drafts.append(
                (
                    candidate,
                    completion,
                    eligible,
                    tuple(exclusion_reasons),
                    tuple(comparison_dimensions),
                    preference_key,
                )
            )
        eligible_drafts = [item for item in drafts if item[2]]
        best_key = min((item[5] for item in eligible_drafts), default=None)
        best_count = sum(item[5] == best_key for item in eligible_drafts) if best_key else 0
        tie = best_count > 1
        entries: list[ProtectedRecommendationAdjudicationEntry] = []
        for candidate, completion, eligible, exclusions, dimensions, key in drafts:
            state = (
                "ineligible"
                if not eligible
                else "preferred"
                if key == best_key and not tie
                else "alternative"
            )
            entry = ProtectedRecommendationAdjudicationEntry(
                candidate_id=candidate.candidate_id,
                candidate_digest=candidate.canonical_digest,
                completion_entry_digest=completion.canonical_digest,
                eligible=eligible,
                exclusion_reasons=exclusions,
                dimensions=dimensions,
                preference_state=state,
                preference_rationale=(
                    "The signed lexicographic policy establishes this protected preference state; "
                    "it is not approval or authority to act."
                ),
                gap_count=completion.gap_count,
                unknown_count=completion.unknown_count,
                canonical_digest="0" * 64,
            )
            entries.append(replace(entry, canonical_digest=digest(payload(entry))))
        encoded = json.dumps(
            GovernedProtectedModelInvocationService._normalize(
                [asdict(entry) for entry in entries]
            ),
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")
        dimension_count = len(instruction.required_dimensions)
        excluded_count = sum(not entry.eligible for entry in entries)
        eligible_count = len(entries) - excluded_count
        preferred_count = sum(entry.preference_state == "preferred" for entry in entries)
        alternative_count = sum(entry.preference_state == "alternative" for entry in entries)
        if (
            len(entries) > instruction.maximum_candidate_count
            or dimension_count > instruction.maximum_dimension_count
            or sum(len(entry.exclusion_reasons) for entry in entries)
            > instruction.maximum_exclusion_count
            or sum(entry.unknown_count for entry in entries) > instruction.maximum_unknown_count
            or len(encoded) > instruction.maximum_output_bytes
            or preferred_count > 1
        ):
            raise ProtectedRecommendationAdjudicationError(
                "protected_recommendation_adjudication_content_invalid"
            )
        comparison_digest = digest(
            tuple(
                (entry.candidate_id, tuple(item.canonical_digest for item in entry.dimensions))
                for entry in entries
            )
        )
        eligibility_digest = digest(
            tuple((entry.candidate_id, entry.eligible) for entry in entries)
        )
        exclusion_digest = digest(
            tuple((entry.candidate_id, entry.exclusion_reasons) for entry in entries)
        )
        preference_digest = digest(
            tuple((entry.candidate_id, entry.preference_state) for entry in entries)
        )
        safety_digest = digest(
            [instruction.safety_profile_digest, "protected-no-presentation-no-authority"]
        )
        report = ProtectedRecommendationAdjudicationReport(
            adjudication_id=instruction.adjudication_id,
            schema_version=instruction.required_report_schema,
            version=1,
            completion_id=instruction.completion_id,
            completion_digest=instruction.completion_digest,
            candidate_set_id=instruction.candidate_set_id,
            candidate_set_digest=instruction.candidate_set_digest,
            policy_digest=instruction.policy_digest,
            entries=tuple(entries),
            candidate_count=len(entries),
            dimension_count=dimension_count,
            eligible_count=eligible_count,
            excluded_count=excluded_count,
            preferred_count=preferred_count,
            alternative_count=alternative_count,
            tie=tie,
            no_supportable_candidate=eligible_count == 0,
            comparison_digest=comparison_digest,
            eligibility_digest=eligibility_digest,
            exclusion_digest=exclusion_digest,
            preference_digest=preference_digest,
            safety_digest=safety_digest,
            byte_count=len(encoded),
            completed_at=instruction.requested_at,
            expires_at=instruction.expires_at,
            canonical_digest="0" * 64,
        )
        report = replace(report, canonical_digest=digest(payload(report)))
        receipt = ProtectedRecommendationAdjudicationReceipt(
            adjudication_id=instruction.adjudication_id,
            schema_version="atlas.protected-recommendation-adjudication-receipt.v1",
            version=1,
            adjudicator_id="protected-recommendation-adjudicator.synthetic",
            attested_by="subject.protected-recommendation-adjudicator-attestor",
            completion_id=instruction.completion_id,
            completion_digest=instruction.completion_digest,
            candidate_set_id=instruction.candidate_set_id,
            candidate_set_digest=instruction.candidate_set_digest,
            adjudication_authorization_digest=instruction.adjudication_authorization_digest,
            policy_digest=instruction.policy_digest,
            report_digest=report.canonical_digest,
            comparison_digest=comparison_digest,
            eligibility_digest=eligibility_digest,
            exclusion_digest=exclusion_digest,
            preference_digest=preference_digest,
            safety_digest=safety_digest,
            cleanup_digest=digest([instruction.adjudication_id, "cleanup-verified"]),
            candidate_count=len(entries),
            dimension_count=dimension_count,
            eligible_count=eligible_count,
            excluded_count=excluded_count,
            preferred_count=preferred_count,
            alternative_count=alternative_count,
            tie=tie,
            no_supportable_candidate=eligible_count == 0,
            byte_count=len(encoded),
            completed_at=instruction.requested_at,
            expires_at=instruction.expires_at,
            source_verified=True,
            complete_candidate_coverage_verified=True,
            deterministic_policy_verified=True,
            conservative_unknowns_verified=True,
            tie_behavior_verified=True,
            no_caller_preference_verified=True,
            no_model_used=True,
            cleanup_verified=True,
            signature_verified=True,
            canonical_digest="0" * 64,
        )
        receipt = replace(receipt, canonical_digest=digest(payload(receipt)))
        self._vault[instruction.adjudication_id] = (receipt, report)
        return receipt, report

    async def rehydrate(
        self,
        *,
        record: ProtectedRecommendationAdjudicationRecord,
        adjudication_authorization_digest: str,
        candidate_set: ProtectedRecommendationCandidateSet,
        completion_report: ProtectedCandidateRiskRecoveryReport,
    ) -> tuple[
        ProtectedRecommendationAdjudicationReceipt,
        ProtectedRecommendationAdjudicationReport,
    ]:
        stored = self._vault.get(record.adjudication_id)
        if stored is None:
            raise ProtectedRecommendationAdjudicationError(
                "protected_recommendation_adjudication_content_unavailable"
            )
        receipt, report = stored
        if (
            adjudication_authorization_digest != record.adjudication_authorization_digest
            or candidate_set.canonical_digest != record.candidate_set_digest
            or completion_report.canonical_digest != report.completion_digest
            or report.canonical_digest != record.protected_report_digest
            or receipt.canonical_digest != record.adjudication_receipt_digest
        ):
            raise ProtectedRecommendationAdjudicationError(
                "protected_recommendation_adjudication_integrity_failed"
            )
        return receipt, report


class UnavailableTrustedProtectedRecommendationAdjudicator:
    async def adjudicate(
        self,
        instruction: ProtectedRecommendationAdjudicationInstruction,
        candidate_set: ProtectedRecommendationCandidateSet,
        impact_report: ProtectedCandidateImpactReport,
        completion_report: ProtectedCandidateRiskRecoveryReport,
        evidence_snapshot: ProtectedOperationalEvidenceSnapshot,
    ) -> tuple[
        ProtectedRecommendationAdjudicationReceipt,
        ProtectedRecommendationAdjudicationReport,
    ]:
        del instruction, candidate_set, impact_report, completion_report, evidence_snapshot
        raise ProtectedRecommendationAdjudicationError(
            "protected_recommendation_adjudicator_unavailable"
        )

    async def rehydrate(
        self,
        *,
        record: ProtectedRecommendationAdjudicationRecord,
        adjudication_authorization_digest: str,
        candidate_set: ProtectedRecommendationCandidateSet,
        completion_report: ProtectedCandidateRiskRecoveryReport,
    ) -> tuple[
        ProtectedRecommendationAdjudicationReceipt,
        ProtectedRecommendationAdjudicationReport,
    ]:
        del record, adjudication_authorization_digest, candidate_set, completion_report
        raise ProtectedRecommendationAdjudicationError(
            "protected_recommendation_adjudication_content_unavailable"
        )
