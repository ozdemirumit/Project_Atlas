from __future__ import annotations

from dataclasses import replace
from datetime import UTC, datetime, timedelta

import pytest

from atlas.core.classification import DataClassification
from atlas.modules.ai.application.service import GroundedQueryContext
from atlas.modules.ai.domain.models import GroundedAnswer
from atlas.modules.conversations.adapters.grounded import GroundedConversationGenerator
from atlas.modules.conversations.application.ports import ConversationGenerationUnavailable
from atlas.modules.conversations.domain.models import (
    NO_EXECUTION_SAFETY_NOTICE,
    ConversationGenerationRequest,
    ConversationScope,
    ConversationTurnStatus,
)
from atlas.modules.knowledge.domain.models import Citation

NOW = datetime(2026, 8, 13, 12, 0, tzinfo=UTC)
SCOPE = ConversationScope("organization.atlas", "environment.development", "site.local")


class StubGroundedAnswerService:
    def __init__(self, answer: GroundedAnswer) -> None:
        self.answer_result = answer
        self.calls: list[tuple[str, int, GroundedQueryContext]] = []
        self.error: Exception | None = None

    async def answer(
        self, *, query: str, max_results: int, context: GroundedQueryContext
    ) -> GroundedAnswer:
        self.calls.append((query, max_results, context))
        if self.error is not None:
            raise self.error
        return self.answer_result


def citation(**changes: object) -> Citation:
    values: dict[str, object] = {
        "reference": "citation.storage.health.1",
        "item_id": "artifact.storage.health",
        "item_version": "3",
        "chunk_id": "evidence.storage.health.1",
        "title": "Authorized storage health observation",
        "source_class": "health_observation",
        "source_reference": "atlas://storage/health/1",
        "location": "controller/health",
        "content_checksum": "a" * 64,
        "observed_at": NOW,
        "classification": DataClassification.INTERNAL,
    }
    values.update(changes)
    return Citation(**values)  # type: ignore[arg-type]


def answer(*, citations: tuple[Citation, ...] | None = None) -> GroundedAnswer:
    return GroundedAnswer(
        answer_id="answer.storage.health.1",
        query_id="query.storage.health.1",
        summary="The authorized evidence reports normal controller health.",
        citations=(citation(),) if citations is None else citations,
        unknowns=("Workload-path telemetry was not available.",),
        model_invoked=True,
        endpoint_id="endpoint.local",
        model_id="model.local",
        response_schema_version="grounded-answer.v1",
        data_profile="internal",
        generated_at=NOW,
    )


def context() -> GroundedQueryContext:
    return GroundedQueryContext(
        subject_id="subject.operator",
        role_ids=frozenset({"role.infrastructure-operator", "group.storage"}),
        organization_id=SCOPE.organization_id,
        environment_id=SCOPE.environment_id,
        correlation_id="correlation.conversation.1",
        decision_id="decision.conversation.1",
        requested_at=NOW,
        classification_ceiling=DataClassification.INTERNAL,
    )


def request() -> ConversationGenerationRequest:
    return ConversationGenerationRequest(
        request_digest="digest.request.1",
        conversation_id="conversation.storage.1",
        conversation_version=2,
        scope=SCOPE,
        owner_subject_id="subject.operator",
        role_ids=context().role_ids,
        decision_id=context().decision_id,
        target_id="asset.storage.primary",
        question="What is the current controller health?",
        prior_turns=(),
        requested_at=NOW,
        correlation_id="correlation.conversation.1",
    )


def generator(
    result: GroundedAnswer | None = None,
) -> tuple[GroundedConversationGenerator, StubGroundedAnswerService]:
    service = StubGroundedAnswerService(result or answer())
    return (
        GroundedConversationGenerator(
            grounded_answer_service=service,
            max_results=7,
        ),
        service,
    )


