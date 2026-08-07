from __future__ import annotations

import json
from collections.abc import Callable
from dataclasses import asdict, replace
from datetime import UTC, datetime
from hashlib import sha256

from atlas.modules.knowledge.application.review_finding_ports import (
    OperationalKnowledgeReviewFindingError,
)
from atlas.modules.knowledge.domain.review_finding import (
    OperationalKnowledgeReviewFindingInstruction,
    OperationalKnowledgeReviewFindingItem,
    OperationalKnowledgeReviewFindingReceipt,
)


def _digest(value: object) -> str:
    return sha256(
        json.dumps(
            value,
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=True,
            default=_json_default,
        ).encode("ascii")
    ).hexdigest()


def _json_default(value: object) -> str:
    if isinstance(value, datetime):
        return value.isoformat()
    raise TypeError(f"Unsupported review finding receipt value: {type(value).__name__}")


class SyntheticOperationalKnowledgeReviewFindingRecorder:
    def __init__(self, *, clock: Callable[[], datetime] | None = None) -> None:
        self._clock = clock or (lambda: datetime.now(UTC))
        self.calls: list[OperationalKnowledgeReviewFindingInstruction] = []
        self._artifacts: dict[str, tuple[OperationalKnowledgeReviewFindingItem, ...]] = {}

    async def record(
        self, instruction: OperationalKnowledgeReviewFindingInstruction
    ) -> OperationalKnowledgeReviewFindingReceipt:
        self.calls.append(instruction)
        normalized_findings = [
            {
                "category_code": item.category_code,
                "severity_code": item.severity_code,
                "summary": item.summary.strip(),
                "detail": item.detail.strip(),
            }
            for item in instruction.findings
        ]
        content = json.dumps(
            normalized_findings, sort_keys=True, separators=(",", ":"), ensure_ascii=True
        ).encode("ascii")
        if len(content) > instruction.maximum_packet_bytes:
            raise OperationalKnowledgeReviewFindingError(
                "operational_knowledge_review_finding_packet_too_large"
            )
        categories = sorted({item.category_code for item in instruction.findings})
        severities = sorted({item.severity_code for item in instruction.findings})
        seed = instruction.finding_packet_id.rsplit(".", 1)[-1]
        receipt = OperationalKnowledgeReviewFindingReceipt(
            finding_packet_id=instruction.finding_packet_id,
            schema_version="atlas.operational-knowledge-review-finding-receipt.v1",
            version=1,
            recorder_id="operational-knowledge-review-finding-recorder.synthetic",
            attested_by="subject.operational-knowledge-review-finding-recorder-attestor",
            source_presentation_id=instruction.source_presentation_id,
            source_presentation_digest=instruction.source_presentation_digest,
            track_code=instruction.track_code,
            finding_artifact_id=f"knowledge-review-finding-artifact.{seed}",
            finding_count=len(instruction.findings),
            finding_bytes=len(content),
            finding_content_digest=sha256(content).hexdigest(),
            finding_metadata_digest=_digest(
                [instruction.track_code, categories, severities, len(instruction.findings)]
            ),
            lineage_digest=_digest(
                [
                    instruction.source_lease_digest,
                    instruction.source_presentation_digest,
                    instruction.source_draft_digest,
                    instruction.presented_content_digest,
                ]
            ),
            category_catalog_digest=_digest(categories),
            severity_catalog_digest=_digest(severities),
            access_digest=_digest(
                [instruction.classification, instruction.access_policy_id, "inherited"]
            ),
            retention_digest=_digest([instruction.retention_policy_id, "inherited"]),
            encryption_digest=_digest([instruction.encryption_profile_id, "encrypted"]),
            cleanup_digest=_digest(
                [instruction.finding_packet_id, "buffers-erased", "channel-closed"]
            ),
            created_at=self._clock(),
            expires_at=instruction.expires_at,
            immutable_finding_confirmed=True,
            encrypted_at_rest=True,
            transient_buffers_erased=True,
            artifact_channel_closed=True,
            signature_verified=True,
            canonical_digest="0" * 64,
        )
        existing = self._artifacts.get(receipt.finding_artifact_id)
        if existing is not None and existing != instruction.findings:
            raise OperationalKnowledgeReviewFindingError(
                "operational_knowledge_review_finding_artifact_conflict"
            )
        self._artifacts[receipt.finding_artifact_id] = instruction.findings
        payload = asdict(receipt)
        payload.pop("canonical_digest")
        return replace(receipt, canonical_digest=_digest(payload))

    def read_artifact(
        self, *, finding_artifact_id: str
    ) -> tuple[OperationalKnowledgeReviewFindingItem, ...] | None:
        return self._artifacts.get(finding_artifact_id)


class UnavailableOperationalKnowledgeReviewFindingRecorder:
    async def record(
        self, instruction: OperationalKnowledgeReviewFindingInstruction
    ) -> OperationalKnowledgeReviewFindingReceipt:
        del instruction
        raise OperationalKnowledgeReviewFindingError(
            "operational_knowledge_review_finding_recorder_unavailable"
        )
