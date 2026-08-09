from __future__ import annotations

import json
from dataclasses import asdict, replace

from atlas.modules.ai.application.protected_model_invocation import (
    GovernedProtectedModelInvocationService,
)
from atlas.modules.ai.application.protected_recommendation_presentation_ports import (
    ProtectedRecommendationPresentationError,
)
from atlas.modules.ai.domain.protected_candidate_impact_enrichment import (
    ProtectedCandidateImpactEntry,
    ProtectedCandidateImpactReport,
)
from atlas.modules.ai.domain.protected_candidate_risk_recovery_completion import (
    ProtectedCandidateRiskRecoveryEntry,
    ProtectedCandidateRiskRecoveryReport,
)
from atlas.modules.ai.domain.protected_recommendation_adjudication import (
    ProtectedRecommendationAdjudicationEntry,
    ProtectedRecommendationAdjudicationReport,
)
from atlas.modules.ai.domain.protected_recommendation_candidate_generation import (
    ProtectedRecommendationCandidate,
    ProtectedRecommendationCandidateSet,
)
from atlas.modules.ai.domain.protected_recommendation_presentation import (
    PresentedRecommendationOption,
    PresentedRecommendationStep,
    ProtectedPresentedRecommendation,
    ProtectedRecommendationPresentationInstruction,
    ProtectedRecommendationPresentationReceipt,
    ProtectedRecommendationPresentationRecord,
)

RISK_ORDER = {"low": 0, "moderate": 1, "high": 2, "critical": 3, "unknown": 4}
CAPABILITY_ORDER = {"C0": 0, "C1": 1}


