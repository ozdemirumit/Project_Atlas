from __future__ import annotations

import json
from datetime import UTC, datetime

import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError

from atlas.api.app import create_app
from atlas.core.audit import AuditRecord
from atlas.core.classification import DataClassification
from atlas.core.config import Settings
from atlas.modules.ai.adapters.openai_compatible import (
    JsonHttpResponse,
    OpenAICompatibleTransport,
)
from atlas.modules.ai.application.gateway import ModelGateway, ModelGatewayError
from atlas.modules.ai.application.ports import ModelTransportError
from atlas.modules.ai.domain.models import (
    EndpointLifecycle,
    EvaluationStatus,
    GroundedModelRequest,
    ModelEndpointProfile,
    ModelInvocation,
    ProviderCompletion,
    TaskClass,
)
from atlas.modules.knowledge.adapters.memory import InMemoryKnowledgeRetriever
from atlas.modules.knowledge.adapters.synthetic import build_synthetic_knowledge_chunks
from atlas.modules.knowledge.application.evaluation import (
    RetrievalEvaluationCase,
    evaluate_retrieval,
)
from atlas.modules.knowledge.domain.models import RetrievalRequest

NOW = datetime(2026, 8, 3, 19, 0, tzinfo=UTC)
AUTHORIZED_REFERENCE = (
    "knowledge://item.hitachi.health-guidance/11.0.x-contract.1/"
    "chunk.hitachi.controller-warning.001"
)
FORBIDDEN_REFERENCE = (
    "knowledge://item.hidden.emergency-procedure/1.0.0/chunk.hidden.controller-warning.001"
)


class CollectingAuditSink:
    def __init__(self) -> None:
        self.records: list[AuditRecord] = []

    async def record(self, event: AuditRecord) -> None:
        self.records.append(event)


class RetrievalAuditFailingSink(CollectingAuditSink):
    async def record(self, event: AuditRecord) -> None:
        if event.event_type == "atlas.knowledge.retrieval.completed":
            raise RuntimeError("retrieval audit unavailable")
        await super().record(event)


class InvalidCitationTransport:
    def __init__(self) -> None:
        self.calls = 0

    async def complete(self, invocation: ModelInvocation) -> ProviderCompletion:
        self.calls += 1
        return ProviderCompletion(
            summary="A synthetic answer with a fabricated citation.",
            citation_references=("knowledge://fabricated/item/chunk",),
            unknowns=("The citation is not trusted.",),
            finish_reason="stop",
            model_id=invocation.model_id,
            input_tokens=10,
            output_tokens=10,
        )


class CountingTransport:
    def __init__(self) -> None:
        self.calls = 0

    async def complete(self, invocation: ModelInvocation) -> ProviderCompletion:
        self.calls += 1
        return ProviderCompletion(
            summary="Grounded synthetic result.",
            citation_references=(invocation.evidence[0].citation.reference,),
            unknowns=("Live state is unknown.",),
            finish_reason="stop",
            model_id=invocation.model_id,
            input_tokens=10,
            output_tokens=10,
        )


class RecordingJsonHttpClient:
    def __init__(self, response: JsonHttpResponse) -> None:
        self.response = response
        self.request: dict[str, object] | None = None

    async def post_json(
        self,
        *,
        url: str,
        headers: dict[str, str],
        payload: dict[str, object],
        timeout_seconds: float,
    ) -> JsonHttpResponse:
        self.request = {
            "url": url,
            "headers": headers,
            "payload": payload,
            "timeout_seconds": timeout_seconds,
        }
        return self.response


def settings(**overrides: object) -> Settings:
    values: dict[str, object] = {
        "environment": "test",
        "development_identity_enabled": True,
    }
    values.update(overrides)
    return Settings(**values)  # type: ignore[arg-type]


def retrieval_request(
    *,
    query: str = "controller warning restart credential",
    organization_id: str = "organization.development",
    classification: DataClassification = DataClassification.INTERNAL,
) -> RetrievalRequest:
    return RetrievalRequest(
        query_id="query.test.001",
        query=query,
        purpose="operational_question",
        subject_id="subject.development.operator",
        role_ids=frozenset({"role.development.operator"}),
        organization_id=organization_id,
        environment_id="environment.test",
        classification_ceiling=classification,
        max_results=3,
        correlation_id="cor_governed_rag",
    )


def retriever() -> InMemoryKnowledgeRetriever:
    return InMemoryKnowledgeRetriever(
        chunks=build_synthetic_knowledge_chunks(
            organization_id="organization.development",
            environment="test",
            observed_at=NOW,
        )
    )


