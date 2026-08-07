from __future__ import annotations

import json
from collections.abc import Callable
from dataclasses import asdict, replace
from datetime import UTC, datetime
from hashlib import sha256

from atlas.modules.knowledge.application.embedding_generation_ports import (
    OperationalKnowledgeEmbeddingError,
)
from atlas.modules.knowledge.domain.embedding_generation import (
    OperationalKnowledgeEmbeddingInstruction,
    OperationalKnowledgeEmbeddingReceipt,
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


class SyntheticOperationalKnowledgeEmbedder:
    def __init__(self, *, clock: Callable[[], datetime] | None = None) -> None:
        self._clock = clock or (lambda: datetime.now(UTC))
        self.calls: list[OperationalKnowledgeEmbeddingInstruction] = []

    async def embed(
        self, instruction: OperationalKnowledgeEmbeddingInstruction
    ) -> OperationalKnowledgeEmbeddingReceipt:
        self.calls.append(instruction)
        vector_manifest = _digest(
            [
                instruction.ordered_chunk_manifest_digest,
                instruction.model_profile_digest,
                instruction.model_artifact_digest,
                instruction.vector_dimension,
                instruction.chunk_count,
            ]
        )
        receipt = OperationalKnowledgeEmbeddingReceipt(
            embedding_set_id=instruction.embedding_set_id,
            schema_version="atlas.operational-knowledge-embedding-receipt.v1",
            version=1,
            embedder_id="operational-knowledge-embedder.synthetic",
            embedded_by="subject.operational-knowledge-embedder",
            instruction_digest=_digest(asdict(instruction)),
            chunk_set_digest=instruction.chunk_set_digest,
            ordered_chunk_manifest_digest=instruction.ordered_chunk_manifest_digest,
            model_profile_digest=instruction.model_profile_digest,
            model_artifact_digest=instruction.model_artifact_digest,
            tokenizer_profile_digest=instruction.tokenizer_profile_digest,
            vector_dimension=instruction.vector_dimension,
            normalization_profile_id=instruction.normalization_profile_id,
            distance_metric_id=instruction.distance_metric_id,
            data_boundary_digest=instruction.data_boundary_digest,
            embedding_count=instruction.chunk_count,
            vector_manifest_digest=vector_manifest,
            chunk_vector_binding_digest=_digest(
                [instruction.ordered_chunk_manifest_digest, vector_manifest]
            ),
            numeric_validation_digest=_digest([vector_manifest, "finite-normalized"]),
            coverage_validation_digest=_digest(
                [instruction.chunk_count, instruction.chunk_count, "complete"]
            ),
            resource_evidence_digest=_digest(
                [instruction.maximum_batch_size, instruction.total_chunk_tokens]
            ),
            embedded_at=self._clock(),
            signature_verified=True,
            canonical_digest="0" * 64,
        )
        payload = asdict(receipt)
        payload.pop("canonical_digest")
        return replace(receipt, canonical_digest=_digest(payload))


class UnavailableOperationalKnowledgeEmbedder:
    async def embed(
        self, instruction: OperationalKnowledgeEmbeddingInstruction
    ) -> OperationalKnowledgeEmbeddingReceipt:
        del instruction
        raise OperationalKnowledgeEmbeddingError("operational_knowledge_embedder_unavailable")
