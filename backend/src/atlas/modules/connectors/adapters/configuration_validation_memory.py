from __future__ import annotations

import asyncio

from atlas.modules.connectors.domain.configuration_validation import (
    ConnectorConfigurationEvidenceSnapshot,
    ConnectorConfigurationValidationPolicySnapshot,
    ConnectorConfigurationValidationRecord,
)


class InMemoryConnectorConfigurationValidationRepository:
    def __init__(self) -> None:
        self._records: dict[str, ConnectorConfigurationValidationRecord] = {}
        self._assignment_index: dict[str, str] = {}
        self._create_index: dict[tuple[str, str], str] = {}
        self._lock = asyncio.Lock()

    async def get(self, *, validation_id: str) -> ConnectorConfigurationValidationRecord | None:
        return self._records.get(validation_id)

    async def get_by_assignment(
        self, *, source_assignment_id: str
    ) -> ConnectorConfigurationValidationRecord | None:
        validation_id = self._assignment_index.get(source_assignment_id)
        return self._records.get(validation_id) if validation_id else None

    async def get_by_create_key(
        self, *, validated_by: str, idempotency_key: str
    ) -> ConnectorConfigurationValidationRecord | None:
        validation_id = self._create_index.get((validated_by, idempotency_key))
        return self._records.get(validation_id) if validation_id else None

    async def add(self, record: ConnectorConfigurationValidationRecord) -> bool:
        async with self._lock:
            create_key = (record.validated_by, record.idempotency_key)
            if (
                record.validation_id in self._records
                or record.source_assignment_id in self._assignment_index
                or create_key in self._create_index
            ):
                return False
            self._records[record.validation_id] = record
            self._assignment_index[record.source_assignment_id] = record.validation_id
            self._create_index[create_key] = record.validation_id
            return True

    async def close(self) -> None:
        return None


class InMemoryConnectorConfigurationEvidenceSource:
    def __init__(self, snapshots: tuple[ConnectorConfigurationEvidenceSnapshot, ...]) -> None:
        self._snapshots = {item.evidence_id: item for item in snapshots}

    async def get_by_id(self, *, evidence_id: str) -> ConnectorConfigurationEvidenceSnapshot | None:
        return self._snapshots.get(evidence_id)


class InMemoryConnectorConfigurationValidationPolicySource:
    def __init__(
        self, policies: tuple[ConnectorConfigurationValidationPolicySnapshot, ...]
    ) -> None:
        self._policies = {item.policy_id: item for item in policies}

    async def get_by_id(
        self, *, policy_id: str
    ) -> ConnectorConfigurationValidationPolicySnapshot | None:
        return self._policies.get(policy_id)