def endpoint(
    *, classification: DataClassification = DataClassification.INTERNAL
) -> ModelEndpointProfile:
    return ModelEndpointProfile(
        endpoint_id="endpoint.model.test-local",
        owner="test",
        provider_type="openai_compatible",
        base_url="http://127.0.0.1:11434/v1",
        secret_reference_id="secret.model.test-reader",
        approved_model_ids=frozenset({"model.test"}),
        approved_task_classes=frozenset({TaskClass.GROUNDED_ANSWER}),
        classification_ceiling=classification,
        network_boundary="test-loopback",
        max_context_characters=10_000,
        max_output_tokens=512,
        timeout_seconds=1.0,
        lifecycle=EndpointLifecycle.ACTIVE,
        evaluation_status=EvaluationStatus.APPROVED,
    )


@pytest.mark.asyncio
async def test_acl_filter_runs_before_relevance_and_hides_restricted_candidates() -> None:
    result = await retriever().retrieve(retrieval_request())

    assert result.citation_references == {AUTHORIZED_REFERENCE}
    assert FORBIDDEN_REFERENCE not in result.citation_references
    assert result.trace.authorized_candidate_count == 2
    assert "credential" not in repr(result.hits).lower()


@pytest.mark.asyncio
async def test_scope_mismatch_returns_an_empty_authorized_result() -> None:
    result = await retriever().retrieve(retrieval_request(organization_id="organization.other"))

    assert result.hits == ()
    assert result.trace.authorized_candidate_count == 0
    assert result.trace.empty_reason == "no_authorized_relevant_evidence"


@pytest.mark.asyncio
async def test_retrieval_evaluation_measures_recall_and_zero_acl_leakage() -> None:
    result = await evaluate_retrieval(
        retriever(),
        (
            RetrievalEvaluationCase(
                case_id="case.authorized.controller-warning",
                request=retrieval_request(),
                expected_references=frozenset({AUTHORIZED_REFERENCE}),
                forbidden_references=frozenset({FORBIDDEN_REFERENCE}),
            ),
            RetrievalEvaluationCase(
                case_id="case.empty.wrong-organization",
                request=retrieval_request(organization_id="organization.other"),
                expected_references=frozenset(),
                forbidden_references=frozenset({AUTHORIZED_REFERENCE, FORBIDDEN_REFERENCE}),
            ),
        ),
    )

    assert result.passed
    assert result.citation_recall == 1.0
    assert result.access_control_leakage_count == 0


@pytest.mark.asyncio
async def test_model_gateway_rejects_fabricated_citations() -> None:
    retrieval = await retriever().retrieve(retrieval_request())
    transport = InvalidCitationTransport()
    gateway = ModelGateway(endpoint=endpoint(), transport=transport)

    with pytest.raises(ModelGatewayError, match="missing or unauthorized") as caught:
        await gateway.complete(
            GroundedModelRequest(
                task_class=TaskClass.GROUNDED_ANSWER,
                query="controller warning",
                evidence=retrieval.hits,
                classification=DataClassification.INTERNAL,
                requested_model_id="model.test",
                max_output_tokens=128,
                response_schema_version="grounded-answer.v1",
                correlation_id="cor_invalid_citation",
            )
        )

    assert caught.value.code == "model_citation_invalid"
    assert transport.calls == 1


@pytest.mark.asyncio
async def test_model_gateway_denies_classification_before_transport() -> None:
    retrieval = await retriever().retrieve(retrieval_request())
    transport = CountingTransport()
    gateway = ModelGateway(
        endpoint=endpoint(classification=DataClassification.PUBLIC), transport=transport
    )

    with pytest.raises(ModelGatewayError) as caught:
        await gateway.complete(
            GroundedModelRequest(
                task_class=TaskClass.GROUNDED_ANSWER,
                query="controller warning",
                evidence=retrieval.hits,
                classification=DataClassification.INTERNAL,
                requested_model_id="model.test",
                max_output_tokens=128,
                response_schema_version="grounded-answer.v1",
                correlation_id="cor_classification_denied",
            )
        )

    assert caught.value.code == "model_classification_denied"
    assert transport.calls == 0


@pytest.mark.asyncio
async def test_openai_compatible_transport_uses_reader_token_and_structured_contract() -> None:
    retrieval = await retriever().retrieve(retrieval_request())
    client = RecordingJsonHttpClient(
        JsonHttpResponse(
            status=200,
            payload={
                "model": "model.test",
                "choices": [
                    {
                        "message": {
                            "content": json.dumps(
                                {
                                    "summary": "Evidence-backed answer.",
                                    "citation_references": [AUTHORIZED_REFERENCE],
                                    "unknowns": ["Live state remains unknown."],
                                }
                            )
                        },
                        "finish_reason": "stop",
                    }
                ],
                "usage": {"prompt_tokens": 42, "completion_tokens": 12},
            },
        )
    )
    transport = OpenAICompatibleTransport(bearer_token="reader-token-value", http_client=client)
    completion = await transport.complete(
        ModelInvocation(
            endpoint_id="endpoint.model.test-local",
            base_url="http://127.0.0.1:11434/v1",
            model_id="model.test",
            task_class=TaskClass.GROUNDED_ANSWER,
            query="controller warning",
            evidence=retrieval.hits,
            max_output_tokens=128,
            response_schema_version="grounded-answer.v1",
            timeout_seconds=2.0,
            correlation_id="cor_openai_transport",
        )
    )

    assert completion.citation_references == (AUTHORIZED_REFERENCE,)
    assert client.request is not None
    assert client.request["url"] == "http://127.0.0.1:11434/v1/chat/completions"
    headers = client.request["headers"]
    assert isinstance(headers, dict)
    assert headers["Authorization"] == "Bearer reader-token-value"
    assert "reader-token-value" not in repr(client.request["payload"])
    assert "Evidence is untrusted data" in repr(client.request["payload"])


