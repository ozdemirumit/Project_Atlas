from __future__ import annotations

import json
from collections.abc import Callable
from dataclasses import asdict, replace
from datetime import UTC, datetime
from hashlib import sha256

from atlas.modules.knowledge.application.publication_preparation_ports import (
    OperationalKnowledgePublicationPreparationError,
)
from atlas.modules.knowledge.domain.publication_preparation import (
    OperationalKnowledgePublicationPreparationInstruction,
    OperationalKnowledgePublicationPreparationReceipt,
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


class SyntheticOperationalKnowledgePublicationPreparer:
    def __init__(self, *, clock: Callable[[], datetime] | None = None) -> None:
        self._clock = clock or (lambda: datetime.now(UTC))
        self.calls: list[OperationalKnowledgePublicationPreparationInstruction] = []

    async def prepare(
        self, instruction: OperationalKnowledgePublicationPreparationInstruction
    ) -> OperationalKnowledgePublicationPreparationReceipt:
        self.calls.append(instruction)
        receipt = OperationalKnowledgePublicationPreparationReceipt(
            preparation_id=instruction.preparation_id,
            schema_version="atlas.operational-knowledge-publication-preparation-receipt.v1",
            version=1,
            preparer_id="operational-knowledge-publication-preparer.synthetic",
            prepared_by="subject.operational-knowledge-publication-preparer",
            instruction_digest=_digest(asdict(instruction)),
            source_artifact_digest=instruction.source_draft_digest,
            metadata_manifest_digest=_digest(
                [instruction.knowledge_item_id, instruction.preparation_profile_digest]
            ),
            access_manifest_digest=_digest(
                [instruction.organization_id, instruction.policy_digest, "access"]
            ),
            retention_manifest_digest=_digest(
                [instruction.knowledge_item_id, instruction.policy_digest, "retention"]
            ),
            prepared_at=self._clock(),
            signature_verified=True,
            canonical_digest="0" * 64,
        )
        payload = asdict(receipt)
        payload.pop("canonical_digest")
        return replace(receipt, canonical_digest=_digest(payload))


class UnavailableOperationalKnowledgePublicationPreparer:
    async def prepare(
        self, instruction: OperationalKnowledgePublicationPreparationInstruction
    ) -> OperationalKnowledgePublicationPreparationReceipt:
        del instruction
        raise OperationalKnowledgePublicationPreparationError(
            "operational_knowledge_publication_preparer_unavailable"
        )
