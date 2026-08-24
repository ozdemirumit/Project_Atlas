from __future__ import annotations

import json
from dataclasses import asdict, replace
from datetime import UTC, datetime
from hashlib import sha256

from atlas.modules.connectors.application.runtime_activation_ports import (
    ConnectorRuntimeActivationError,
)
from atlas.modules.connectors.domain.runtime_activation import (
    ConnectorRuntimeActivationInstruction,
    ConnectorRuntimeActivationReceipt,
    ConnectorRuntimeHealthProbeResult,
)


class SyntheticConnectorRuntimeActivator:
    def __init__(self, *, clock=None) -> None:  # type: ignore[no-untyped-def]
        self._clock = clock or (lambda: datetime.now(UTC))
        self.activated: set[str] = set()
        self.compensated: set[str] = set()

    async def activate(
        self, instruction: ConnectorRuntimeActivationInstruction
    ) -> ConnectorRuntimeActivationReceipt:
        self.activated.add(instruction.activation_attempt_id)
        now = self._clock()
        receipt = ConnectorRuntimeActivationReceipt(
            receipt_id=(
                "connector-runtime-activation-receipt."
                f"{instruction.activation_attempt_id.rsplit('.', 1)[-1]}"
            ),
            schema_version="atlas.connector-runtime-activation-receipt.v1",
            version=1,
            activation_id=instruction.activation_id,
            activation_attempt_id=instruction.activation_attempt_id,
            organization_id=instruction.organization_id,
            environment_id=instruction.environment_id,
            source_brokerage_authorization_digest=(
                instruction.source_brokerage_authorization_digest
            ),
            package_digest=instruction.package_digest,
            activation_profile_digest=instruction.activation_profile_digest,
            activation_policy_digest=instruction.activation_policy_digest,
            activation_adapter_id=instruction.activation_adapter_id,
            runner_identity_digest=instruction.runner_identity_digest,
            image_digest=instruction.image_digest,
            workload_identity_digest=instruction.workload_identity_digest,
            health_probe_results=tuple(
                ConnectorRuntimeHealthProbeResult(probe_id=item, outcome="health.passed")
                for item in instruction.health_probe_ids
            ),
            started_at=now,
            healthy_at=now,
            lease_delivery_confirmed=True,
            delivery_channel_closed=True,
            lease_revocation_confirmed=True,
            runner_started=True,
            package_loaded=True,
            runtime_healthy=True,
            target_network_used=False,
            capability_invoked=False,
            signed_by="subject.connector-runtime-activation-adapter-attestor",
            signature_verified=True,
            canonical_digest="0" * 64,
        )
        return replace(receipt, canonical_digest=self._digest(receipt))

    async def compensate(self, *, activation_attempt_id: str) -> None:
        self.compensated.add(activation_attempt_id)

    @staticmethod
    def _digest(receipt: ConnectorRuntimeActivationReceipt) -> str:
        payload = asdict(receipt)
        payload.pop("canonical_digest")
        for field in ("started_at", "healthy_at"):
            payload[field] = payload[field].isoformat()
        return sha256(
            json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("ascii")
        ).hexdigest()


class UnavailableConnectorRuntimeActivator:
    async def activate(
        self, instruction: ConnectorRuntimeActivationInstruction
    ) -> ConnectorRuntimeActivationReceipt:
        del instruction
        raise ConnectorRuntimeActivationError("runtime_activation_adapter_unavailable")

    async def compensate(self, *, activation_attempt_id: str) -> None:
        del activation_attempt_id
