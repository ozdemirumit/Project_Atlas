from __future__ import annotations

import json
from dataclasses import asdict, replace

from atlas.modules.ai.application.protected_model_invocation import (
    GovernedProtectedModelInvocationService,
)
from atlas.modules.ai.application.protected_recommendation_candidate_generation_ports import (
    ProtectedRecommendationCandidateError,
)
from atlas.modules.ai.domain.protected_answer_presentation import ProtectedPresentedAnswer
from atlas.modules.ai.domain.protected_draft_adjudication import (
    ProtectedDraftAdjudicationReport,
)
from atlas.modules.ai.domain.protected_model_invocation import ProtectedModelResponseDraft
from atlas.modules.ai.domain.protected_recommendation_candidate_generation import (
    ProtectedRecommendationCandidate,
    ProtectedRecommendationCandidateInstruction,
    ProtectedRecommendationCandidateReceipt,
    ProtectedRecommendationCandidateRecord,
    ProtectedRecommendationCandidateSet,
    ProtectedRecommendationCandidateStep,
)
from atlas.modules.knowledge.domain.model_context_assembly import ProtectedModelContextPackage


class SyntheticTrustedProtectedRecommendationCandidateGenerator:
    def __init__(self) -> None:
        self.calls: list[ProtectedRecommendationCandidateInstruction] = []
        self._vault: dict[
            str, tuple[ProtectedRecommendationCandidateReceipt, ProtectedRecommendationCandidateSet]
        ] = {}

    async def generate(
        self,
        instruction: ProtectedRecommendationCandidateInstruction,
        answer: ProtectedPresentedAnswer,
        report: ProtectedDraftAdjudicationReport,
        draft: ProtectedModelResponseDraft,
        context: ProtectedModelContextPackage,
    ) -> tuple[ProtectedRecommendationCandidateReceipt, ProtectedRecommendationCandidateSet]:
        self.calls.append(instruction)
        digest = GovernedProtectedModelInvocationService._digest
        payload = GovernedProtectedModelInvocationService._payload
        allowed_citations = {unit.evidence_reference_id for unit in context.evidence_units}
        if (
            answer.presentation_id != instruction.presentation_id
            or answer.canonical_digest != instruction.answer_digest
            or draft.summary != answer.summary
            or draft.citation_references != answer.citation_references
            or draft.unknowns != answer.unknowns
            or report.outcome != "adjudication-outcome.eligible"
            or report.draft_digest != draft.canonical_digest == instruction.draft_digest
            or context.canonical_digest != instruction.context_package_digest
            or not answer.citation_references
            or not answer.unknowns
            or not all(reference in allowed_citations for reference in answer.citation_references)
        ):
            raise ProtectedRecommendationCandidateError(
                "protected_recommendation_candidate_source_invalid"
            )

        templates = {
            "recommendation-category.investigate": (
                "Repeat the approved read-only health observation",
                (
                    "Determine whether the observed warning remains present without changing "
                    "the target."
                ),
                "phase.observe",
                "Repeat the approved bounded hardware-health read and preserve the new evidence.",
                "hitachi.opscenter.storage.hardware.read",
                "C1",
                "candidate-state.provisional",
                "confidence.moderate",
            ),
            "recommendation-category.escalate": (
                "Prepare an evidence-bound vendor escalation",
                "Give the accountable engineer a complete evidence package for vendor review.",
                "phase.escalate",
                (
                    "Prepare an approved support package containing only authorized evidence "
                    "references."
                ),
                "atlas.vendor.support.package.prepare",
                "C1",
                "candidate-state.provisional",
                "confidence.moderate",
            ),
            "recommendation-category.defer-no-action": (
                "Defer operational change while preserving observation",
                (
                    "Avoid unsupported change activity until current impact and recovery evidence "
                    "exists."
                ),
                "phase.defer",
                (
                    "Record the unresolved warning and continue authorized observation without "
                    "mutation."
                ),
                None,
                "C0",
                "candidate-state.provisional",
                "confidence.low",
            ),
        }
        candidates: list[ProtectedRecommendationCandidate] = []
        for index, category in enumerate(instruction.required_categories, start=1):
            template = templates.get(category)
            if template is None:
                raise ProtectedRecommendationCandidateError(
                    "protected_recommendation_candidate_policy_invalid"
                )
            title, outcome, phase, action, capability, capability_class, state, confidence = (
                template
            )
            if capability is not None and capability not in instruction.allowed_capability_ids:
                raise ProtectedRecommendationCandidateError(
                    "protected_recommendation_candidate_capability_denied"
                )
            step = ProtectedRecommendationCandidateStep(
                order=1,
                phase=phase,
                conceptual_action=action,
                capability_id=capability,
                capability_class=capability_class,
            )
            candidate = ProtectedRecommendationCandidate(
                candidate_id=f"{instruction.candidate_set_id}.candidate-{index}",
                version=1,
                category=category,
                state=state,
                title=title,
                intended_outcome=outcome,
                steps=(step,),
                supporting_citation_references=answer.citation_references,
                contradicting_citation_references=(),
                assumptions=("The exact source evidence remains current for this bounded review.",),
                unknowns=answer.unknowns,
                applicability_limits=(
                    "This candidate is limited to the exact source purpose and protected evidence.",
                ),
                evidence_gaps=(
                    *answer.unknowns,
                    (
                        "Service impact, duration, interruption, recovery, and policy readiness "
                        "are not assessed."
                    ),
                ),
                confidence=confidence,
                confidence_rationale=(
                    "The candidate is grounded in authorized evidence but remains incomplete until "
                    "independent impact and recovery analysis succeeds."
                ),
                canonical_digest="0" * 64,
            )
            candidate = replace(candidate, canonical_digest=digest(payload(candidate)))
            candidates.append(candidate)

        encoded = json.dumps(
            GovernedProtectedModelInvocationService._normalize(
                [asdict(candidate) for candidate in candidates]
            ),
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")
        text = encoded.decode("utf-8").lower()
        if (
            len(candidates) > instruction.maximum_candidate_count
            or any(
                len(candidate.steps) > instruction.maximum_steps_per_candidate
                for candidate in candidates
            )
            or any(
                len(candidate.title) > instruction.maximum_title_characters
                for candidate in candidates
            )
            or any(
                len(candidate.intended_outcome) > instruction.maximum_outcome_characters
                for candidate in candidates
            )
            or any(
                len(
                    candidate.assumptions
                    + candidate.unknowns
                    + candidate.applicability_limits
                    + candidate.evidence_gaps
                )
                > instruction.maximum_text_items_per_candidate
                for candidate in candidates
            )
            or len(encoded) > instruction.maximum_output_bytes
            or any(
                token in text
                for token in (
                    "<script",
                    "tool_call",
                    "password=",
                    "secret=",
                    "execution authorized",
                    "operation completed",
                )
            )
        ):
            raise ProtectedRecommendationCandidateError(
                "protected_recommendation_candidate_content_invalid"
            )

        citation_digest = digest(answer.citation_references)
        unknown_digest = digest(answer.unknowns)
        source_digest = digest(
            [
                instruction.presentation_digest,
                answer.canonical_digest,
                report.canonical_digest,
                draft.canonical_digest,
                context.canonical_digest,
            ]
        )
        safety_digest = digest(
            [
                instruction.prohibited_output_profile_digest,
                instruction.maximum_capability_class,
                "non-executable",
                "no-preference",
            ]
        )
        candidate_set = ProtectedRecommendationCandidateSet(
            candidate_set_id=instruction.candidate_set_id,
            schema_version=instruction.required_candidate_set_schema,
            version=1,
            presentation_id=instruction.presentation_id,
            presentation_digest=instruction.presentation_digest,
            answer_digest=instruction.answer_digest,
            source_binding_digest=source_digest,
            policy_digest=instruction.policy_digest,
            candidates=tuple(candidates),
            citation_set_digest=citation_digest,
            unknown_set_digest=unknown_digest,
            safety_digest=safety_digest,
            byte_count=len(encoded),
            generated_at=instruction.requested_at,
            expires_at=instruction.expires_at,
            canonical_digest="0" * 64,
        )
        candidate_set = replace(candidate_set, canonical_digest=digest(payload(candidate_set)))
        cleanup_digest = digest([instruction.candidate_set_id, "cleanup-verified"])
        receipt = ProtectedRecommendationCandidateReceipt(
            candidate_set_id=instruction.candidate_set_id,
            schema_version="atlas.protected-recommendation-candidate-receipt.v1",
            version=1,
            generator_id="protected-recommendation-candidate-generator.synthetic",
            attested_by="subject.protected-recommendation-candidate-generator-attestor",
            presentation_id=instruction.presentation_id,
            presentation_digest=instruction.presentation_digest,
            generation_authorization_digest=instruction.generation_authorization_digest,
            policy_digest=instruction.policy_digest,
            candidate_set_digest=candidate_set.canonical_digest,
            source_binding_digest=source_digest,
            citation_set_digest=citation_digest,
            unknown_set_digest=unknown_digest,
            safety_digest=safety_digest,
            cleanup_digest=cleanup_digest,
            candidate_count=len(candidates),
            step_count=sum(len(candidate.steps) for candidate in candidates),
            citation_count=len(answer.citation_references),
            unknown_count=len(answer.unknowns),
            byte_count=len(encoded),
            generated_at=instruction.requested_at,
            expires_at=instruction.expires_at,
            source_verified=True,
            diversity_verified=True,
            citations_verified=True,
            unknowns_preserved=True,
            capability_boundary_verified=True,
            non_executable_verified=True,
            no_preference_assigned=True,
            no_model_used=True,
            cleanup_verified=True,
            signature_verified=True,
            canonical_digest="0" * 64,
        )
        receipt = replace(receipt, canonical_digest=digest(payload(receipt)))
        self._vault[instruction.candidate_set_id] = (receipt, candidate_set)
        return receipt, candidate_set

    async def rehydrate(
        self,
        *,
        record: ProtectedRecommendationCandidateRecord,
        generation_authorization_digest: str,
        answer: ProtectedPresentedAnswer,
        report: ProtectedDraftAdjudicationReport,
        draft: ProtectedModelResponseDraft,
        context: ProtectedModelContextPackage,
    ) -> tuple[ProtectedRecommendationCandidateReceipt, ProtectedRecommendationCandidateSet]:
        stored = self._vault.get(record.candidate_set_id)
        if stored is None:
            raise ProtectedRecommendationCandidateError(
                "protected_recommendation_candidate_content_unavailable"
            )
        receipt, candidate_set = stored
        expected_source = GovernedProtectedModelInvocationService._digest(
            [
                record.presentation_digest,
                answer.canonical_digest,
                report.canonical_digest,
                draft.canonical_digest,
                context.canonical_digest,
            ]
        )
        if (
            generation_authorization_digest != record.generation_authorization_digest
            or answer.canonical_digest != record.answer_digest
            or candidate_set.canonical_digest != record.candidate_content_digest
            or candidate_set.source_binding_digest != record.source_binding_digest
            or expected_source != record.source_binding_digest
            or receipt.canonical_digest != record.generation_receipt_digest
        ):
            raise ProtectedRecommendationCandidateError(
                "protected_recommendation_candidate_integrity_failed"
            )
        return receipt, candidate_set


class UnavailableTrustedProtectedRecommendationCandidateGenerator:
    async def generate(
        self,
        instruction: ProtectedRecommendationCandidateInstruction,
        answer: ProtectedPresentedAnswer,
        report: ProtectedDraftAdjudicationReport,
        draft: ProtectedModelResponseDraft,
        context: ProtectedModelContextPackage,
    ) -> tuple[ProtectedRecommendationCandidateReceipt, ProtectedRecommendationCandidateSet]:
        del instruction, answer, report, draft, context
        raise ProtectedRecommendationCandidateError(
            "protected_recommendation_candidate_generator_unavailable"
        )

    async def rehydrate(
        self,
        *,
        record: ProtectedRecommendationCandidateRecord,
        generation_authorization_digest: str,
        answer: ProtectedPresentedAnswer,
        report: ProtectedDraftAdjudicationReport,
        draft: ProtectedModelResponseDraft,
        context: ProtectedModelContextPackage,
    ) -> tuple[ProtectedRecommendationCandidateReceipt, ProtectedRecommendationCandidateSet]:
        del record, generation_authorization_digest, answer, report, draft, context
        raise ProtectedRecommendationCandidateError(
            "protected_recommendation_candidate_content_unavailable"
        )
