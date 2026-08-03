from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from uuid import uuid4

from atlas import __version__
from atlas.core.audit import AuditRecord, AuditSink
from atlas.core.classification import DataClassification
from atlas.modules.ai.application.gateway import ModelGateway
from atlas.modules.ai.domain.models import (
    GroundedAnswer,
    GroundedModelRequest,
    TaskClass,
)
from atlas.modules.knowledge.application.service import KnowledgeRetrievalService
from atlas.modules.knowledge.domain.models import RetrievalRequest


@dataclass(frozen=True, slots=True)
class GroundedQueryContext:
    subject_id: str
    role_ids: frozenset[str]
    organization_id: str
    environment_id: str
    correlation_id: str
    decision_id: str
    requested_at: datetime
    classification_ceiling: DataClassification = DataClassification.INTERNAL


class GroundedAnswerService:
    def __init__(
        self,
        *,
        retrieval_service: KnowledgeRetrievalService,
        model_gateway: ModelGateway,
        audit_sink: AuditSink,
        model_id: str,
        data_profile: str,
    ) -> None:
        self._retrieval_service = retrieval_service
        self._model_gateway = model_gateway
        self._audit_sink = audit_sink
        self._model_id = model_id
        self._data_profile = data_profile

    async def answer(
        self, *, query: str, max_results: int, context: GroundedQueryContext
    ) -> GroundedAnswer:
        query_id = f"qry_{uuid4().hex}"
        retrieval = await self._retrieval_service.retrieve(
            RetrievalRequest(
                query_id=query_id,
                query=query,
                purpose="operational_question",
                subject_id=context.subject_id,
                role_ids=context.role_ids,
                organization_id=context.organization_id,
                environment_id=context.environment_id,
                classification_ceiling=context.classification_ceiling,
                max_results=max_results,
                correlation_id=context.correlation_id,
            ),
            decision_id=context.decision_id,
            requested_at=context.requested_at,
        )

        if retrieval.hits:
            draft = await self._model_gateway.complete(
                GroundedModelRequest(
                    task_class=TaskClass.GROUNDED_ANSWER,
                    query=query,
                    evidence=retrieval.hits,
                    classification=context.classification_ceiling,
                    requested_model_id=self._model_id,
                    max_output_tokens=512,
                    response_schema_version="grounded-answer.v1",
                    correlation_id=context.correlation_id,
                )
            )
            answer = GroundedAnswer(
                answer_id=f"ans_{uuid4().hex}",
                query_id=query_id,
                summary=draft.summary,
                citations=draft.citations,
                unknowns=draft.unknowns,
                model_invoked=True,
                endpoint_id=draft.endpoint_id,
                model_id=draft.model_id,
                response_schema_version=draft.response_schema_version,
                data_profile=self._data_profile,
                generated_at=context.requested_at,
            )
            result_code = "grounded_answer_returned"
        else:
            answer = GroundedAnswer(
                answer_id=f"ans_{uuid4().hex}",
                query_id=query_id,
                summary="No authorized relevant evidence was found. No conclusion was generated.",
                citations=(),
                unknowns=("The requested question cannot be answered from authorized evidence.",),
                model_invoked=False,
                endpoint_id=None,
                model_id=None,
                response_schema_version="grounded-answer.v1",
                data_profile=self._data_profile,
                generated_at=context.requested_at,
            )
            result_code = "grounded_answer_no_evidence"

        await self._audit_sink.record(
            AuditRecord(
                event_id=f"evt_{uuid4().hex}",
                event_type="atlas.ai.grounded_answer.completed",
                schema_version="1.0",
                producer="project-atlas-api",
                producer_version=__version__,
                occurred_at=context.requested_at,
                correlation_id=context.correlation_id,
                subject_id=context.subject_id,
                actor_type="human",
                authentication_method=None,
                assurance_level=None,
                permission_id="ai.grounded-query.create",
                resource_type="resource.ai.grounded-query",
                scope_reference="/".join(
                    (context.organization_id, context.environment_id, "grounded-query")
                ),
                decision_id=context.decision_id,
                outcome="succeeded",
                result_code=result_code,
            )
        )
        return answer