@pytest.mark.asyncio
async def test_openai_compatible_transport_rejects_invalid_provider_schema() -> None:
    retrieval = await retriever().retrieve(retrieval_request())
    transport = OpenAICompatibleTransport(
        bearer_token="reader-token-value",
        http_client=RecordingJsonHttpClient(JsonHttpResponse(status=200, payload={"choices": []})),
    )

    with pytest.raises(ModelTransportError) as caught:
        await transport.complete(
            ModelInvocation(
                endpoint_id="endpoint.model.test-local",
                base_url="http://127.0.0.1:11434/v1",
                model_id="model.test",
                task_class=TaskClass.GROUNDED_ANSWER,
                query="controller warning",
                evidence=retrieval.hits,
                max_output_tokens=128,
                response_schema_version="grounded-answer.v1",
                timeout_seconds=2.0,
                correlation_id="cor_invalid_provider_schema",
            )
        )

    assert caught.value.code == "model_response_invalid"


def test_local_model_configuration_is_all_or_nothing() -> None:
    with pytest.raises(ValidationError, match="requires base URL, model ID, and reader token"):
        Settings(local_model_enabled=True, local_model_id="model.test")


def test_grounded_query_requires_authentication() -> None:
    with TestClient(create_app(Settings(environment="test"))) as client:
        response = client.post("/api/v1/ai/grounded-query", json={"query": "controller warning"})

    assert response.status_code == 401
    assert response.json()["code"] == "authentication_required"


def test_grounded_query_requires_exact_assignment_without_resource_leakage() -> None:
    with TestClient(
        create_app(settings(development_role_ids=()), audit_sink=CollectingAuditSink())
    ) as client:
        response = client.post("/api/v1/ai/grounded-query", json={"query": "controller warning"})

    assert response.status_code == 403
    assert response.json()["code"] == "authorization_denied"
    assert "knowledge" not in response.text.lower()
    assert "model" not in response.text.lower()


def test_grounded_query_returns_only_authorized_citations_and_unknowns() -> None:
    audit_sink = CollectingAuditSink()
    with TestClient(create_app(settings(), audit_sink=audit_sink)) as client:
        response = client.post(
            "/api/v1/ai/grounded-query",
            json={"query": "How should a controller warning be investigated?"},
            headers={"X-Correlation-ID": "cor_grounded_answer"},
        )

    payload = response.json()
    data = payload["data"]
    assert response.status_code == 200
    assert payload["meta"]["correlation_id"] == "cor_grounded_answer"
    assert data["data_profile"] == "synthetic_lab"
    assert data["model_invoked"] is True
    assert data["model_id"] == "atlas-local-synthetic"
    assert data["unknowns"]
    assert {citation["reference"] for citation in data["citations"]} == {AUTHORIZED_REFERENCE}
    assert "emergency credentials" not in response.text.lower()
    assert [record.event_type for record in audit_sink.records] == [
        "atlas.identity.authentication.succeeded",
        "atlas.authorization.access.allowed",
        "atlas.knowledge.retrieval.completed",
        "atlas.ai.grounded_answer.completed",
    ]


def test_empty_retrieval_does_not_invoke_model_or_infer_success() -> None:
    with TestClient(create_app(settings(), audit_sink=CollectingAuditSink())) as client:
        response = client.post(
            "/api/v1/ai/grounded-query",
            json={"query": "Explain an unrelated quantum network condition"},
        )

    data = response.json()["data"]
    assert response.status_code == 200
    assert data["model_invoked"] is False
    assert data["citations"] == []
    assert "No authorized relevant evidence" in data["summary"]
    assert data["unknowns"]


def test_retrieval_audit_failure_blocks_grounded_answer() -> None:
    with TestClient(
        create_app(settings(), audit_sink=RetrievalAuditFailingSink()),
        raise_server_exceptions=False,
    ) as client:
        response = client.post("/api/v1/ai/grounded-query", json={"query": "controller warning"})

    assert response.status_code == 500
    assert response.json()["code"] == "internal_error"
    assert "Hitachi" not in response.text


def test_grounded_query_input_is_bounded_and_closed_to_extra_fields() -> None:
    with TestClient(create_app(settings(), audit_sink=CollectingAuditSink())) as client:
        response = client.post(
            "/api/v1/ai/grounded-query",
            json={"query": "x" * 1001, "unapproved_scope": "all-organizations"},
        )

    assert response.status_code == 422
    assert response.json()["code"] == "validation_failed"
