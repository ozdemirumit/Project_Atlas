from __future__ import annotations

import asyncio

from atlas.modules.ai.application.ports import ModelTransport, ModelTransportError
from atlas.modules.ai.domain.models import (
    EndpointLifecycle,
    EvaluationStatus,
    GroundedAnswerDraft,
    GroundedModelRequest,
    ModelEndpointProfile,
    ModelInvocation,
)


class ModelGatewayError(Exception):
    def __init__(self, code: str, detail: str) -> None:
        super().__init__(detail)
        self.code = code
        self.detail = detail


class ModelGateway:
    def __init__(self, *, endpoint: ModelEndpointProfile, transport: ModelTransport) -> None:
        self._endpoint = endpoint
        self._transport = transport

    async def complete(self, request: GroundedModelRequest) -> GroundedAnswerDraft:
        endpoint = self._endpoint
        if endpoint.lifecycle is not EndpointLifecycle.ACTIVE:
            raise ModelGatewayError("model_endpoint_unavailable", "The model endpoint is disabled.")
        if endpoint.evaluation_status is not EvaluationStatus.APPROVED:
            raise ModelGatewayError(
                "model_endpoint_not_approved", "The model endpoint has not passed evaluation."
            )
        if request.task_class not in endpoint.approved_task_classes:
            raise ModelGatewayError(
                "model_task_denied", "The endpoint is not approved for this task."
            )
        if request.requested_model_id not in endpoint.approved_model_ids:
            raise ModelGatewayError("model_identity_denied", "The requested model is not approved.")
        if not endpoint.classification_ceiling.permits(request.classification):
            raise ModelGatewayError(
                "model_classification_denied",
                "The endpoint cannot receive the requested data classification.",
            )
        if not request.evidence:
            raise ModelGatewayError(
                "insufficient_evidence", "Grounded model requests require authorized evidence."
            )
        if not 1 <= request.max_output_tokens <= endpoint.max_output_tokens:
            raise ModelGatewayError("model_output_limit", "The requested output limit is invalid.")
        context_size = len(request.query) + sum(len(hit.excerpt) for hit in request.evidence)
        if context_size > endpoint.max_context_characters:
            raise ModelGatewayError("model_context_limit", "The model context limit was exceeded.")

        invocation = ModelInvocation(
            endpoint_id=endpoint.endpoint_id,
            base_url=endpoint.base_url,
            model_id=request.requested_model_id,
            task_class=request.task_class,
            query=request.query,
            evidence=request.evidence,
            max_output_tokens=request.max_output_tokens,
            response_schema_version=request.response_schema_version,
            timeout_seconds=endpoint.timeout_seconds,
            correlation_id=request.correlation_id,
        )
        try:
            async with asyncio.timeout(endpoint.timeout_seconds):
                completion = await self._transport.complete(invocation)
        except TimeoutError as error:
            raise ModelGatewayError("model_timeout", "The model request timed out.") from error
        except ModelTransportError as error:
            raise ModelGatewayError(
                "model_provider_unavailable", "The model provider returned an invalid response."
            ) from error

        if completion.model_id != request.requested_model_id:
            raise ModelGatewayError(
                "model_identity_mismatch", "The provider returned an unexpected model identity."
            )
        if not completion.summary.strip() or not completion.unknowns:
            raise ModelGatewayError(
                "model_schema_invalid", "The model output omitted required structured fields."
            )
        citations = {hit.citation.reference: hit.citation for hit in request.evidence}
        returned_references = tuple(dict.fromkeys(completion.citation_references))
        if not returned_references or any(ref not in citations for ref in returned_references):
            raise ModelGatewayError(
                "model_citation_invalid",
                "The model output contains missing or unauthorized citation references.",
            )
        return GroundedAnswerDraft(
            summary=completion.summary,
            citations=tuple(citations[ref] for ref in returned_references),
            unknowns=completion.unknowns,
            endpoint_id=endpoint.endpoint_id,
            model_id=completion.model_id,
            finish_reason=completion.finish_reason,
            response_schema_version=request.response_schema_version,
        )
