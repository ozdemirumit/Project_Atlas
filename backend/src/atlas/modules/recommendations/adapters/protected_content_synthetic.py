from __future__ import annotations

import json
from collections.abc import Callable
from dataclasses import asdict, replace
from datetime import UTC, datetime
from hashlib import sha256

from atlas.modules.recommendations.application.protected_content_ports import (
    RecommendationProtectedContentError,
)
from atlas.modules.recommendations.domain.protected_content import (
    RecommendationProtectedContentInstruction,
    RecommendationProtectedContentPresenterGrant,
    RecommendationProtectedContentReceipt,
)


def _digest(value: object) -> str:
    return sha256(
        json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode("ascii")
    ).hexdigest()


def _clean(value: str) -> str:
    return " ".join(value.replace("<", "[").replace(">", "]").split())


class SyntheticRecommendationProtectedContentPresenter:
    def __init__(self, *, clock: Callable[[], datetime] | None = None) -> None:
        self._clock = clock or (lambda: datetime.now(UTC))
        self.calls: list[RecommendationProtectedContentInstruction] = []

    async def present(
        self, instruction: RecommendationProtectedContentInstruction
    ) -> RecommendationProtectedContentPresenterGrant:
        self.calls.append(instruction)
        lines = [
            "Recommendation review snapshot",
            "",
            f"Review track: {_clean(instruction.track_code.removeprefix('review-track.'))}",
            f"Outcome: {_clean(instruction.outcome)}",
            f"Headline: {_clean(instruction.headline)}",
            f"Safety notice: {_clean(instruction.safety_notice)}",
        ]
        for index, option in enumerate(instruction.options, start=1):
            lines.extend(
                (
                    "",
                    f"Option {index}: {_clean(option.title)}",
                    f"Role: {_clean(option.role)}",
                    f"Category: {_clean(option.category)}",
                    f"Intended outcome: {_clean(option.intended_outcome)}",
                    f"Rationale: {_clean(option.rationale)}",
                    f"Confidence: {_clean(option.confidence)}",
                    f"Risk: {_clean(option.overall_risk)}",
                    (
                        "Estimated work: "
                        f"{option.work_minimum_minutes}-{option.work_maximum_minutes} minutes"
                    ),
                    (
                        "Expected interruption: "
                        f"{_clean(option.interruption_expected_mode)}, "
                        f"{option.interruption_minimum_minutes}-"
                        f"{option.interruption_maximum_minutes} minutes"
                    ),
                    (
                        "Recovery: "
                        f"{_clean(option.recovery_feasibility)}, "
                        f"{option.recovery_minimum_minutes}-"
                        f"{option.recovery_maximum_minutes} minutes"
                    ),
                )
            )
            lines.extend(
                (
                    f"Step {step.order}: {_clean(step.phase)} - "
                    f"{_clean(step.conceptual_action)} [{step.capability_class}]"
                )
                for step in option.steps
            )
            lines.extend(f"Evidence: {_clean(item)}" for item in option.evidence_references)
            lines.extend(f"Assumption: {_clean(item)}" for item in option.assumptions)
            lines.extend(f"Unknown: {_clean(item)}" for item in option.unknowns)
            lines.extend(f"Evidence gap: {_clean(item)}" for item in option.evidence_gaps)
        if instruction.evidence_needs:
            lines.extend(("", "Additional evidence needed"))
            lines.extend(f"- {_clean(item)}" for item in instruction.evidence_needs)
        lines.extend(
            (
                "",
                "Review boundary",
                "- This content is read-only and is presented only to the assigned reviewer.",
                "- No finding, decision, approval, workflow, or operational action is recorded.",
            )
        )
        content = "\n".join(lines)
        encoded = content.encode("utf-8")
        truncated = len(encoded) > instruction.maximum_content_bytes
        if truncated:
            encoded = encoded[: instruction.maximum_content_bytes]
            while True:
                try:
                    content = encoded.decode("utf-8")
                    break
                except UnicodeDecodeError:
                    encoded = encoded[:-1]
        presented_at = self._clock()
        receipt = RecommendationProtectedContentReceipt(
            presentation_id=instruction.presentation_id,
            schema_version="atlas.recommendation-protected-content-receipt.v1",
            version=1,
            presenter_id="recommendation-protected-content-presenter.synthetic",
            attested_by="subject.recommendation-protected-content-presenter-attestor",
            lease_id=instruction.lease_id,
            lease_digest=instruction.lease_digest,
            recommendation_id=instruction.recommendation_id,
            promotion_id=instruction.promotion_id,
            recommendation_artifact_digest=instruction.recommendation_artifact_digest,
            track_code=instruction.track_code,
            lease_holder_subject_digest=instruction.lease_holder_subject_digest,
            browser_session_binding_digest=instruction.browser_session_binding_digest,
            output_media_type=instruction.output_media_type,
            language=instruction.language,
            presented_content_digest=sha256(encoded).hexdigest(),
            content_bytes=len(encoded),
            source_binding_digest=instruction.source_binding_digest,
            redaction_digest=_digest([instruction.redaction_profile_id, "applied"]),
            truncation_digest=_digest([instruction.maximum_content_bytes, truncated, len(encoded)]),
            cleanup_digest=_digest([instruction.presentation_id, "buffers-erased", "closed"]),
            presented_at=presented_at,
            expires_at=instruction.expires_at,
            source_integrity_verified=True,
            redaction_applied=True,
            truncated=truncated,
            active_content_rejected=True,
            transient_buffers_erased=True,
            presenter_channel_closed=True,
            signature_verified=True,
            canonical_digest="0" * 64,
        )
        payload = asdict(receipt)
        payload.pop("canonical_digest")
        receipt = replace(receipt, canonical_digest=_digest(_normalize(payload)))
        return RecommendationProtectedContentPresenterGrant(receipt=receipt, content=content)


def _normalize(value: object) -> object:
    if isinstance(value, datetime):
        return value.isoformat()
    if isinstance(value, dict):
        return {str(key): _normalize(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_normalize(item) for item in value]
    return value


class UnavailableRecommendationProtectedContentPresenter:
    async def present(
        self, instruction: RecommendationProtectedContentInstruction
    ) -> RecommendationProtectedContentPresenterGrant:
        del instruction
        raise RecommendationProtectedContentError(
            "recommendation_protected_content_presenter_unavailable"
        )
