from __future__ import annotations

from dataclasses import asdict, replace

from atlas.modules.recommendations.application.final_disposition import (
    FinalRecommendationDispositionService,
)
from atlas.modules.recommendations.application.final_disposition_ports import (
    FinalRecommendationDispositionError,
)
from atlas.modules.recommendations.domain.final_disposition import (
    FinalRecommendationDispositionInstruction,
    FinalRecommendationDispositionReceipt,
)


class SyntheticFinalRecommendationDispositionAttestor:
    async def attest(
        self, instruction: FinalRecommendationDispositionInstruction
    ) -> FinalRecommendationDispositionReceipt:
        digest = FinalRecommendationDispositionService._digest
        receipt = FinalRecommendationDispositionReceipt(
            disposition_id=instruction.disposition_id,
            schema_version="atlas.final-recommendation-disposition-receipt.v1",
            version=1,
            attestor_id="final-recommendation-disposition-attestor.synthetic",
            attested_by="subject.final-recommendation-disposition-attestor",
            disposition_code=instruction.disposition_code,
            instruction_digest=digest(asdict(instruction)),
            attested_at=instruction.requested_at,
            source_verified=True,
            no_model_used=True,
            no_network_used=True,
            no_operational_authority=True,
            signature_verified=True,
            canonical_digest="0" * 64,
        )
        return replace(
            receipt,
            canonical_digest=FinalRecommendationDispositionService._receipt_digest(receipt),
        )


class UnavailableFinalRecommendationDispositionAttestor:
    async def attest(
        self, instruction: FinalRecommendationDispositionInstruction
    ) -> FinalRecommendationDispositionReceipt:
        del instruction
        raise FinalRecommendationDispositionError(
            "final_recommendation_disposition_attestor_unavailable"
        )
