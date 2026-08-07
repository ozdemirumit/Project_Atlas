from __future__ import annotations

import json
from collections.abc import Callable
from dataclasses import asdict, replace
from datetime import UTC, datetime
from hashlib import sha256

from atlas.modules.knowledge.application.deterministic_chunking_ports import (
    OperationalKnowledgeChunkingError,
)
from atlas.modules.knowledge.domain.deterministic_chunking import (
    OperationalKnowledgeChunkingInstruction,
    OperationalKnowledgeChunkingReceipt,
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


class SyntheticOperationalKnowledgeChunker:
    def __init__(self, *, clock: Callable[[], datetime] | None = None) -> None:
        self._clock = clock or (lambda: datetime.now(UTC))
        self.calls: list[OperationalKnowledgeChunkingInstruction] = []

    async def chunk(
        self, instruction: OperationalKnowledgeChunkingInstruction
    ) -> OperationalKnowledgeChunkingReceipt:
        self.calls.append(instruction)
        chunk_count = min(3, instruction.maximum_chunks)
        total_characters = instruction.canonical_characters
        minimum_characters = max(1, total_characters // chunk_count)
        maximum_characters = min(
            instruction.maximum_chunk_characters,
            minimum_characters + (total_characters % chunk_count),
        )
        total_tokens = min(
            chunk_count * instruction.maximum_chunk_tokens,
            max(chunk_count, total_characters // 4),
        )
        overlap = min(instruction.maximum_overlap_characters, 32)
        ordered_manifest = _digest(
            [
                instruction.protected_material_digest,
                instruction.chunking_profile_digest,
                instruction.algorithm_profile_digest,
                chunk_count,
                total_characters,
                overlap,
            ]
        )
        receipt = OperationalKnowledgeChunkingReceipt(
            chunk_set_id=instruction.chunk_set_id,
            schema_version="atlas.operational-knowledge-chunking-receipt.v1",
            version=1,
            chunker_id="operational-knowledge-chunker.synthetic",
            chunked_by="subject.operational-knowledge-chunker",
            instruction_digest=_digest(asdict(instruction)),
            materialization_digest=instruction.materialization_digest,
            protected_material_digest=instruction.protected_material_digest,
            chunking_profile_digest=instruction.chunking_profile_digest,
            algorithm_profile_digest=instruction.algorithm_profile_digest,
            ordered_chunk_manifest_digest=ordered_manifest,
            structure_manifest_digest=_digest([ordered_manifest, "structure-v1"]),
            governance_binding_digest=instruction.governance_binding_digest,
            determinism_evidence_digest=_digest([ordered_manifest, ordered_manifest]),
            chunk_count=chunk_count,
            total_chunk_characters=total_characters,
            total_chunk_tokens=total_tokens,
            minimum_chunk_characters=minimum_characters,
            maximum_chunk_characters=maximum_characters,
            overlap_characters=overlap,
            chunked_at=self._clock(),
            signature_verified=True,
            canonical_digest="0" * 64,
        )
        payload = asdict(receipt)
        payload.pop("canonical_digest")
        return replace(receipt, canonical_digest=_digest(payload))


class UnavailableOperationalKnowledgeChunker:
    async def chunk(
        self, instruction: OperationalKnowledgeChunkingInstruction
    ) -> OperationalKnowledgeChunkingReceipt:
        del instruction
        raise OperationalKnowledgeChunkingError("operational_knowledge_chunker_unavailable")