@pytest.mark.asyncio
async def test_maps_authorized_citations_and_preserves_exact_request_context() -> None:
    adapter, service = generator()

    result = await adapter.generate(request())

    assert len(service.calls) == 1
    query, max_results, called_context = service.calls[0]
    assert "Authorized target: asset.storage.primary" in query
    assert f"Current question: {request().question}" in query
    assert max_results == 7
    assert called_context == context()
    assert result.request_digest == request().request_digest
    assert result.conversation_id == request().conversation_id
    assert result.scope == SCOPE
    assert result.owner_subject_id == request().owner_subject_id
    assert result.target_id == request().target_id
    assert result.status is ConversationTurnStatus.COMPLETED
    assert result.evidence_references[0].evidence_id == "evidence.storage.health.1"
    assert result.evidence_references[0].citation == "citation.storage.health.1"
    assert result.evidence_references[0].artifact_id == "artifact.storage.health"
    assert result.evidence_references[0].artifact_version == "3"
    assert result.evidence_references[0].source_type == "health_observation"
    assert result.evidence_references[0].source_reference == "atlas://storage/health/1"
    assert result.evidence_references[0].observed_at == NOW
    assert result.artifact_references == ()
    assert result.assumptions == ()
    assert result.safety_notice == NO_EXECUTION_SAFETY_NOTICE
    assert not any(result.authority.canonical_value().values())


@pytest.mark.asyncio
async def test_no_citations_produces_explicit_partial_result() -> None:
    partial_answer = replace(
        answer(citations=()),
        model_invoked=False,
        endpoint_id=None,
        model_id=None,
        summary="No authorized relevant evidence was found. No conclusion was generated.",
    )
    adapter, _ = generator(partial_answer)

    result = await adapter.generate(request())

    assert result.status is ConversationTurnStatus.PARTIAL
    assert result.evidence_references == ()
    assert result.unknowns == partial_answer.unknowns
    assert result.confidence_basis == (
        "No authorized citation was returned; no conclusion is treated as complete.",
    )
    assert result.failure_code is None


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "changed_request",
    (
        replace(request(), owner_subject_id="subject.other"),
        replace(request(), role_ids=frozenset({"role.other"})),
        replace(request(), decision_id="decision.other"),
        replace(request(), correlation_id="correlation.other"),
        replace(request(), requested_at=NOW + timedelta(seconds=1)),
    ),
)
async def test_constructs_a_fresh_grounded_context_from_each_request(
    changed_request: ConversationGenerationRequest,
) -> None:
    adapter, service = generator()
    if changed_request.requested_at != NOW:
        service.answer_result = replace(
            service.answer_result,
            generated_at=changed_request.requested_at,
        )

    await adapter.generate(changed_request)

    called_context = service.calls[0][2]
    assert called_context.subject_id == changed_request.owner_subject_id
    assert called_context.role_ids == changed_request.role_ids
    assert called_context.decision_id == changed_request.decision_id
    assert called_context.correlation_id == changed_request.correlation_id
    assert called_context.requested_at == changed_request.requested_at


@pytest.mark.asyncio
async def test_preserves_opaque_vendor_artifact_version_without_inventing_one() -> None:
    adapter, _ = generator(answer(citations=(citation(item_version="11.0.x-contract.1"),)))

    result = await adapter.generate(request())

    assert result.evidence_references[0].artifact_version == "11.0.x-contract.1"


@pytest.mark.asyncio
async def test_rejects_answer_time_or_classification_outside_bound_context() -> None:
    mismatched_time, _ = generator(replace(answer(), generated_at=NOW + timedelta(seconds=1)))
    restricted, _ = generator(
        answer(citations=(citation(classification=DataClassification.RESTRICTED),))
    )

    with pytest.raises(ConversationGenerationUnavailable):
        await mismatched_time.generate(request())
    with pytest.raises(ConversationGenerationUnavailable):
        await restricted.generate(request())


@pytest.mark.asyncio
async def test_rejects_duplicate_evidence_and_citations_without_model_invocation() -> None:
    duplicate, _ = generator(answer(citations=(citation(), citation(reference="citation.2"))))
    impossible, _ = generator(
        replace(answer(), model_invoked=False, endpoint_id=None, model_id=None)
    )

    with pytest.raises(ConversationGenerationUnavailable):
        await duplicate.generate(request())
    with pytest.raises(ConversationGenerationUnavailable):
        await impossible.generate(request())


@pytest.mark.asyncio
async def test_wraps_grounded_service_unavailability_without_leaking_provider_details() -> None:
    adapter, service = generator()
    service.error = RuntimeError("provider secret and endpoint details")

    with pytest.raises(
        ConversationGenerationUnavailable,
        match="conversation_generation_unavailable",
    ):
        await adapter.generate(request())
