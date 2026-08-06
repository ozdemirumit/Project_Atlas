from __future__ import annotations

import json
from collections.abc import Callable
from dataclasses import asdict, replace
from datetime import UTC, datetime, timedelta
from hashlib import sha256

from atlas.modules.connectors.application.bounded_invocation_ports import (
    ConnectorBoundedInvocationAdapter,
    ConnectorBoundedInvocationError,
)
from atlas.modules.connectors.domain.bounded_invocation import (
    ConnectorBoundedInvocationInstruction,
    ConnectorBoundedInvocationReceipt,
)


class SyntheticConnectorBoundedInvocationAdapter:
    def __init__(self, *, clock: Callable[[], datetime] | None = None) -> None:
        self._clock = clock or (lambda: datetime.now(UTC))
        self.calls: list[str] = []

    async def invoke(
        self, instruction: ConnectorBoundedInvocationInstruction
    ) -> ConnectorBoundedInvocationReceipt:
        self.calls.append(instruction.invocation_id)
        started_at = self._clock()
        receipt = ConnectorBoundedInvocationReceipt(
            invocation_id=instruction.invocation_id,
            schema_version="atlas.connector-bounded-invocation-receipt.v1",
            version=1,
            adapter_id="connector-bounded-invocation-adapter.synthetic",
            attested_by="subject.connector-bounded-invocation-adapter-attestor",
            source_authorization_digest=instruction.source_authorization_digest,
            capability_id=instruction.capability_id,
            invocation_profile_digest=instruction.invocation_profile_digest,
            input_envelope_digest=instruction.input_envelope_digest,
            result_schema_digest=instruction.output_schema_digest,
            result_policy_digest=instruction.result_policy_digest,
            normalized_redacted_result_digest=self._digest(
                [instruction.capability_id, "synthetic-redacted-result-v1"]
            ),
            observation_count=1,
            output_bytes=256,
            started_at=started_at,
            completed_at=started_at + timedelta(milliseconds=25),
            target_connection_opened=True,
            capability_invoked_once=True,
            result_received=True,
            result_schema_validated=True,
            result_redacted=True,
            target_session_closed=True,
            delivery_channel_closed=True,
            lease_revocation_confirmed=True,
            target_disconnected=True,
            signature_verified=True,
            canonical_digest="0" * 64,
        )
        return replace(receipt, canonical_digest=self._receipt_digest(receipt))

    @classmethod
    def _receipt_digest(cls, receipt: ConnectorBoundedInvocationReceipt) -> str:
        payload = asdict(receipt)
        payload.pop("canonical_digest")
        for field in ("started_at", "completed_at"):
            payload[field] = payload[field].isoformat()
        return cls._digest(payload)

    @staticmethod
    def _digest(payload: object) -> str:
        return sha256(
            json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("ascii")
        ).hexdigest()


class UnavailableConnectorBoundedInvocationAdapter(ConnectorBoundedInvocationAdapter):
    async def invoke(
        self, instruction: ConnectorBoundedInvocationInstruction
    ) -> ConnectorBoundedInvocationReceipt:
        del instruction
        raise ConnectorBoundedInvocationError("bounded_invocation_adapter_unavailable")
