from __future__ import annotations

from datetime import datetime
from uuid import uuid4

from atlas import __version__
from atlas.core.audit import AuditRecord, AuditSink
from atlas.modules.knowledge.application.ports import KnowledgeRetriever
from atlas.modules.knowledge.domain.models import RetrievalRequest, RetrievalResult


class KnowledgeRetrievalService:
    def __init__(self, *, retriever: KnowledgeRetriever, audit_sink: AuditSink) -> None:
        self._retriever = retriever
        self._audit_sink = audit_sink

    async def retrieve(
        self, request: RetrievalRequest, *, decision_id: str, requested_at: datetime
    ) -> RetrievalResult:
        result = await self._retriever.retrieve(request)
        await self._audit_sink.record(
            AuditRecord(
                event_id=f"evt_{uuid4().hex}",
                event_type="atlas.knowledge.retrieval.completed",
                schema_version="1.0",
                producer="project-atlas-api",
                producer_version=__version__,
                occurred_at=requested_at,
                correlation_id=request.correlation_id,
                subject_id=request.subject_id,
                actor_type="human",
                authentication_method=None,
                assurance_level=None,
                permission_id="ai.grounded-query.create",
                resource_type="resource.knowledge.retrieval",
                scope_reference="/".join(
                    (request.organization_id, request.environment_id, request.purpose)
                ),
                decision_id=decision_id,
                outcome="succeeded",
                result_code=(
                    "knowledge_retrieval_returned"
                    if result.hits
                    else "no_authorized_relevant_evidence"
                ),
            )
        )
        return result
