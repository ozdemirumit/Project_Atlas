from __future__ import annotations

import json
from collections.abc import Callable
from dataclasses import asdict, replace
from datetime import UTC, datetime
from hashlib import sha256

from atlas.modules.knowledge.application.review_decision_ports import (
    OperationalKnowledgeTrackReviewDecisionError,
)
from atlas.modules.knowledge.domain.review_decision import (
    OperationalKnowledgeTrackReviewDecisionInstruction,
    OperationalKnowledgeTrackReviewDecisionReceipt,
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


class SyntheticOperationalKnowledgeTrackReviewDecisionAttestor:
    def __init__(self, *, clock: Callable[[], datetime] | None = None) -> None:
        self._clock = clock or (lambda: datetime.now(UTC))
        self.calls: list[OperationalKnowledgeTrackReviewDecisionInstruction] = []

    async def attest(
        self, instruction: OperationalKnowledgeTrackReviewDecisionInstruction
    ) -> OperationalKnowledgeTrackReviewDecisionReceipt:
        self.calls.append(instruction)
        receipt = OperationalKnowledgeTrackReviewDecisionReceipt(
            decision_id=instruction.decision_id,
            schema_version="atlas.operational-knowledge-track-review-decision-receipt.v1",
            version=1,
            attestor_id="operational-knowledge-track-review-decision-attestor.synthetic",
            attested_by="subject.operational-knowledge-track-review-decision-attestor",
            source_finding_presentation_id=instruction.source_finding_presentation_id,
            source_finding_presentation_digest=(instruction.source_finding_presentation_digest),
            track_code=instruction.track_code,
            disposition_code=instruction.disposition_code,
            basis_digest=_digest(instruction.basis_codes),
            instruction_digest=_digest(asdict(instruction)),
            attested_at=self._clock(),
            signature_verified=True,
            canonical_digest="0" * 64,
        )
        payload = asdict(receipt)
        payload.pop("canonical_digest")
        return replace(receipt, canonical_digest=_digest(payload))


class UnavailableOperationalKnowledgeTrackReviewDecisionAttestor:
    async def attest(
        self, instruction: OperationalKnowledgeTrackReviewDecisionInstruction
    ) -> OperationalKnowledgeTrackReviewDecisionReceipt:
        del instruction
        raise OperationalKnowledgeTrackReviewDecisionError(
            "operational_knowledge_track_review_decision_attestor_unavailable"
        )
