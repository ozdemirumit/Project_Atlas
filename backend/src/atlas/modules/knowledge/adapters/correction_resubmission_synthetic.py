from __future__ import annotations

import json
from collections.abc import Callable
from dataclasses import asdict, replace
from datetime import UTC, datetime
from hashlib import sha256

from atlas.modules.knowledge.application.correction_resubmission_ports import (
    OperationalKnowledgeCorrectionError,
)
from atlas.modules.knowledge.domain.correction_resubmission import (
    AWAITING_REVIEWER,
    OperationalKnowledgeCorrectionInstruction,
    OperationalKnowledgeCorrectionReceipt,
)


def _digest(value: object) -> str:
    return sha256(
        json.dumps(
            value,
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=True,
            default=lambda item: item.isoformat() if isinstance(item, datetime) else str(item),
        ).encode("ascii")
    ).hexdigest()


class SyntheticOperationalKnowledgeCorrectionAdapter:
    def __init__(self, *, clock: Callable[[], datetime] | None = None) -> None:
        self._clock = clock or (lambda: datetime.now(UTC))
        self.calls: list[OperationalKnowledgeCorrectionInstruction] = []

    async def correct_and_resubmit(
        self, instruction: OperationalKnowledgeCorrectionInstruction
    ) -> OperationalKnowledgeCorrectionReceipt:
        self.calls.append(instruction)
        seed = instruction.correction_id.rsplit(".", 1)[-1]
        receipt = OperationalKnowledgeCorrectionReceipt(
            correction_id=instruction.correction_id,
            schema_version="atlas.operational-knowledge-correction-receipt.v1",
            version=1,
            adapter_id="operational-knowledge-correction-adapter.synthetic",
            attested_by="subject.operational-knowledge-correction-attestor",
            source_review_request_id=instruction.source_review_request_id,
            source_review_request_digest=instruction.source_review_request_digest,
            decision_aggregate_digest=instruction.decision_aggregate_digest,
            correction_submission_id=instruction.correction_submission_id,
            correction_submission_digest=instruction.correction_submission_digest,
            new_draft_id=instruction.new_draft_id,
            new_draft_version_id=instruction.new_draft_version_id,
            new_draft_artifact_id=f"knowledge-draft-artifact.correction-{seed}",
            new_draft_schema_version="atlas.operational-evidence-knowledge-artifact.v1",
            new_draft_content_digest=_digest(
                [instruction.correction_submission_digest, "corrected-content"]
            ),
            new_draft_metadata_digest=_digest(
                [instruction.source_draft_digest, "corrected-metadata"]
            ),
            new_provenance_digest=_digest(
                [instruction.decision_aggregate_digest, instruction.correction_submission_digest]
            ),
            new_draft_item_count=1,
            new_draft_bytes=1024,
            new_review_request_id=instruction.new_review_request_id,
            new_manifest_id=f"knowledge-review-manifest.correction-{seed}",
            new_manifest_artifact_id=f"knowledge-review-manifest-artifact.correction-{seed}",
            new_manifest_schema_version="atlas.operational-knowledge-review-manifest.v1",
            new_manifest_digest=_digest([instruction.new_review_request_id, "manifest"]),
            new_routing_digest=_digest(
                [instruction.domain_queue_id, instruction.security_queue_id]
            ),
            new_governance_digest=_digest(
                [instruction.correction_policy_digest, instruction.classification]
            ),
            new_artifact_digest=_digest([instruction.new_draft_id, "artifact"]),
            domain_status=AWAITING_REVIEWER,
            security_status=AWAITING_REVIEWER,
            manifest_bytes=2048,
            created_at=self._clock(),
            immutable_draft_confirmed=True,
            immutable_manifest_confirmed=True,
            encrypted_at_rest=True,
            transient_buffers_erased=True,
            artifact_channel_closed=True,
            signature_verified=True,
            instruction_digest=_digest(asdict(instruction)),
            canonical_digest="0" * 64,
        )
        payload = asdict(receipt)
        payload.pop("canonical_digest")
        return replace(receipt, canonical_digest=_digest(payload))


class UnavailableOperationalKnowledgeCorrectionAdapter:
    async def correct_and_resubmit(
        self, instruction: OperationalKnowledgeCorrectionInstruction
    ) -> OperationalKnowledgeCorrectionReceipt:
        del instruction
        raise OperationalKnowledgeCorrectionError(
            "operational_knowledge_correction_adapter_unavailable"
        )
