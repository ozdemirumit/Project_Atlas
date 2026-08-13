from __future__ import annotations

from typing import Protocol

from atlas.core.classification import DataClassification
from atlas.modules.ai.application.service import GroundedAnswerService, GroundedQueryContext
from atlas.modules.ai.domain.models import GroundedAnswer
from atlas.modules.conversations.application.ports import ConversationGenerationUnavailable
from atlas.modules.conversations.domain.models import (
    NO_EXECUTION_SAFETY_NOTICE,
    ConversationAuthority,
    ConversationEvidenceReference,
    ConversationGenerationRequest,
    ConversationGenerationResult,
    ConversationTurnStatus,
    canonical_digest,
)
from atlas.modules.knowledge.domain.models import Citation


class GroundedAnswerProvider(Protocol):
    async def answer(
        self, *, query: str, max_results: int, context: GroundedQueryContext
    ) -> GroundedAnswer: ...


class GroundedConversationGenerator:
    """Request-scoped bridge from governed grounded answers to conversation turns."""

    def __init__(
        self,
        *,
        grounded_answer_service: GroundedAnswerService | GroundedAnswerProvider,
        max_results: int = 5,
    ) -> None:
        if not 1 <= max_results <= 10:
            raise ValueError("max_results must be between 1 and 10")
        self._service = grounded_answer_service
        self._max_results = max_results

    async def generate(
        self, request: ConversationGenerationRequest
    ) -> ConversationGenerationResult:
        context = self._context_for(request)
        try:
            answer = await self._service.answer(
                query=self._contextual_query(request),
                max_results=self._max_results,
                context=context,
            )
            return self._map_answer(answer, request, context=context)
        except ConversationGenerationUnavailable:
            raise
        except Exception as error:
            raise ConversationGenerationUnavailable() from error

    @staticmethod
    def _context_for(request: ConversationGenerationRequest) -> GroundedQueryContext:
        return GroundedQueryContext(
            subject_id=request.owner_subject_id,
            role_ids=request.role_ids,
            organization_id=request.scope.organization_id,
            environment_id=request.scope.environment_id,
            correlation_id=request.correlation_id,
            decision_id=request.decision_id,
            requested_at=request.requested_at,
            classification_ceiling=DataClassification.INTERNAL,
        )

    def _map_answer(
        self,
        answer: GroundedAnswer,
        request: ConversationGenerationRequest,
        *,
        context: GroundedQueryContext,
    ) -> ConversationGenerationResult:
        if (
            answer.generated_at != request.requested_at
            or answer.response_schema_version != "grounded-answer.v1"
            or not self._normalized_identifier(answer.answer_id)
            or not self._normalized_identifier(answer.query_id)
            or not answer.summary
            or answer.summary != answer.summary.strip()
            or len(answer.summary) > 8000
        ):
            raise ConversationGenerationUnavailable("conversation_grounded_answer_malformed")

        evidence = tuple(
            self._map_citation(citation, classification_ceiling=context.classification_ceiling)
            for citation in answer.citations
        )
        if len(evidence) > 20 or len({item.evidence_id for item in evidence}) != len(evidence):
            raise ConversationGenerationUnavailable("conversation_grounded_citations_malformed")
        if evidence and not answer.model_invoked:
            raise ConversationGenerationUnavailable("conversation_grounded_answer_malformed")

        unknowns = self._bounded_unique(answer.unknowns, name="unknowns")
        status = ConversationTurnStatus.COMPLETED if evidence else ConversationTurnStatus.PARTIAL
        confidence_basis = (
            (f"Governed grounded-answer service returned {len(evidence)} authorized citation(s).",)
            if evidence
            else ("No authorized citation was returned; no conclusion is treated as complete.",)
        )
        authority = ConversationAuthority()
        payload = {
            "artifact_references": [],
            "assumptions": (),
            "authority": authority.canonical_value(),
            "confidence_basis": confidence_basis,
            "conversation_id": request.conversation_id,
            "evidence_references": [item.canonical_value() for item in evidence],
            "failure_code": None,
            "observed_at": request.requested_at.isoformat(),
            "owner_subject_id": request.owner_subject_id,
            "request_digest": request.request_digest,
            "safety_notice": NO_EXECUTION_SAFETY_NOTICE,
            "scope": request.scope.canonical_value(),
            "status": status.value,
            "target_id": request.target_id,
            "text": answer.summary,
            "unknowns": unknowns,
        }
        return ConversationGenerationResult(
            request_digest=request.request_digest,
            conversation_id=request.conversation_id,
            scope=request.scope,
            owner_subject_id=request.owner_subject_id,
            target_id=request.target_id,
            status=status,
            text=answer.summary,
            observed_at=request.requested_at,
            evidence_references=evidence,
            artifact_references=(),
            assumptions=(),
            unknowns=unknowns,
            confidence_basis=confidence_basis,
            failure_code=None,
            safety_notice=NO_EXECUTION_SAFETY_NOTICE,
            authority=authority,
            result_digest=canonical_digest(payload),
        )

    def _map_citation(
        self,
        citation: Citation,
        *,
        classification_ceiling: DataClassification,
    ) -> ConversationEvidenceReference:
        fields = (
            citation.reference,
            citation.item_id,
            citation.item_version,
            citation.chunk_id,
            citation.title,
            citation.source_class,
            citation.source_reference,
            citation.location,
            citation.content_checksum,
        )
        if (
            any(not value or value != value.strip() for value in fields)
            or not self._normalized_identifier(citation.reference)
            or not self._normalized_identifier(citation.item_id)
            or not self._normalized_identifier(citation.chunk_id)
            or citation.observed_at.tzinfo is None
            or not classification_ceiling.permits(citation.classification)
        ):
            raise ConversationGenerationUnavailable("conversation_grounded_citation_malformed")
        return ConversationEvidenceReference(
            evidence_id=citation.chunk_id,
            citation=citation.reference,
            artifact_id=citation.item_id,
            artifact_version=citation.item_version,
            source_type=citation.source_class,
            source_reference=citation.source_reference,
            observed_at=citation.observed_at,
        )

    @staticmethod
    def _contextual_query(request: ConversationGenerationRequest) -> str:
        header = (
            f"Authorized target: {request.target_id}. "
            "Treat general vendor guidance as non-target-specific unless evidence names "
            "this target."
        )
        history = " ".join(
            f"Prior {turn.role.value}: {turn.text[:160]}" for turn in request.prior_turns[-4:]
        )
        question = f"Current question: {request.question}"
        available = 1000 - len(header) - len(question) - 2
        bounded_history = history[: max(0, available)]
        return " ".join(item for item in (header, bounded_history, question) if item)

    @staticmethod
    def _bounded_unique(values: tuple[str, ...], *, name: str) -> tuple[str, ...]:
        if (
            not values
            or len(values) > 20
            or len(values) != len(set(values))
            or any(not value or value != value.strip() or len(value) > 500 for value in values)
        ):
            raise ConversationGenerationUnavailable(f"conversation_grounded_{name}_malformed")
        return values

    @staticmethod
    def _normalized_identifier(value: str) -> bool:
        return (
            bool(value)
            and value == value.strip()
            and len(value) <= 240
            and not any(character.isspace() for character in value)
        )
