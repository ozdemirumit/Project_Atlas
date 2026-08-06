from __future__ import annotations

import json
from collections.abc import Callable
from dataclasses import asdict, replace
from datetime import UTC, datetime
from hashlib import sha256

from atlas.modules.knowledge.application.protected_content_ports import (
    OperationalKnowledgeProtectedContentError,
)
from atlas.modules.knowledge.domain.protected_content import (
    OperationalKnowledgeProtectedContentInstruction,
    OperationalKnowledgeProtectedContentPresenterGrant,
    OperationalKnowledgeProtectedContentReceipt,
)


def _digest(value: object) -> str:
    return sha256(
        json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode("ascii")
    ).hexdigest()


class SyntheticOperationalKnowledgeProtectedContentPresenter:
    def __init__(self, *, clock: Callable[[], datetime] | None = None) -> None:
        self._clock = clock or (lambda: datetime.now(UTC))
        self.calls: list[OperationalKnowledgeProtectedContentInstruction] = []

    async def present(
        self, instruction: OperationalKnowledgeProtectedContentInstruction
    ) -> OperationalKnowledgeProtectedContentPresenterGrant:
        self.calls.append(instruction)
        track = instruction.track_code.removeprefix("review-track.").title()
        content = "\n".join(
            (
                "Operational knowledge review snapshot",
                "",
                f"Title: {instruction.title}",
                f"Review track: {track}",
                f"Knowledge item: {instruction.knowledge_item_id}",
                f"Draft version: {instruction.draft_version_id}",
                "",
                "Evidence summary",
                "- The immutable operational evidence draft is available for accountable review.",
                "- Source integrity, classification, access, and retention bindings were verified.",
                "- Sensitive values are redacted by the governed synthetic presentation profile.",
                "",
                "Review boundary",
                "- This snapshot is read-only and supports inspection only.",
                "- No finding, decision, approval, publication, or operational action is recorded.",
            )
        )
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
        receipt = OperationalKnowledgeProtectedContentReceipt(
            presentation_id=instruction.presentation_id,
            schema_version="atlas.operational-knowledge-protected-content-receipt.v1",
            version=1,
            presenter_id="operational-knowledge-protected-content-presenter.synthetic",
            attested_by="subject.operational-knowledge-protected-content-presenter-attestor",
            lease_id=instruction.lease_id,
            lease_digest=instruction.lease_digest,
            source_draft_id=instruction.source_draft_id,
            source_draft_digest=instruction.source_draft_digest,
            draft_artifact_id=instruction.draft_artifact_id,
            draft_content_digest=instruction.draft_content_digest,
            track_code=instruction.track_code,
            lease_holder_subject_digest=instruction.lease_holder_subject_digest,
            browser_session_binding_digest=instruction.browser_session_binding_digest,
            output_media_type=instruction.output_media_type,
            language=instruction.language,
            presented_content_digest=sha256(encoded).hexdigest(),
            content_bytes=len(encoded),
            source_binding_digest=_digest(
                [instruction.draft_artifact_id, instruction.draft_content_digest]
            ),
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
            artifact_channel_closed=True,
            signature_verified=True,
            canonical_digest="0" * 64,
        )
        payload = asdict(receipt)
        payload.pop("canonical_digest")
        receipt = replace(receipt, canonical_digest=_digest(_normalize(payload)))
        return OperationalKnowledgeProtectedContentPresenterGrant(receipt=receipt, content=content)


def _normalize(value: object) -> object:
    if isinstance(value, datetime):
        return value.isoformat()
    if isinstance(value, dict):
        return {str(key): _normalize(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_normalize(item) for item in value]
    return value


class UnavailableOperationalKnowledgeProtectedContentPresenter:
    async def present(
        self, instruction: OperationalKnowledgeProtectedContentInstruction
    ) -> OperationalKnowledgeProtectedContentPresenterGrant:
        del instruction
        raise OperationalKnowledgeProtectedContentError(
            "operational_knowledge_protected_content_presenter_unavailable"
        )
