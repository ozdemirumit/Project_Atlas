from __future__ import annotations

import asyncio
import base64
import hmac
from datetime import timedelta
from hashlib import sha256

from atlas.modules.connectors.application.package_signing_ports import PackageSigningError
from atlas.modules.connectors.domain.package_signing import (
    ConnectorPackageSignatureResult,
    ConnectorPackageSigningEnvelope,
    ConnectorPackageSigningPolicySnapshot,
    ConnectorPackageSigningReceipt,
)


class InMemoryPackageSigningRepository:
    def __init__(self) -> None:
        self._receipts: dict[str, ConnectorPackageSigningReceipt] = {}
        self._attestation_index: dict[str, str] = {}
        self._create_index: dict[tuple[str, str], str] = {}
        self._lock = asyncio.Lock()

    @property
    def durable(self) -> bool:
        return False

    async def get(self, *, receipt_id: str) -> ConnectorPackageSigningReceipt | None:
        return self._receipts.get(receipt_id)

    async def get_by_attestation(
        self, *, source_attestation_report_id: str
    ) -> ConnectorPackageSigningReceipt | None:
        receipt_id = self._attestation_index.get(source_attestation_report_id)
        return self._receipts.get(receipt_id) if receipt_id else None

    async def get_by_create_key(
        self, *, requested_by: str, idempotency_key: str
    ) -> ConnectorPackageSigningReceipt | None:
        receipt_id = self._create_index.get((requested_by, idempotency_key))
        return self._receipts.get(receipt_id) if receipt_id else None

    async def add(self, receipt: ConnectorPackageSigningReceipt) -> bool:
        async with self._lock:
            key = (receipt.requested_by, receipt.idempotency_key)
            if (
                receipt.receipt_id in self._receipts
                or receipt.envelope.source_attestation_report_id in self._attestation_index
                or key in self._create_index
            ):
                return False
            self._receipts[receipt.receipt_id] = receipt
            self._attestation_index[receipt.envelope.source_attestation_report_id] = (
                receipt.receipt_id
            )
            self._create_index[key] = receipt.receipt_id
            return True

    async def close(self) -> None:
        return None


class InMemoryPackageSigningPolicySource:
    def __init__(self, policies: tuple[ConnectorPackageSigningPolicySnapshot, ...] = ()) -> None:
        self._records = {item.policy_id: item for item in policies}

    async def get_by_id(self, *, policy_id: str) -> ConnectorPackageSigningPolicySnapshot | None:
        return self._records.get(policy_id)


class NonProductionHmacPackageSigner:
    def __init__(self, *, key_material: bytes, signer_workload_id: str) -> None:
        if len(key_material) < 32:
            raise ValueError("Non-production signer key must be at least 32 bytes")
        self._key_material = key_material
        self._signer_workload_id = signer_workload_id
        self.invocation_count = 0

    async def sign(
        self,
        *,
        envelope: ConnectorPackageSigningEnvelope,
        policy: ConnectorPackageSigningPolicySnapshot,
        idempotency_key: str,
    ) -> ConnectorPackageSignatureResult:
        if (
            policy.signer_profile_id != "signer-profile.nonproduction-hmac"
            or policy.algorithm != "algorithm.hmac-sha256-nonproduction"
            or policy.signer_workload_id != self._signer_workload_id
        ):
            raise PackageSigningError("package_signing_signer_profile_invalid")
        self.invocation_count += 1
        signature_bytes = hmac.new(
            self._key_material,
            f"{envelope.canonical_digest}:{idempotency_key}".encode("ascii"),
            sha256,
        ).digest()
        signature_value = base64.urlsafe_b64encode(signature_bytes).decode("ascii").rstrip("=")
        return ConnectorPackageSignatureResult(
            signer_profile_id=policy.signer_profile_id,
            signer_workload_id=policy.signer_workload_id,
            key_id=policy.key_id,
            algorithm=policy.algorithm,
            envelope_digest=envelope.canonical_digest,
            signature_value=signature_value,
            signature_digest=sha256(signature_bytes).hexdigest(),
            issued_at=envelope.created_at,
            expires_at=envelope.created_at + timedelta(hours=policy.signature_lifetime_hours),
            signature_verified=True,
        )


class UnavailablePackageSigner:
    async def sign(
        self,
        *,
        envelope: ConnectorPackageSigningEnvelope,
        policy: ConnectorPackageSigningPolicySnapshot,
        idempotency_key: str,
    ) -> ConnectorPackageSignatureResult:
        del envelope, policy, idempotency_key
        raise PackageSigningError("package_signing_signer_unavailable")