class SyntheticTrustedProtectedRecommendationPresenter:
    def __init__(self) -> None:
        self.calls: list[ProtectedRecommendationPresentationInstruction] = []
        self._vault: dict[
            str,
            tuple[
                ProtectedRecommendationPresentationReceipt,
                ProtectedPresentedRecommendation,
            ],
        ] = {}

    async def present(
        self,
        instruction: ProtectedRecommendationPresentationInstruction,
        adjudication_report: ProtectedRecommendationAdjudicationReport,
        candidate_set: ProtectedRecommendationCandidateSet,
        impact_report: ProtectedCandidateImpactReport,
        completion_report: ProtectedCandidateRiskRecoveryReport,
    ) -> tuple[ProtectedRecommendationPresentationReceipt, ProtectedPresentedRecommendation]:
        self.calls.append(instruction)
        self._verify_sources(
            instruction,
            adjudication_report,
            candidate_set,
            impact_report,
            completion_report,
        )
        impacts = {entry.candidate_id: entry for entry in impact_report.entries}
        completions = {entry.candidate_id: entry for entry in completion_report.entries}
        candidates = {candidate.candidate_id: candidate for candidate in candidate_set.candidates}
        selected_entries, outcome = self._selected_entries(adjudication_report)
        options: list[PresentedRecommendationOption] = []
        for entry in selected_entries:
            candidate = candidates[entry.candidate_id]
            impact = impacts[entry.candidate_id]
            completion = completions[entry.candidate_id]
            role = (
                "unsupported"
                if outcome == "no_support"
                else "tied"
                if outcome == "tie"
                else entry.preference_state
            )
            options.append(self._option(role, entry, candidate, impact, completion, instruction))
        evidence_needs = tuple(
            dict.fromkeys(gap for option in options for gap in option.evidence_gaps)
        )
        recommendation = ProtectedPresentedRecommendation(
            presentation_id=instruction.presentation_id,
            outcome=outcome,
            headline=self._headline(outcome),
            safety_notice=(
                "Decision support only. This presentation does not approve a change, create a "
                "workflow, authorize execution, or mutate infrastructure."
            ),
            options=tuple(options),
            evidence_needs=evidence_needs,
            media_type=instruction.media_type,
            byte_count=1,
            presented_at=instruction.requested_at,
            expires_at=instruction.expires_at,
            canonical_digest="0" * 64,
        )
        encoded = self._encoded(recommendation)
        if len(encoded) > instruction.maximum_output_bytes or self._contains_prohibited(encoded):
            raise ProtectedRecommendationPresentationError(
                "protected_recommendation_presentation_content_invalid"
            )
        digest = GovernedProtectedModelInvocationService._digest
        payload = GovernedProtectedModelInvocationService._payload
        recommendation = replace(recommendation, byte_count=len(encoded))
        recommendation = replace(recommendation, canonical_digest=digest(payload(recommendation)))
        evidence_count = len(
            {
                reference
                for option in recommendation.options
                for reference in option.evidence_references
            }
        )
        unknown_count = sum(len(option.unknowns) for option in recommendation.options)
        source_binding_digest = digest(
            [
                instruction.adjudication_digest,
                adjudication_report.canonical_digest,
                candidate_set.canonical_digest,
                impact_report.canonical_digest,
                completion_report.canonical_digest,
            ]
        )
        receipt = ProtectedRecommendationPresentationReceipt(
            presentation_id=instruction.presentation_id,
            schema_version="atlas.protected-recommendation-presentation-receipt.v1",
            version=1,
            presenter_id="protected-recommendation-presenter.synthetic",
            attested_by="subject.protected-recommendation-presenter-attestor",
            adjudication_id=instruction.adjudication_id,
            adjudication_digest=instruction.adjudication_digest,
            presentation_authorization_digest=instruction.presentation_authorization_digest,
            policy_digest=instruction.policy_digest,
            recommendation_digest=recommendation.canonical_digest,
            source_binding_digest=source_binding_digest,
            rendering_digest=digest(
                [instruction.rendering_profile_digest, instruction.media_type, len(encoded)]
            ),
            cleanup_digest=digest([instruction.presentation_id, "cleanup-verified"]),
            outcome=outcome,
            option_count=len(options),
            preferred_count=sum(option.role == "preferred" for option in options),
            evidence_reference_count=evidence_count,
            unknown_count=unknown_count,
            byte_count=len(encoded),
            presented_at=instruction.requested_at,
            expires_at=instruction.expires_at,
            source_verified=True,
            outcome_preserved=True,
            safe_fields_verified=True,
            inert_rendering_verified=True,
            no_model_used=True,
            no_operational_authority=True,
            cleanup_verified=True,
            signature_verified=True,
            canonical_digest="0" * 64,
        )
        receipt = replace(receipt, canonical_digest=digest(payload(receipt)))
        self._vault[instruction.presentation_id] = (receipt, recommendation)
        return receipt, recommendation

    async def rehydrate(
        self,
        *,
        record: ProtectedRecommendationPresentationRecord,
        presentation_authorization_digest: str,
        adjudication_report: ProtectedRecommendationAdjudicationReport,
        candidate_set: ProtectedRecommendationCandidateSet,
        impact_report: ProtectedCandidateImpactReport,
        completion_report: ProtectedCandidateRiskRecoveryReport,
    ) -> ProtectedPresentedRecommendation:
        stored = self._vault.get(record.presentation_id)
        if stored is None:
            raise ProtectedRecommendationPresentationError(
                "protected_recommendation_presentation_content_unavailable"
            )
        receipt, recommendation = stored
        source_binding_digest = GovernedProtectedModelInvocationService._digest(
            [
                record.adjudication_digest,
                adjudication_report.canonical_digest,
                candidate_set.canonical_digest,
                impact_report.canonical_digest,
                completion_report.canonical_digest,
            ]
        )
        if (
            presentation_authorization_digest != record.presentation_authorization_digest
            or receipt.canonical_digest != record.presentation_receipt_digest
            or receipt.source_binding_digest != source_binding_digest
            or source_binding_digest != record.source_binding_digest
            or recommendation.canonical_digest != record.recommendation_digest
            or recommendation.byte_count != record.byte_count
        ):
            raise ProtectedRecommendationPresentationError(
                "protected_recommendation_presentation_integrity_failed"
            )
        return recommendation

    @staticmethod
    def _verify_sources(
        instruction: ProtectedRecommendationPresentationInstruction,
        adjudication_report: ProtectedRecommendationAdjudicationReport,
        candidate_set: ProtectedRecommendationCandidateSet,
        impact_report: ProtectedCandidateImpactReport,
        completion_report: ProtectedCandidateRiskRecoveryReport,
    ) -> None:
        candidate_ids = {item.candidate_id for item in candidate_set.candidates}
        if (
            adjudication_report.canonical_digest != instruction.adjudication_report_digest
            or candidate_set.canonical_digest != instruction.candidate_set_digest
            or impact_report.canonical_digest != instruction.impact_report_digest
            or completion_report.canonical_digest != instruction.completion_report_digest
            or candidate_ids != {item.candidate_id for item in adjudication_report.entries}
            or candidate_ids != {item.candidate_id for item in impact_report.entries}
            or candidate_ids != {item.candidate_id for item in completion_report.entries}
            or len(candidate_ids) > instruction.maximum_option_count
        ):
            raise ProtectedRecommendationPresentationError(
                "protected_recommendation_presentation_source_invalid"
            )

    @classmethod
    def _selected_entries(
        cls, report: ProtectedRecommendationAdjudicationReport
    ) -> tuple[tuple[ProtectedRecommendationAdjudicationEntry, ...], str]:
        if report.no_supportable_candidate:
            return report.entries, "no_support"
        if report.tie:
            eligible = tuple(entry for entry in report.entries if entry.eligible)
            best_key = min(cls._comparison_key(entry) for entry in eligible)
            tied = tuple(entry for entry in eligible if cls._comparison_key(entry) == best_key)
            if len(tied) < 2:
                raise ProtectedRecommendationPresentationError(
                    "protected_recommendation_presentation_tie_invalid"
                )
            return tied, "tie"
        preferred = tuple(
            entry for entry in report.entries if entry.preference_state == "preferred"
        )
        alternatives = tuple(
            entry for entry in report.entries if entry.preference_state == "alternative"
        )
        if len(preferred) != 1:
            raise ProtectedRecommendationPresentationError(
                "protected_recommendation_presentation_preference_invalid"
            )
        return preferred + alternatives, "preferred"

    @staticmethod
    def _comparison_key(entry: ProtectedRecommendationAdjudicationEntry) -> tuple[int, ...]:
        values = {item.dimension: item.value for item in entry.dimensions}
        return (
            int(values.get("category-precedence", "999999")),
            RISK_ORDER.get(values.get("risk-and-uncertainty", "unknown"), 4),
            CAPABILITY_ORDER.get(values.get("capability-class", "C1"), 1),
            int(values.get("interruption", "999999")),
            int(values.get("work-duration", "999999")),
            entry.unknown_count,
        )

    @staticmethod
    def _option(
        role: str,
        adjudication: ProtectedRecommendationAdjudicationEntry,
        candidate: ProtectedRecommendationCandidate,
        impact: ProtectedCandidateImpactEntry,
        completion: ProtectedCandidateRiskRecoveryEntry,
        instruction: ProtectedRecommendationPresentationInstruction,
    ) -> PresentedRecommendationOption:
        if (
            len(candidate.steps) > instruction.maximum_steps_per_option
            or max(
                len(candidate.assumptions),
                len(candidate.unknowns),
                len(candidate.evidence_gaps),
                len(candidate.applicability_limits),
            )
            > instruction.maximum_text_items_per_option
        ):
            raise ProtectedRecommendationPresentationError(
                "protected_recommendation_presentation_content_invalid"
            )
        evidence = tuple(
            dict.fromkeys(
                candidate.supporting_citation_references
                + completion.interruption.evidence_references
                + completion.recovery.evidence_references
            )
        )
        return PresentedRecommendationOption(
            role=role,
            category=candidate.category,
            title=candidate.title,
            intended_outcome=candidate.intended_outcome,
            rationale=adjudication.preference_rationale,
            confidence=candidate.confidence,
            confidence_rationale=candidate.confidence_rationale,
            steps=tuple(
                PresentedRecommendationStep(
                    order=step.order,
                    phase=step.phase,
                    conceptual_action=step.conceptual_action,
                    capability_class=step.capability_class,
                )
                for step in candidate.steps
            ),
            overall_risk=completion.overall_risk,
            work_minimum_minutes=completion.work_duration.minimum_minutes,
            work_maximum_minutes=completion.work_duration.maximum_minutes,
            interruption_expected_mode=completion.interruption.expected_mode,
            interruption_minimum_minutes=completion.interruption.expected_minimum_minutes,
            interruption_maximum_minutes=completion.interruption.worst_maximum_minutes,
            recovery_feasibility=completion.recovery.feasibility,
            recovery_minimum_minutes=completion.recovery.duration.minimum_minutes,
            recovery_maximum_minutes=completion.recovery.duration.maximum_minutes,
            technical_service_count=len(impact.technical_service_ids),
            business_service_count=len(impact.business_service_ids),
            evidence_references=evidence,
            assumptions=candidate.assumptions,
            unknowns=tuple(dict.fromkeys(candidate.unknowns + impact.unknowns)),
            evidence_gaps=tuple(dict.fromkeys(candidate.evidence_gaps + impact.known_gaps)),
            applicability_limits=candidate.applicability_limits,
            support_reasons=adjudication.exclusion_reasons,
        )

    @staticmethod
    def _headline(outcome: str) -> str:
        return {
            "preferred": "A preferred decision-support option is available.",
            "tie": "Multiple options remain equally supported; no option was selected.",
            "no_support": "No option is currently supportable; additional evidence is required.",
        }[outcome]

    @staticmethod
    def _encoded(recommendation: ProtectedPresentedRecommendation) -> bytes:
        value = asdict(recommendation)
        value["canonical_digest"] = ""
        return json.dumps(value, sort_keys=True, separators=(",", ":"), default=str).encode()

    @staticmethod
    def _contains_prohibited(encoded: bytes) -> bool:
        lowered = encoded.lower()
        return any(
            token in lowered
            for token in (
                b"<script",
                b"```",
                b"tool_call",
                b"password=",
                b"secret=",
                b"http://",
                b"https://",
                b"operation completed",
            )
        )


