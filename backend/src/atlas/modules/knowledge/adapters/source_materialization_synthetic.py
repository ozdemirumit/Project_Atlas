from __future__ import annotations

import json
from collections.abc import Callable
from dataclasses import asdict, replace
from datetime import UTC, datetime
from hashlib import sha256

from atlas.modules.knowledge.application.source_materialization_ports import (
    OperationalKnowledgeSourceMaterializationError,
)
from atlas.modules.knowledge.domain.source_materialization import (
    OperationalKnowledgeSourceMaterializationInstruction,
    OperationalKnowledgeSourceMaterializationReceipt,
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


class SyntheticOperationalKnowledgeSourceMaterializer:
    def __init__(self, *, clock: Callable[[], datetime] | None = None) -> None:
        self._clock = clock or (lambda: datetime.now(UTC))
        self.calls: list[OperationalKnowledgeSourceMaterializationInstruction] = []

    async def materialize(
        self, instruction: OperationalKnowledgeSourceMaterializationInstruction
    ) -> OperationalKnowledgeSourceMaterializationReceipt:
        self.calls.append(instruction)
        source_bytes = 256
        canonical_bytes = 240
        canonical_characters = 240
        receipt = OperationalKnowledgeSourceMaterializationReceipt(
            materialization_id=instruction.materialization_id,
            schema_version="atlas.operational-knowledge-source-materialization-receipt.v1",
            version=1,
            materializer_id="operational-knowledge-source-materializer.synthetic",
            materialized_by="subject.operational-knowledge-source-materializer",
            instruction_digest=_digest(asdict(instruction)),
            source_artifact_digest=instruction.source_artifact_digest,
            protected_material_digest=_digest(
                [instruction.source_artifact_digest, instruction.canonicalization_profile_digest]
            ),
            canonicalization_profile_digest=instruction.canonicalization_profile_digest,
            media_type="text/markdown",
            source_bytes=source_bytes,
            canonical_bytes=canonical_bytes,
            canonical_characters=canonical_characters,
            security_scan_evidence_digest=_digest(
                [instruction.source_security_profile_digest, "synthetic-clean"]
            ),
            governance_binding_digest=_digest(
                [
                    instruction.metadata_manifest_digest,
                    instruction.access_manifest_digest,
                    instruction.retention_manifest_digest,
                ]
            ),
            materialized_at=self._clock(),
            signature_verified=True,
            canonical_digest="0" * 64,
        )
        payload = asdict(receipt)
        payload.pop("canonical_digest")
        return replace(receipt, canonical_digest=_digest(payload))


class UnavailableOperationalKnowledgeSourceMaterializer:
    async def materialize(
        self, instruction: OperationalKnowledgeSourceMaterializationInstruction
    ) -> OperationalKnowledgeSourceMaterializationReceipt:
        del instruction
        raise OperationalKnowledgeSourceMaterializationError(
            "operational_knowledge_source_materializer_unavailable"
        )
