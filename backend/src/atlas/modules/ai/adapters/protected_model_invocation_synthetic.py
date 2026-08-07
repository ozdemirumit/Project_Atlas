from __future__ import annotations

from collections.abc import Callable
from dataclasses import asdict, replace
from datetime import UTC, datetime

from atlas.modules.ai.application.protected_model_invocation import (
    GovernedProtectedModelInvocationService,
)
from atlas.modules.ai.application.protected_model_invocation_ports import (
    ProtectedModelInvocationError,
)
from atlas.modules.ai.domain.protected_model_invocation import (
    ProtectedModelInvocationInstruction,
    ProtectedModelInvocationReceipt,
    ProtectedModelInvocationRecord,
    ProtectedModelResponseDraft,
)
from atlas.modules.knowledge.domain.model_context_assembly import ProtectedModelContextPackage


class SyntheticTrustedProtectedModelGateway:
    def __init__(self, *, clock: Callable[[], datetime] | None = None) -> None:
        self._clock = clock or (lambda: datetime.now(UTC))
        self._vault: dict[str, tuple[ProtectedModelResponseDraft, str, str]] = {}
        self.calls: list[ProtectedModelInvocationInstruction] = []

    async def invoke(
        self,
        instruction: ProtectedModelInvocationInstruction,
        context: ProtectedModelContextPackage,
    ) -> tuple[ProtectedModelInvocationReceipt, ProtectedModelResponseDraft]:
        self.calls.append(instruction)
        digest = GovernedProtectedModelInvocationService._digest
        payload = GovernedProtectedModelInvocationService._payload
        if (
            context.context_id != instruction.context_id
            or context.canonical_digest != instruction.context_package_digest
            or context.canonical_digest != digest(payload(context))
        ):
            raise ProtectedModelInvocationError(
                "protected_model_invocation_context_integrity_failed"
            )
        references = tuple(unit.evidence_reference_id for unit in context.evidence_units[:2])
        if not references:
            raise ProtectedModelInvocationError("protected_model_invocation_insufficient_evidence")
        now = self._clock()
        draft = ProtectedModelResponseDraft(
            invocation_id=instruction.invocation_id,
            summary=(
                "Authorized evidence supports further investigation; no infrastructure action "
                "is authorized."
            ),
            citation_references=references,
            unknowns=(
                "Live infrastructure state was not queried.",
                "Current service impact remains unconfirmed.",
            ),
            endpoint_profile_id=instruction.endpoint_profile_id,
            model_id=instruction.model_id,
            finish_reason="stop",
            response_schema_version=instruction.output_schema_version,
            input_tokens=context.estimated_token_count,
            output_tokens=48,
            generated_at=now,
            expires_at=instruction.expires_at,
            canonical_digest="0" * 64,
        )
        draft = replace(draft, canonical_digest=digest(payload(draft)))
        artifact_reference = (
            f"protected-model-draft-artifact.{instruction.invocation_id.rsplit('.', 1)[-1]}"
        )
        artifact_digest = digest(asdict(draft))
        self._vault[artifact_reference] = (
            draft,
            instruction.invocation_authorization_digest,
            artifact_digest,
        )
        receipt = ProtectedModelInvocationReceipt(
            invocation_id=instruction.invocation_id,
            schema_version="atlas.protected-model-invocation-receipt.v1",
            version=1,
            gateway_id="protected-model-gateway.synthetic",
            attested_by="subject.protected-model-gateway-attestor",
            context_id=instruction.context_id,
            context_digest=instruction.context_digest,
            context_package_digest=instruction.context_package_digest,
            authorization_context_digest=instruction.authorization_context_digest,
            endpoint_profile_id=instruction.endpoint_profile_id,
            endpoint_profile_digest=instruction.endpoint_profile_digest,
            model_id=instruction.model_id,
            response_schema_version=instruction.output_schema_version,
            protected_draft_reference=artifact_reference,
            protected_draft_digest=artifact_digest,
            draft_digest=draft.canonical_digest,
            citation_set_digest=digest(references),
            output_safety_digest=digest(["output-safety.no-tools-no-operation-claims-v1"]),
            input_tokens=draft.input_tokens,
            output_tokens=draft.output_tokens,
            finish_reason=draft.finish_reason,
            outcome="invocation-outcome.completed",
            invoked_at=now,
            expires_at=instruction.expires_at,
            tools_disabled=True,
            streaming_disabled=True,
            schema_verified=True,
            citations_verified=True,
            output_safety_verified=True,
            protected_vault_write_verified=True,
            signature_verified=True,
            canonical_digest="0" * 64,
        )
        receipt = replace(receipt, canonical_digest=digest(payload(receipt)))
        return receipt, draft

    async def rehydrate(
        self, *, record: ProtectedModelInvocationRecord, invocation_authorization_digest: str
    ) -> ProtectedModelResponseDraft:
        stored = self._vault.get(record.protected_draft_reference)
        if (
            stored is None
            or stored[1] != invocation_authorization_digest
            or stored[2] != record.protected_draft_digest
            or stored[0].canonical_digest != record.draft_digest
            or self._clock() >= record.expires_at
        ):
            raise ProtectedModelInvocationError("protected_model_invocation_draft_unavailable")
        return stored[0]


class UnavailableTrustedProtectedModelGateway:
    async def invoke(
        self,
        instruction: ProtectedModelInvocationInstruction,
        context: ProtectedModelContextPackage,
    ) -> tuple[ProtectedModelInvocationReceipt, ProtectedModelResponseDraft]:
        del instruction, context
        raise ProtectedModelInvocationError("protected_model_invocation_gateway_unavailable")

    async def rehydrate(
        self, *, record: ProtectedModelInvocationRecord, invocation_authorization_digest: str
    ) -> ProtectedModelResponseDraft:
        del record, invocation_authorization_digest
        raise ProtectedModelInvocationError("protected_model_invocation_draft_unavailable")