class UnavailableTrustedProtectedRecommendationPresenter:
    async def present(
        self,
        instruction: ProtectedRecommendationPresentationInstruction,
        adjudication_report: ProtectedRecommendationAdjudicationReport,
        candidate_set: ProtectedRecommendationCandidateSet,
        impact_report: ProtectedCandidateImpactReport,
        completion_report: ProtectedCandidateRiskRecoveryReport,
    ) -> tuple[ProtectedRecommendationPresentationReceipt, ProtectedPresentedRecommendation]:
        del instruction, adjudication_report, candidate_set, impact_report, completion_report
        raise ProtectedRecommendationPresentationError(
            "protected_recommendation_presentation_presenter_unavailable"
        )

    async def rehydrate(
        self,
        *,
        record: ProtectedRecommendationPresentationRecord,
        presentation_authorization_digest: str,
        adjudication_report: ProtectedRecommendationAdjudicationReport,
        candidate_set: ProtectedRecommendationCandidateSet,
        impact_report: ProtectedCandidateImpactReport,
        completion_report: ProtectedCandidateRiskRecoveryReport,
    ) -> ProtectedPresentedRecommendation:
        del (
            record,
            presentation_authorization_digest,
            adjudication_report,
            candidate_set,
            impact_report,
            completion_report,
        )
        raise ProtectedRecommendationPresentationError(
            "protected_recommendation_presentation_recommendation_unavailable"
        )
