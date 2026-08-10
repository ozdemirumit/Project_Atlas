from __future__ import annotations

import json
from collections.abc import Callable
from dataclasses import asdict, replace
from datetime import UTC, datetime
from hashlib import sha256

from atlas.modules.recommendations.adapters.human_review_finding_synthetic import (
    SyntheticRecommendationHumanReviewFindingRecorder,
)
from atlas.modules.recommendations.application.finding_presentation_ports import (
    RecommendationFindingPresentationError,
)
from atlas.modules.recommendations.domain.finding_presentation import (
    RecommendationFindingPresentationInstruction,
    RecommendationFindingPresentationReceipt,
)


def _digest(value: object) -> str:
    return sha256(
        json.dumps(
            value,
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=True,
            default=_json_default,
        ).encode("ascii")
    ).hexdigest()


def _json_default(value: object) -> str:
    if isinstance(value, datetime):
        return value.isoformat()
    raise TypeError(f"Unsupported finding presentation value: {type(value).__name__}")


class SyntheticRecommendationFindingPresenter:
    def __init__(
        self,
        *,
        recorder: SyntheticRecommendationHumanReviewFindingRecorder,
        clock: Callable[[], datetime] | None = None,
    ) -> None:
        self._recorder = recorder
        self._clock = clock or (lambda: datetime.now(UTC))
        self.calls: list[RecommendationFindingPresentationInstruction] = []

    async def present(
        self, instruction: RecommendationFindingPresentationInstruction
    ) -> RecommendationFindingPresentationReceipt:
        self.calls.append(instruction)
        findings = self._recorder.read_artifact(
            finding_artifact_id=instruction.source_finding_artifact_id
        )
        if findings is None:
            raise RecommendationFindingPresentationError(
                "recommendation_finding_presentation_artifact_not_found"
            )
        normalized = [
            {
                "category_code": item.category_code,
                "severity_code": item.severity_code,
                "summary": item.summary.strip(),
                "detail": item.detail.strip(),
            }
            for item in findings
        ]
        content = json.dumps(
            normalized, sort_keys=True, separators=(",", ":"), ensure_ascii=True
        ).encode("ascii")
        categories = sorted({item.category_code for item in findings})
        severities = sorted({item.severity_code for item in findings})
        if (
            len(findings) != instruction.expected_finding_count
            or len(findings) > instruction.maximum_findings
            or len(content) != instruction.expected_finding_bytes
            or len(content) > instruction.maximum_packet_bytes
            or sha256(content).hexdigest() != instruction.expected_content_digest
            or _digest([instruction.track_code, categories, severities, len(findings)])
            != instruction.expected_metadata_digest
            or _digest(categories) != instruction.expected_category_catalog_digest
            or _digest(severities) != instruction.expected_severity_catalog_digest
        ):
            raise RecommendationFindingPresentationError(
                "recommendation_finding_presentation_artifact_drift"
            )
        receipt = RecommendationFindingPresentationReceipt(
            finding_presentation_id=instruction.finding_presentation_id,
            schema_version="atlas.recommendation-finding-presentation-receipt.v1",
            version=1,
            presenter_id="recommendation-finding-presenter.synthetic",
            attested_by="subject.recommendation-finding-presenter-attestor",
            source_finding_packet_id=instruction.source_finding_packet_id,
            source_finding_digest=instruction.source_finding_digest,
            track_code=instruction.track_code,
            media_type="media-type.application-json",
            findings=findings,
            finding_count=len(findings),
            finding_bytes=len(content),
            finding_content_digest=sha256(content).hexdigest(),
            finding_metadata_digest=instruction.expected_metadata_digest,
            lineage_digest=instruction.expected_lineage_digest,
            category_catalog_digest=instruction.expected_category_catalog_digest,
            severity_catalog_digest=instruction.expected_severity_catalog_digest,
            access_digest=instruction.expected_access_digest,
            retention_digest=instruction.expected_retention_digest,
            encryption_digest=instruction.expected_encryption_digest,
            source_cleanup_digest=instruction.expected_source_cleanup_digest,
            presentation_cleanup_digest=_digest(
                [instruction.finding_presentation_id, "buffers-erased", "channel-closed"]
            ),
            presented_at=self._clock(),
            expires_at=instruction.expires_at,
            source_integrity_verified=True,
            encrypted_source_verified=True,
            transient_buffers_erased=True,
            artifact_channel_closed=True,
            signature_verified=True,
            canonical_digest="0" * 64,
        )
        payload = asdict(receipt)
        payload.pop("canonical_digest")
        return replace(receipt, canonical_digest=_digest(payload))


class UnavailableRecommendationFindingPresenter:
    async def present(
        self, instruction: RecommendationFindingPresentationInstruction
    ) -> RecommendationFindingPresentationReceipt:
        del instruction
        raise RecommendationFindingPresentationError(
            "recommendation_finding_presentation_presenter_unavailable"
        )
