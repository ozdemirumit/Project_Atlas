from __future__ import annotations

import json
from collections.abc import Callable
from dataclasses import asdict, replace
from datetime import UTC, datetime
from hashlib import sha256

from atlas.modules.connectors.application.invocation_evidence_ports import (
    ConnectorInvocationEvidenceAdapter,
    ConnectorInvocationEvidenceError,
)
from atlas.modules.connectors.domain.invocation_evidence import (
    ConnectorInvocationEvidenceInstruction,
    ConnectorInvocationEvidenceReceipt,
)


class SyntheticConnectorInvocationEvidenceAdapter:
    def __init__(self, *, clock: Callable[[], datetime] | None = None) -> None:
        self._clock = clock or (lambda: datetime.now(UTC))
        self.calls: list[str] = []

    async def ingest(
        self, instruction: ConnectorInvocationEvidenceInstruction
    ) -> ConnectorInvocationEvidenceReceipt:
        self.calls.append(instruction.ingestion_id)
        ingested_at = max(self._clock(), instruction.source_completed_at)
        receipt = ConnectorInvocationEvidenceReceipt(
            ingestion_id=instruction.ingestion_id,
            schema_version="atlas.connector-invocation-evidence-receipt.v1",
            version=1,
            adapter_id="connector-invocation-evidence-adapter.synthetic",
            attested_by="subject.connector-invocation-evidence-adapter-attestor",
            source_invocation_digest=instruction.source_invocation_digest,
            normalized_redacted_result_digest=instruction.normalized_redacted_result_digest,
            evidence_package_id=(
                f"connector-evidence-package.{instruction.ingestion_id.rsplit('.', 1)[-1]}"
            ),
            evidence_schema_version="atlas.connector-evidence-package.v1",
            evidence_content_digest=self._digest(
                [instruction.normalized_redacted_result_digest, "synthetic-immutable-content-v1"]
            ),
            evidence_metadata_digest=self._digest(
                [instruction.ingestion_policy_digest, "synthetic-governed-metadata-v1"]
            ),
            classification=instruction.classification,
            access_policy_id=instruction.access_policy_id,
            access_policy_digest=instruction.access_policy_digest,
            retention_policy_id=instruction.retention_policy_id,
            retention_policy_digest=instruction.retention_policy_digest,
            encryption_profile_id=instruction.encryption_profile_id,
            encryption_profile_digest=instruction.encryption_profile_digest,
            evidence_item_count=instruction.source_observation_count,
            evidence_bytes=instruction.source_output_bytes,
            observed_from=instruction.source_started_at,
            observed_to=instruction.source_completed_at,
            ingested_at=ingested_at,
            immutable_storage_confirmed=True,
            encrypted_at_rest=True,
            transient_buffers_erased=True,
            artifact_channel_closed=True,
            signature_verified=True,
            canonical_digest="0" * 64,
        )
        return replace(receipt, canonical_digest=self._receipt_digest(receipt))

    @classmethod
    def _receipt_digest(cls, receipt: ConnectorInvocationEvidenceReceipt) -> str:
        payload = asdict(receipt)
        payload.pop("canonical_digest")
        for field in ("observed_from", "observed_to", "ingested_at"):
            payload[field] = payload[field].isoformat()
        return cls._digest(payload)

    @staticmethod
    def _digest(payload: object) -> str:
        return sha256(
            json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("ascii")
        ).hexdigest()


class UnavailableConnectorInvocationEvidenceAdapter(ConnectorInvocationEvidenceAdapter):
    async def ingest(
        self, instruction: ConnectorInvocationEvidenceInstruction
    ) -> ConnectorInvocationEvidenceReceipt:
        del instruction
        raise ConnectorInvocationEvidenceError("invocation_evidence_adapter_unavailable")
