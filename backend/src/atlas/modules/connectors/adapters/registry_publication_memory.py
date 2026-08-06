from __future__ import annotations

import asyncio
import hmac
from dataclasses import replace
from datetime import datetime
from hashlib import sha256

from atlas.modules.connectors.application.package_signing import PackageSigningService
from atlas.modules.connectors.application.registry_publication_ports import (
    RegistryPublicationError,
)
from atlas.modules.connectors.domain.package_signing import (
    ConnectorPackageSigningPolicySnapshot,
    ConnectorPackageSigningReceipt,
)
from atlas.modules.connectors.domain.registry_publication import (
    ConnectorInternalRegistryPublicationReceipt,
    ConnectorInternalRegistryPublicationResult,
    ConnectorPackageSignatureVerification,
    ConnectorRegistryPublicationPolicySnapshot,
)


class InMemoryRegistryPublicationRepository:
    def __init__(self) -> None:
        self._receipts: dict[str, ConnectorInternalRegistryPublicationReceipt] = {}
        self._signing_index: dict[str, str] = {}
        self._create_index: dict[tuple[str, str], str] = {}
        self._lock = asyncio.Lock()

    @property
    def durable(self) -> bool:
        return False

    async def get(self, *, receipt_id: str) -> ConnectorInternalRegistryPublicationReceipt | None:
        return self._receipts.get(receipt_id)

    async def get_by_signing_receipt(
        self, *, source_signing_receipt_id: str
    ) -> ConnectorInternalRegistryPublicationReceipt | None:
        receipt_id = self._signing_index.get(source_signing_receipt_id)
        return self._receipts.get(receipt_id) if receipt_id else None

    async def get_by_create_key(
        self, *, requested_by: str, idempotency_key: str
    ) -> ConnectorInternalRegistryPublicationReceipt | None:
        receipt_id = self._create_index.get((requested_by, idempotency_key))
        return self._receipts.get(receipt_id) if receipt_id else None

    async def add(self, receipt: ConnectorInternalRegistryPublicationReceipt) -> bool:
        async with self._lock:
            key = (receipt.requested_by, receipt.idempotency_key)
            if (
                receipt.receipt_id in self._receipts
                or receipt.source_signing_receipt_id in self._signing_index
                or key in self._create_index
            ):
                return False
            self._receipts[receipt.receipt_id] = receipt
            self._signing_index[receipt.source_signing_receipt_id] = receipt.receipt_id
            self._create_index[key] = receipt.receipt_id
            return True

    async def close(self) -> None:
        return None


class InMemoryRegistryPublicationPolicySource:
    def __init__(
        self, policies: tuple[ConnectorRegistryPublicationPolicySnapshot, ...] = ()
    ) -> None:
        self._records = {item.policy_id: item for item in policies}

    async def get_by_id(
        self, *, policy_id: str
    ) -> ConnectorRegistryPublicationPolicySnapshot | None:
        return self._records.get(policy_id)


class NonProductionHmacPackageSignatureVerifier:
    def __init__(self, *, key_material: bytes, verifier_workload_id: str) -> None:
        if len(key_material) < 32:
            raise ValueError("Non-production verifier key must be at least 32 bytes")
        self._key_material = key_material
        self._verifier_workload_id = verifier_workload_id
        self.invocation_count = 0

    async def verify(
        self,
        *,
        receipt: ConnectorPackageSigningReceipt,
        signing_policy: ConnectorPackageSigningPolicySnapshot,
        publication_policy: ConnectorRegistryPublicationPolicySnapshot,
        verified_at: datetime,
    ) -> ConnectorPackageSignatureVerification:
        if (
            publication_policy.verifier_profile_id != "verifier-profile.nonproduction-hmac"
            or publication_policy.verifier_workload_id != self._verifier_workload_id
            or signing_policy.key_id != publication_policy.required_key_id
        ):
            raise RegistryPublicationError("registry_publication_verifier_profile_invalid")
        self.invocation_count += 1
        expected = hmac.new(
            self._key_material,
            f"{receipt.envelope.canonical_digest}:{receipt.idempotency_key}".encode("ascii"),
            sha256,
        ).digest()
        actual = PackageSigningService._signature_bytes(receipt.signature.signature_value)
        if not hmac.compare_digest(expected, actual):
            raise RegistryPublicationError("registry_publication_signature_invalid")
        return ConnectorPackageSignatureVerification(
            verifier_profile_id=publication_policy.verifier_profile_id,
            verifier_workload_id=self._verifier_workload_id,
            key_id=receipt.signature.key_id,
            algorithm=receipt.signature.algorithm,
            envelope_digest=receipt.envelope.canonical_digest,
            signature_digest=receipt.signature.signature_digest,
            verified_at=verified_at,
            signature_valid=True,
        )


class InMemoryNonProductionRegistryPublisher:
    def __init__(self, *, registry_profile_id: str, publisher_workload_id: str) -> None:
        self._registry_profile_id = registry_profile_id
        self._publisher_workload_id = publisher_workload_id
        self._results: dict[str, ConnectorInternalRegistryPublicationResult] = {}
        self._content: dict[str, bytes] = {}
        self._lock = asyncio.Lock()
        self.invocation_count = 0

    async def publish(
        self,
        *,
        content: bytes,
        source_signing_receipt_digest: str,
        policy: ConnectorRegistryPublicationPolicySnapshot,
        published_at: datetime,
        idempotency_key: str,
    ) -> ConnectorInternalRegistryPublicationResult:
        del idempotency_key
        if (
            policy.registry_profile_id != self._registry_profile_id
            or policy.publisher_workload_id != self._publisher_workload_id
        ):
            raise RegistryPublicationError("registry_publication_publisher_profile_invalid")
        package_digest = sha256(content).hexdigest()
        artifact_reference = f"registry-artifact.sha256-{package_digest}"
        publication_digest = sha256(
            (
                f"{policy.registry_profile_id}:{artifact_reference}:{package_digest}:"
                f"{len(content)}:{source_signing_receipt_digest}"
            ).encode("ascii")
        ).hexdigest()
        async with self._lock:
            self.invocation_count += 1
            existing = self._results.get(package_digest)
            if existing is not None:
                if self._content[package_digest] != content:
                    raise RegistryPublicationError("registry_publication_artifact_conflict")
                return replace(existing, reused=True)
            result = ConnectorInternalRegistryPublicationResult(
                registry_profile_id=policy.registry_profile_id,
                publisher_workload_id=policy.publisher_workload_id,
                artifact_reference_schema=policy.artifact_reference_schema,
                artifact_reference=artifact_reference,
                package_digest=package_digest,
                package_size_bytes=len(content),
                source_signing_receipt_digest=source_signing_receipt_digest,
                publication_digest=publication_digest,
                published_at=published_at,
                integrity_verified=True,
            )
            self._content[package_digest] = content
            self._results[package_digest] = result
            return result


class UnavailablePackageSignatureVerifier:
    async def verify(self, **_: object) -> ConnectorPackageSignatureVerification:
        raise RegistryPublicationError("registry_publication_verifier_unavailable")


class UnavailableInternalRegistryPublisher:
    async def publish(self, **_: object) -> ConnectorInternalRegistryPublicationResult:
        raise RegistryPublicationError("registry_publication_publisher_unavailable")
