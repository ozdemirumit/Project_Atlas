from __future__ import annotations

import json
from collections.abc import Callable
from dataclasses import asdict, replace
from datetime import UTC, datetime
from enum import Enum
from hashlib import sha256

from atlas.modules.knowledge.application.draft_review_request_ports import (
    OperationalKnowledgeReviewRequestAdapter,
    OperationalKnowledgeReviewRequestError,
)
from atlas.modules.knowledge.domain.draft_review_request import (
    AWAITING_REVIEWER,
    OperationalKnowledgeReviewRequestInstruction,
    OperationalKnowledgeReviewRequestReceipt,
)


def _normalize(value: object) -> object:
    if isinstance(value, Enum):
        return value.value
    if isinstance(value, datetime):
        return value.isoformat()
    if isinstance(value, dict):
        return {str(key): _normalize(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_normalize(item) for item in value]
    return value


def _digest(payload: object) -> str:
    return sha256(
        json.dumps(_normalize(payload), sort_keys=True, separators=(",", ":")).encode("ascii")
    ).hexdigest()


class SyntheticOperationalKnowledgeReviewRequestAdapter:
    adapter_id = "operational-knowledge-review-request-adapter.synthetic"
    attestor_id = "subject.operational-knowledge-review-request-adapter-attestor"
    receipt_schema = "atlas.operational-knowledge-review-request-receipt.v1"

    def __init__(self, *, clock: Callable[[], datetime] | None = None) -> None:
        self._clock = clock or (lambda: datetime.now(UTC))
        self.call_count = 0

    async def create_review_request(
        self, instruction: OperationalKnowledgeReviewRequestInstruction
    ) -> OperationalKnowledgeReviewRequestReceipt:
        self.call_count += 1
        seed = _digest(
            [
                instruction.review_request_id,
                instruction.draft_digest,
                instruction.orchestration_policy_digest,
            ]
        )
        manifest_bytes = min(
            instruction.maximum_manifest_bytes,
            max(1024, instruction.draft_item_count * 256),
        )
        receipt = OperationalKnowledgeReviewRequestReceipt(
            review_request_id=instruction.review_request_id,
            schema_version=self.receipt_schema,
            version=1,
            adapter_id=self.adapter_id,
            attested_by=self.attestor_id,
            draft_id=instruction.draft_id,
            draft_digest=instruction.draft_digest,
            draft_content_digest=instruction.draft_content_digest,
            manifest_id=f"operational-knowledge-review-manifest.{seed[:24]}",
            manifest_artifact_id=f"artifact.operational-knowledge-review-manifest.{seed[:24]}",
            manifest_schema_version="atlas.operational-knowledge-review-manifest.v1",
            manifest_digest=_digest([seed, "manifest", instruction.draft_metadata_digest]),
            routing_digest=_digest(
                [
                    instruction.domain_track_code,
                    instruction.domain_queue_id,
                    instruction.security_track_code,
                    instruction.security_queue_id,
                    instruction.assignment_strategy,
                ]
            ),
            governance_digest=_digest(
                [
                    instruction.classification,
                    instruction.access_policy_digest,
                    instruction.retention_policy_digest,
                    instruction.encryption_profile_digest,
                ]
            ),
            artifact_digest=_digest([seed, "encrypted-immutable-artifact"]),
            domain_track_code=instruction.domain_track_code,
            security_track_code=instruction.security_track_code,
            domain_queue_id=instruction.domain_queue_id,
            security_queue_id=instruction.security_queue_id,
            assignment_strategy=instruction.assignment_strategy,
            sla_class=instruction.sla_class,
            domain_status=AWAITING_REVIEWER,
            security_status=AWAITING_REVIEWER,
            manifest_bytes=manifest_bytes,
            created_at=max(self._clock(), instruction.draft_created_at),
            immutable_manifest_confirmed=True,
            encrypted_at_rest=True,
            transient_buffers_erased=True,
            artifact_channel_closed=True,
            signature_verified=True,
            canonical_digest="0" * 64,
        )
        payload = asdict(receipt)
        payload.pop("canonical_digest")
        return replace(receipt, canonical_digest=_digest(payload))


class UnavailableOperationalKnowledgeReviewRequestAdapter(OperationalKnowledgeReviewRequestAdapter):
    async def create_review_request(
        self, instruction: OperationalKnowledgeReviewRequestInstruction
    ) -> OperationalKnowledgeReviewRequestReceipt:
        del instruction
        raise OperationalKnowledgeReviewRequestError(
            "operational_knowledge_review_request_adapter_unavailable"
        )
