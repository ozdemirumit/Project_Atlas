from __future__ import annotations

import json
from collections.abc import Callable
from dataclasses import asdict, replace
from datetime import UTC, datetime
from hashlib import sha256

from atlas.modules.knowledge.application.evidence_draft_ports import (
    OperationalEvidenceKnowledgeDraftAdapter,
    OperationalEvidenceKnowledgeDraftError,
)
from atlas.modules.knowledge.domain.evidence_draft import (
    OperationalEvidenceKnowledgeDraftInstruction,
    OperationalEvidenceKnowledgeDraftReceipt,
)


def _normalize(value: object) -> object:
    if isinstance(value, datetime):
        return value.isoformat()
    if isinstance(value, dict):
        return {str(key): _normalize(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_normalize(item) for item in value]
    return value


def _digest(value: object) -> str:
    return sha256(
        json.dumps(
            _normalize(value), sort_keys=True, separators=(",", ":"), ensure_ascii=True
        ).encode("ascii")
    ).hexdigest()


class SyntheticOperationalEvidenceKnowledgeDraftAdapter(OperationalEvidenceKnowledgeDraftAdapter):
    def __init__(self, *, clock: Callable[[], datetime] | None = None) -> None:
        self._clock = clock or (lambda: datetime.now(UTC))
        self.calls: list[OperationalEvidenceKnowledgeDraftInstruction] = []

    async def create_draft(
        self, instruction: OperationalEvidenceKnowledgeDraftInstruction
    ) -> OperationalEvidenceKnowledgeDraftReceipt:
        self.calls.append(instruction)
        seed = instruction.draft_id.rsplit(".", 1)[-1]
        title = f"{instruction.display_name} {instruction.capability_id} operational evidence"
        receipt = OperationalEvidenceKnowledgeDraftReceipt(
            draft_id=instruction.draft_id,
            schema_version="atlas.operational-evidence-knowledge-draft-receipt.v1",
            version=1,
            adapter_id="operational-evidence-knowledge-draft-adapter.synthetic",
            attested_by="subject.operational-evidence-knowledge-draft-adapter-attestor",
            source_ingestion_digest=instruction.source_ingestion_digest,
            evidence_package_id=instruction.evidence_package_id,
            evidence_content_digest=instruction.evidence_content_digest,
            knowledge_item_id=f"knowledge-item.operational-evidence.{seed}",
            draft_version_id=f"knowledge-draft-version.{seed}",
            draft_artifact_id=f"knowledge-draft-artifact.{seed}",
            draft_schema_version="atlas.operational-knowledge-draft.v1",
            title=title[:200],
            draft_domain=instruction.draft_domain,
            content_type=instruction.content_type,
            source_authority=instruction.source_authority,
            language=instruction.language,
            knowledge_lifecycle="draft",
            classification=instruction.classification,
            access_policy_id=instruction.access_policy_id,
            access_policy_digest=instruction.access_policy_digest,
            retention_policy_id=instruction.retention_policy_id,
            retention_policy_digest=instruction.retention_policy_digest,
            encryption_profile_id=instruction.encryption_profile_id,
            encryption_profile_digest=instruction.encryption_profile_digest,
            draft_content_digest=_digest(
                [instruction.evidence_content_digest, instruction.content_type, "draft-content"]
            ),
            draft_metadata_digest=_digest(
                [title, instruction.draft_domain, instruction.language, "draft-metadata"]
            ),
            provenance_digest=_digest(
                [instruction.source_ingestion_digest, instruction.evidence_package_id]
            ),
            draft_access_digest=_digest(
                [instruction.access_policy_digest, instruction.classification, "inherited"]
            ),
            draft_retention_digest=_digest([instruction.retention_policy_digest, "inherited"]),
            draft_item_count=instruction.evidence_item_count,
            draft_bytes=instruction.evidence_bytes,
            observed_from=instruction.observed_from,
            observed_to=instruction.observed_to,
            created_at=max(self._clock(), instruction.source_ingested_at),
            immutable_draft_confirmed=True,
            encrypted_at_rest=True,
            transient_buffers_erased=True,
            artifact_channel_closed=True,
            signature_verified=True,
            canonical_digest="0" * 64,
        )
        payload = asdict(receipt)
        payload.pop("canonical_digest")
        return replace(receipt, canonical_digest=_digest(payload))


class UnavailableOperationalEvidenceKnowledgeDraftAdapter(OperationalEvidenceKnowledgeDraftAdapter):
    async def create_draft(
        self, instruction: OperationalEvidenceKnowledgeDraftInstruction
    ) -> OperationalEvidenceKnowledgeDraftReceipt:
        del instruction
        raise OperationalEvidenceKnowledgeDraftError(
            "operational_evidence_knowledge_draft_adapter_unavailable"
        )
