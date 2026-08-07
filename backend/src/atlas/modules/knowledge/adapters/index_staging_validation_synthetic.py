from __future__ import annotations

import json
from collections.abc import Callable
from dataclasses import asdict, replace
from datetime import UTC, datetime
from hashlib import sha256

from atlas.modules.knowledge.application.index_staging_validation_ports import (
    OperationalKnowledgeIndexError,
)
from atlas.modules.knowledge.domain.index_staging_validation import (
    OperationalKnowledgeIndexInstruction,
    OperationalKnowledgeIndexReceipt,
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


class SyntheticOperationalKnowledgeIndexer:
    def __init__(self, *, clock: Callable[[], datetime] | None = None) -> None:
        self._clock = clock or (lambda: datetime.now(UTC))
        self.calls: list[OperationalKnowledgeIndexInstruction] = []

    async def stage_and_validate(
        self, instruction: OperationalKnowledgeIndexInstruction
    ) -> OperationalKnowledgeIndexReceipt:
        self.calls.append(instruction)
        projection_manifest = _digest(
            [
                instruction.embedding_set_digest,
                instruction.vector_manifest_digest,
                instruction.index_profile_digest,
                instruction.embedding_count,
            ]
        )
        receipt = OperationalKnowledgeIndexReceipt(
            index_staging_id=instruction.index_staging_id,
            schema_version="atlas.operational-knowledge-index-receipt.v1",
            version=1,
            indexer_id="operational-knowledge-indexer.synthetic",
            indexed_by="subject.operational-knowledge-indexer",
            instruction_digest=_digest(asdict(instruction)),
            embedding_set_digest=instruction.embedding_set_digest,
            model_profile_digest=instruction.model_profile_digest,
            vector_dimension=instruction.vector_dimension,
            normalization_profile_id=instruction.normalization_profile_id,
            distance_metric_id=instruction.distance_metric_id,
            index_profile_digest=instruction.index_profile_digest,
            staging_boundary_digest=instruction.staging_boundary_digest,
            expected_point_count=instruction.embedding_count,
            staged_point_count=instruction.embedding_count,
            projection_manifest_digest=projection_manifest,
            point_coverage_digest=_digest(
                [instruction.chunk_vector_binding_digest, instruction.embedding_count, "complete"]
            ),
            authorization_metadata_validation_digest=_digest(
                [
                    instruction.authorization_payload_profile_digest,
                    instruction.classification,
                    instruction.access_policy_id,
                    instruction.retention_policy_id,
                    "valid",
                ]
            ),
            model_compatibility_validation_digest=_digest(
                [
                    instruction.model_profile_digest,
                    instruction.vector_dimension,
                    instruction.normalization_profile_id,
                    instruction.distance_metric_id,
                    "compatible",
                ]
            ),
            isolation_validation_digest=_digest(
                [instruction.staging_boundary_digest, instruction.organization_id, "inactive"]
            ),
            reconciliation_digest=_digest(
                [projection_manifest, instruction.embedding_count, "sealed"]
            ),
            projection_sealed=True,
            validated_at=self._clock(),
            signature_verified=True,
            canonical_digest="0" * 64,
        )
        payload = asdict(receipt)
        payload.pop("canonical_digest")
        return replace(receipt, canonical_digest=_digest(payload))


class UnavailableOperationalKnowledgeIndexer:
    async def stage_and_validate(
        self, instruction: OperationalKnowledgeIndexInstruction
    ) -> OperationalKnowledgeIndexReceipt:
        del instruction
        raise OperationalKnowledgeIndexError("operational_knowledge_indexer_unavailable")
