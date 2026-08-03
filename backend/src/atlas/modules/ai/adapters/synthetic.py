from __future__ import annotations

from atlas.modules.ai.domain.models import ModelInvocation, ProviderCompletion


class SyntheticOpenAICompatibleTransport:
    async def complete(self, invocation: ModelInvocation) -> ProviderCompletion:
        references = tuple(hit.citation.reference for hit in invocation.evidence[:2])
        products = ", ".join(dict.fromkeys(hit.product for hit in invocation.evidence))
        return ProviderCompletion(
            summary=(
                f"Authorized synthetic evidence for {products} was retrieved. "
                "The evidence can support investigation but does not authorize an operation."
            ),
            citation_references=references,
            unknowns=(
                "Live infrastructure state was not queried by this model request.",
                "The synthetic knowledge profile cannot confirm current service impact.",
            ),
            finish_reason="stop",
            model_id=invocation.model_id,
            input_tokens=128,
            output_tokens=48,
        )
