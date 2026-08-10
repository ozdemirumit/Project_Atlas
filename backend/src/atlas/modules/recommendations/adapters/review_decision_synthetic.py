from __future__ import annotations

import json
from collections.abc import Callable
from dataclasses import asdict, replace
from datetime import UTC, datetime
from hashlib import sha256

from atlas.modules.recommendations.application.review_decision_ports import (
    RecommendationTrackReviewDecisionError,
)
from atlas.modules.recommendations.domain.review_decision import (
    RecommendationTrackReviewDecisionInstruction,
    RecommendationTrackReviewDecisionReceipt,
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


class SyntheticRecommendationTrackReviewDecisionAttestor:
    def __init__(self, *, clock: Callable[[], datetime] | None = None) -> None:
        self._clock = clock or (lambda: datetime.now(UTC))
        self.calls: list[RecommendationTrackReviewDecisionInstruction] = []

    async def attest(
        self, instruction: RecommendationTrackReviewDecisionInstruction
    ) -> RecommendationTrackReviewDecisionReceipt:
        self.calls.append(instruction)
        receipt = RecommendationTrackReviewDecisionReceipt(
            decision_id=instruction.decision_id,
            schema_version="atlas.recommendation-track-review-decision-receipt.v1",
            version=1,
            attestor_id="recommendation-track-review-decision-attestor.synthetic",
            attested_by="subject.recommendation-track-review-decision-attestor",
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


class UnavailableRecommendationTrackReviewDecisionAttestor:
    async def attest(
        self, instruction: RecommendationTrackReviewDecisionInstruction
    ) -> RecommendationTrackReviewDecisionReceipt:
        del instruction
        raise RecommendationTrackReviewDecisionError(
            "recommendation_track_review_decision_attestor_unavailable"
        )
