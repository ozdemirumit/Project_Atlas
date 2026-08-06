from __future__ import annotations

import json
import secrets
from collections.abc import Callable
from dataclasses import asdict, replace
from datetime import UTC, datetime, timedelta
from enum import Enum
from hashlib import sha256

from atlas.modules.knowledge.application.protected_inspection_ports import (
    OperationalKnowledgeProtectedInspectionBroker,
    OperationalKnowledgeProtectedInspectionError,
)
from atlas.modules.knowledge.domain.protected_inspection import (
    OperationalKnowledgeProtectedInspectionBrokerGrant,
    OperationalKnowledgeProtectedInspectionInstruction,
    OperationalKnowledgeProtectedInspectionReceipt,
)


def _normalize(value: object) -> object:
    if isinstance(value, Enum):
        return value.value
    if isinstance(value, datetime):
        return value.isoformat()
    if isinstance(value, dict):
        return {str(key): _normalize(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_normalize(item) for item in value]
    return value


def _digest(payload: object) -> str:
    return sha256(
        json.dumps(_normalize(payload), sort_keys=True, separators=(",", ":")).encode("ascii")
    ).hexdigest()


class SyntheticOperationalKnowledgeProtectedInspectionBroker:
    broker_id = "operational-knowledge-protected-inspection-broker.synthetic"
    attestor_id = "subject.operational-knowledge-protected-inspection-broker-attestor"
    receipt_schema = "atlas.operational-knowledge-protected-inspection-receipt.v1"

    def __init__(self, *, clock: Callable[[], datetime] | None = None) -> None:
        self._clock = clock or (lambda: datetime.now(UTC))
        self.call_count = 0

    async def issue(
        self, instruction: OperationalKnowledgeProtectedInspectionInstruction
    ) -> OperationalKnowledgeProtectedInspectionBrokerGrant:
        self.call_count += 1
        issued_at = self._clock()
        lease_secret = secrets.token_urlsafe(48)
        lease_secret_digest = _digest(
            [instruction.inspection_policy_digest, "lease-secret", lease_secret]
        )
        receipt = OperationalKnowledgeProtectedInspectionReceipt(
            lease_id=instruction.lease_id,
            schema_version=self.receipt_schema,
            version=1,
            broker_id=self.broker_id,
            attested_by=self.attestor_id,
            assignment_set_id=instruction.assignment_set_id,
            assignment_set_digest=instruction.assignment_set_digest,
            track_code=instruction.track_code,
            opaque_assignment_id=instruction.opaque_assignment_id,
            lease_holder_subject_digest=instruction.current_subject_digest,
            browser_session_binding_digest=instruction.browser_session_binding_digest,
            lease_secret_digest=lease_secret_digest,
            lease_digest=_digest([instruction.lease_id, lease_secret_digest, "lease"]),
            assignment_binding_digest=_digest(
                [instruction.assignment_set_digest, instruction.opaque_assignment_id]
            ),
            policy_binding_digest=_digest(
                [instruction.inspection_policy_digest, instruction.lease_ttl_minutes]
            ),
            cleanup_digest=_digest([instruction.lease_id, "secret-buffer-erased"]),
            issued_at=issued_at,
            expires_at=issued_at + timedelta(minutes=instruction.lease_ttl_minutes),
            exact_assignee_verified=True,
            assignment_current=True,
            browser_session_bound=True,
            non_transferable=True,
            refresh_disabled=True,
            immutable_lease_confirmed=True,
            plaintext_secret_buffer_erased=True,
            broker_channel_closed=True,
            signature_verified=True,
            canonical_digest="0" * 64,
        )
        payload = asdict(receipt)
        payload.pop("canonical_digest")
        receipt = replace(receipt, canonical_digest=_digest(payload))
        return OperationalKnowledgeProtectedInspectionBrokerGrant(
            receipt=receipt,
            lease_secret=lease_secret,
        )


class UnavailableOperationalKnowledgeProtectedInspectionBroker(
    OperationalKnowledgeProtectedInspectionBroker
):
    async def issue(
        self, instruction: OperationalKnowledgeProtectedInspectionInstruction
    ) -> OperationalKnowledgeProtectedInspectionBrokerGrant:
        del instruction
        raise OperationalKnowledgeProtectedInspectionError(
            "operational_knowledge_protected_inspection_broker_unavailable"
        )
