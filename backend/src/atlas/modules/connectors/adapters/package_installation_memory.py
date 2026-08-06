from __future__ import annotations

import asyncio
from datetime import UTC, datetime

from atlas.modules.connectors.application.package_installation_ports import PackageInstallationError
from atlas.modules.connectors.domain.package_installation import (
    ConnectorPackageInstallationPolicySnapshot,
    ConnectorPackageInstallationReceipt,
    ConnectorPackageInstallationResult,
)
from atlas.modules.connectors.domain.package_registration import ConnectorPackageRegistrationRecord


class InMemoryPackageInstallationRepository:
    def __init__(self) -> None:
        self._receipts: dict[str, ConnectorPackageInstallationReceipt] = {}
        self._lock = asyncio.Lock()

    @property
    def durable(self) -> bool:
        return False

    async def get(self, *, receipt_id: str) -> ConnectorPackageInstallationReceipt | None:
        return self._receipts.get(receipt_id)

    async def get_by_registration_record(
        self, *, source_registration_record_id: str
    ) -> ConnectorPackageInstallationReceipt | None:
        return next(
            (
                item
                for item in self._receipts.values()
                if item.source_registration_record_id == source_registration_record_id
            ),
            None,
        )

    async def get_by_package_release(
        self, *, connector_id: str, release_version: str
    ) -> ConnectorPackageInstallationReceipt | None:
        return next(
            (
                item
                for item in self._receipts.values()
                if item.connector_id == connector_id and item.release_version == release_version
            ),
            None,
        )

    async def get_by_create_key(
        self, *, installed_by: str, idempotency_key: str
    ) -> ConnectorPackageInstallationReceipt | None:
        return next(
            (
                item
                for item in self._receipts.values()
                if item.installed_by == installed_by and item.idempotency_key == idempotency_key
            ),
            None,
        )

    async def add(self, receipt: ConnectorPackageInstallationReceipt) -> bool:
        async with self._lock:
            if receipt.receipt_id in self._receipts:
                return False
            if any(
                item.source_registration_record_id == receipt.source_registration_record_id
                or (
                    item.connector_id == receipt.connector_id
                    and item.release_version == receipt.release_version
                )
                or (
                    item.installed_by == receipt.installed_by
                    and item.idempotency_key == receipt.idempotency_key
                )
                for item in self._receipts.values()
            ):
                return False
            self._receipts[receipt.receipt_id] = receipt
            return True

    async def close(self) -> None:
        return None


class InMemoryPackageInstallationPolicySource:
    def __init__(self, policies: tuple[ConnectorPackageInstallationPolicySnapshot, ...]) -> None:
        self._policies = {item.policy_id: item for item in policies}

    async def get_by_id(
        self, *, policy_id: str
    ) -> ConnectorPackageInstallationPolicySnapshot | None:
        return self._policies.get(policy_id)


class InMemoryNonExecutingPackageInstaller:
    def __init__(self) -> None:
        self._content: dict[str, bytes] = {}
        self._references: dict[str, str] = {}
        self._lock = asyncio.Lock()
        self.invocation_count = 0

    async def install(
        self,
        *,
        content: bytes,
        registration: ConnectorPackageRegistrationRecord,
        policy: ConnectorPackageInstallationPolicySnapshot,
        idempotency_key: str,
    ) -> ConnectorPackageInstallationResult:
        del idempotency_key
        reference = (
            f"installation://{policy.installation_store_profile_id}/sha256:"
            f"{registration.package_digest}"
        )
        async with self._lock:
            existing = self._content.get(registration.package_digest)
            if existing is not None and existing != content:
                raise PackageInstallationError("package_installation_store_conflict")
            existing_reference = self._references.get(registration.package_digest)
            if existing_reference is not None and existing_reference != reference:
                raise PackageInstallationError("package_installation_store_conflict")
            self._content.setdefault(registration.package_digest, bytes(content))
            self._references.setdefault(registration.package_digest, reference)
            self.invocation_count += 1
        return ConnectorPackageInstallationResult(
            installer_profile_id=policy.installer_profile_id,
            installer_workload_id=policy.installer_workload_id,
            installation_custodian_id=policy.installation_custodian_id,
            installation_store_profile_id=policy.installation_store_profile_id,
            artifact_reference_schema=policy.installation_artifact_reference_schema,
            artifact_reference=reference,
            package_digest=registration.package_digest,
            package_size_bytes=len(content),
            stored_at=datetime.now(UTC),
        )


class UnavailablePackageInstaller:
    async def install(
        self,
        *,
        content: bytes,
        registration: ConnectorPackageRegistrationRecord,
        policy: ConnectorPackageInstallationPolicySnapshot,
        idempotency_key: str,
    ) -> ConnectorPackageInstallationResult:
        del content, registration, policy, idempotency_key
        raise PackageInstallationError("package_installation_installer_unavailable")
