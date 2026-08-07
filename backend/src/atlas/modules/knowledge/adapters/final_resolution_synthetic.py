from __future__ import annotations

import json
from collections.abc import Callable
from dataclasses import asdict, replace
from datetime import UTC, datetime
from hashlib import sha256

from atlas.modules.knowledge.application.final_resolution_ports import (
    OperationalKnowledgeFinalResolutionError,
)
from atlas.modules.knowledge.domain.final_resolution import (
    OperationalKnowledgeFinalResolutionInstruction,
    OperationalKnowledgeFinalResolutionReceipt,
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


class SyntheticOperationalKnowledgeFinalResolutionAttestor:
    def __init__(self, *, clock: Callable[[], datetime] | None = None) -> None:
        self._clock = clock or (lambda: datetime.now(UTC))
        self.calls: list[OperationalKnowledgeFinalResolutionInstruction] = []

    async def attest(
        self, instruction: OperationalKnowledgeFinalResolutionInstruction
    ) -> OperationalKnowledgeFinalResolutionReceipt:
        self.calls.append(instruction)
        receipt = OperationalKnowledgeFinalResolutionReceipt(
            resolution_id=instruction.resolution_id,
            schema_version="atlas.operational-knowledge-final-resolution-receipt.v1",
            version=1,
            attestor_id="operational-knowledge-final-resolution-attestor.synthetic",
            attested_by="subject.operational-knowledge-final-resolution-attestor",
            disposition_code=instruction.disposition_code,
            instruction_digest=_digest(asdict(instruction)),
            attested_at=self._clock(),
            signature_verified=True,
            canonical_digest="0" * 64,
        )
        payload = asdict(receipt)
        payload.pop("canonical_digest")
        return replace(receipt, canonical_digest=_digest(payload))


class UnavailableOperationalKnowledgeFinalResolutionAttestor:
    async def attest(
        self, instruction: OperationalKnowledgeFinalResolutionInstruction
    ) -> OperationalKnowledgeFinalResolutionReceipt:
        del instruction
        raise OperationalKnowledgeFinalResolutionError(
            "operational_knowledge_final_resolution_attestor_unavailable"
        )
