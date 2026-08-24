from __future__ import annotations

import json
from dataclasses import asdict, replace
from datetime import UTC, datetime
from hashlib import sha256

from atlas.modules.connectors.application.target_session_ports import ConnectorTargetSessionError
from atlas.modules.connectors.domain.target_session import (
    ConnectorTargetConnectivityCheckResult,
    ConnectorTargetSessionInstruction,
    ConnectorTargetSessionReceipt,
)


class SyntheticConnectorTargetSessionAdapter:
    def __init__(self, *, clock=None) -> None:  # type: ignore[no-untyped-def]
        self._clock = clock or (lambda: datetime.now(UTC))
        self.compensated: set[str] = set()

    async def verify(
        self, instruction: ConnectorTargetSessionInstruction
    ) -> ConnectorTargetSessionReceipt:
        receipt = ConnectorTargetSessionReceipt(
            receipt_id=(
                f"connector-target-session-receipt.{instruction.verification_id.rsplit('.', 1)[-1]}"
            ),
            schema_version="atlas.connector-target-session-receipt.v1",
            version=1,
            verification_id=instruction.verification_id,
            verification_attempt_id=instruction.verification_attempt_id,
            organization_id=instruction.organization_id,
            environment_id=instruction.environment_id,
            source_runtime_activation_digest=instruction.source_runtime_activation_digest,
            package_digest=instruction.package_digest,
            session_profile_digest=instruction.session_profile_digest,
            session_policy_digest=instruction.session_policy_digest,
            session_adapter_id=instruction.session_adapter_id,
            target_identity_digest=instruction.expected_target_identity_digest,
            protocol_classification=instruction.protocol_classification,
            tls_classification="tls.1-3-verified",
            connectivity_check_results=tuple(
                ConnectorTargetConnectivityCheckResult(check_id=item, outcome="connectivity.passed")
                for item in instruction.connectivity_check_ids
            ),
            verified_at=self._clock(),
            lease_delivery_confirmed=True,
            authentication_verified=True,
            target_identity_verified=True,
            read_only_privilege_verified=True,
            target_session_established=True,
            target_session_closed=True,
            delivery_channel_closed=True,
            lease_revocation_confirmed=True,
            capability_invoked=False,
            signed_by="subject.connector-target-session-adapter-attestor",
            signature_verified=True,
            canonical_digest="0" * 64,
        )
        return replace(receipt, canonical_digest=self._digest(receipt))

    async def compensate(self, *, verification_attempt_id: str) -> None:
        self.compensated.add(verification_attempt_id)

    @staticmethod
    def _digest(receipt: ConnectorTargetSessionReceipt) -> str:
        payload = asdict(receipt)
        payload.pop("canonical_digest")
        payload["verified_at"] = payload["verified_at"].isoformat()
        return sha256(
            json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("ascii")
        ).hexdigest()


class UnavailableConnectorTargetSessionAdapter:
    async def verify(
        self, instruction: ConnectorTargetSessionInstruction
    ) -> ConnectorTargetSessionReceipt:
        del instruction
        raise ConnectorTargetSessionError("target_session_adapter_unavailable")

    async def compensate(self, *, verification_attempt_id: str) -> None:
        del verification_attempt_id
