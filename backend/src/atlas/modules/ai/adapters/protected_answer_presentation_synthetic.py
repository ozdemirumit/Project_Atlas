from __future__ import annotations

from dataclasses import replace

from atlas.modules.ai.application.protected_answer_presentation_ports import (
    ProtectedAnswerPresentationError,
)
from atlas.modules.ai.application.protected_model_invocation import (
    GovernedProtectedModelInvocationService,
)
from atlas.modules.ai.domain.protected_answer_presentation import (
    ProtectedAnswerPresentationInstruction,
    ProtectedAnswerPresentationReceipt,
    ProtectedAnswerPresentationRecord,
    ProtectedPresentedAnswer,
)
from atlas.modules.ai.domain.protected_draft_adjudication import (
    ProtectedDraftAdjudicationReport,
)
from atlas.modules.ai.domain.protected_model_invocation import ProtectedModelResponseDraft
from atlas.modules.knowledge.domain.model_context_assembly import ProtectedModelContextPackage


class SyntheticTrustedProtectedAnswerPresenter:
    def __init__(self) -> None:
        self.calls: list[ProtectedAnswerPresentationInstruction] = []

    async def present(
        self,
        instruction: ProtectedAnswerPresentationInstruction,
        report: ProtectedDraftAdjudicationReport,
        draft: ProtectedModelResponseDraft,
        context: ProtectedModelContextPackage,
    ) -> tuple[ProtectedAnswerPresentationReceipt, ProtectedPresentedAnswer]:
        self.calls.append(instruction)
        digest = GovernedProtectedModelInvocationService._digest
        payload = GovernedProtectedModelInvocationService._payload
        allowed = {unit.evidence_reference_id for unit in context.evidence_units}
        encoded = self._encoded(draft)
        valid = (
            report.outcome == "adjudication-outcome.eligible"
            and report.draft_digest == draft.canonical_digest == instruction.draft_digest
            and report.citation_count == len(draft.citation_references)
            and report.unknown_count == len(draft.unknowns)
            and context.canonical_digest == instruction.context_package_digest
            and len(draft.summary) <= instruction.maximum_summary_characters
            and 0 < len(draft.citation_references) <= instruction.maximum_citation_count
            and 0 < len(draft.unknowns) <= instruction.maximum_unknown_count
            and all(reference in allowed for reference in draft.citation_references)
            and len(encoded) <= instruction.maximum_output_bytes
            and not any(
                token in draft.summary.lower()
                for token in ("<script", "tool_call", "password=", "secret=", "operation completed")
            )
        )
        if not valid:
            raise ProtectedAnswerPresentationError("protected_answer_presentation_content_invalid")
        answer = ProtectedPresentedAnswer(
            presentation_id=instruction.presentation_id,
            summary=draft.summary,
            citation_references=draft.citation_references,
            unknowns=draft.unknowns,
            media_type=instruction.media_type,
            byte_count=len(encoded),
            generated_at=instruction.requested_at,
            expires_at=instruction.expires_at,
            canonical_digest="0" * 64,
        )
        answer = replace(answer, canonical_digest=digest(payload(answer)))
        citation_digest = digest(draft.citation_references)
        unknown_digest = digest(draft.unknowns)
        source_digest = digest(
            [
                instruction.adjudication_digest,
                instruction.invocation_digest,
                report.canonical_digest,
                draft.canonical_digest,
                context.canonical_digest,
            ]
        )
        rendering_digest = digest(
            [instruction.rendering_profile_digest, instruction.media_type, len(encoded)]
        )
        cleanup_digest = digest([instruction.presentation_id, "cleanup-verified"])
        receipt = ProtectedAnswerPresentationReceipt(
            presentation_id=instruction.presentation_id,
            schema_version="atlas.protected-answer-presentation-receipt.v1",
            version=1,
            presenter_id="protected-answer-presenter.synthetic",
            attested_by="subject.protected-answer-presenter-attestor",
            adjudication_id=instruction.adjudication_id,
            adjudication_digest=instruction.adjudication_digest,
            invocation_digest=instruction.invocation_digest,
            draft_digest=instruction.draft_digest,
            report_digest=instruction.report_digest,
            presentation_authorization_digest=instruction.presentation_authorization_digest,
            policy_digest=instruction.policy_digest,
            answer_digest=answer.canonical_digest,
            citation_set_digest=citation_digest,
            unknown_set_digest=unknown_digest,
            source_binding_digest=source_digest,
            rendering_digest=rendering_digest,
            cleanup_digest=cleanup_digest,
            summary_character_count=len(draft.summary),
            citation_count=len(draft.citation_references),
            unknown_count=len(draft.unknowns),
            byte_count=len(encoded),
            presented_at=instruction.requested_at,
            expires_at=instruction.expires_at,
            source_verified=True,
            eligible_outcome_verified=True,
            content_verified=True,
            inert_rendering_verified=True,
            no_model_used=True,
            cleanup_verified=True,
            signature_verified=True,
            canonical_digest="0" * 64,
        )
        receipt = replace(receipt, canonical_digest=digest(payload(receipt)))
        return receipt, answer

    async def rehydrate(
        self,
        *,
        record: ProtectedAnswerPresentationRecord,
        presentation_authorization_digest: str,
        report: ProtectedDraftAdjudicationReport,
        draft: ProtectedModelResponseDraft,
        context: ProtectedModelContextPackage,
    ) -> ProtectedPresentedAnswer:
        instruction = ProtectedAnswerPresentationInstruction(
            presentation_id=record.presentation_id,
            adjudication_id=record.adjudication_id,
            adjudication_digest=record.adjudication_digest,
            invocation_id=record.invocation_id,
            invocation_digest=record.invocation_digest,
            context_id=record.context_id,
            context_digest=record.context_digest,
            context_package_digest=record.context_package_digest,
            draft_digest=record.draft_digest,
            report_digest=record.report_digest,
            organization_id=record.organization_id,
            environment_id=record.environment_id,
            consumer_subject_digest=record.consumer_subject_digest,
            presentation_authorization_digest=presentation_authorization_digest,
            policy_id=record.presentation_policy_id,
            policy_digest=record.presentation_policy_digest,
            rendering_profile_digest=record.rendering_digest,
            prohibited_output_profile_digest="0" * 64,
            media_type=record.media_type,
            maximum_summary_characters=record.summary_character_count,
            maximum_citation_count=record.citation_count,
            maximum_unknown_count=record.unknown_count,
            maximum_output_bytes=record.byte_count,
            requested_at=record.presented_at,
            expires_at=record.expires_at,
        )
        _, answer = await self.present(instruction, report, draft, context)
        if (
            presentation_authorization_digest != record.presentation_authorization_digest
            or answer.canonical_digest != record.answer_digest
            or answer.byte_count != record.byte_count
        ):
            raise ProtectedAnswerPresentationError("protected_answer_presentation_integrity_failed")
        return answer

    @staticmethod
    def _encoded(draft: ProtectedModelResponseDraft) -> bytes:
        return (
            draft.summary + "\n" + "\n".join(draft.citation_references + draft.unknowns)
        ).encode("utf-8")


class UnavailableTrustedProtectedAnswerPresenter:
    async def present(
        self,
        instruction: ProtectedAnswerPresentationInstruction,
        report: ProtectedDraftAdjudicationReport,
        draft: ProtectedModelResponseDraft,
        context: ProtectedModelContextPackage,
    ) -> tuple[ProtectedAnswerPresentationReceipt, ProtectedPresentedAnswer]:
        del instruction, report, draft, context
        raise ProtectedAnswerPresentationError(
            "protected_answer_presentation_presenter_unavailable"
        )

    async def rehydrate(
        self,
        *,
        record: ProtectedAnswerPresentationRecord,
        presentation_authorization_digest: str,
        report: ProtectedDraftAdjudicationReport,
        draft: ProtectedModelResponseDraft,
        context: ProtectedModelContextPackage,
    ) -> ProtectedPresentedAnswer:
        del record, presentation_authorization_digest, report, draft, context
        raise ProtectedAnswerPresentationError("protected_answer_presentation_answer_unavailable")
