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
        self._assignment_index: dict[tuple[str, str, str], str] = {}
        self._create_index: dict[tuple[str, str, str, str], str] = {}
        self._lock = asyncio.Lock()

    async def get(self, *, validation_id: str) -> ConnectorConfigurationValidationRecord | None:
        return self._records.get(validation_id)

    async def get_in_scope(
        self,
        *,
        validation_id: str,
        organization_id: str,
        environment_id: str,
    ) -> ConnectorConfigurationValidationRecord | None:
        record = self._records.get(validation_id)
        if (
            record is None
            or record.organization_id != organization_id
            or record.environment_id != environment_id
        ):
            return None
        return record

    async def get_by_assignment(
        self, *, source_assignment_id: str
    ) -> ConnectorConfigurationValidationRecord | None:
        return next(
            (
                record
                for record in self._records.values()
                if record.source_assignment_id == source_assignment_id
            ),
            None,
        )

    async def get_by_assignment_in_scope(
        self,
        *,
        source_assignment_id: str,
        organization_id: str,
        environment_id: str,
    ) -> ConnectorConfigurationValidationRecord | None:
        validation_id = self._assignment_index.get(
            (organization_id, environment_id, source_assignment_id)
        )
        return self._records.get(validation_id) if validation_id else None

    async def list_scope(
        self, *, organization_id: str, environment_id: str
    ) -> tuple[ConnectorConfigurationValidationRecord, ...]:
        return tuple(
            sorted(
                (
                    item
                    for item in self._records.values()
                    if item.organization_id == organization_id
                    and item.environment_id == environment_id
                ),
                key=lambda item: item.validation_id,
            )
        )

    async def get_by_create_key(
        self, *, validated_by: str, idempotency_key: str
    ) -> ConnectorConfigurationValidationRecord | None:
        return next(
            (
                record
                for record in self._records.values()
                if record.validated_by == validated_by and record.idempotency_key == idempotency_key
            ),
            None,
        )

    async def get_by_create_key_in_scope(
        self,
        *,
        validated_by: str,
        idempotency_key: str,
        organization_id: str,
        environment_id: str,
    ) -> ConnectorConfigurationValidationRecord | None:
        validation_id = self._create_index.get(
            (organization_id, environment_id, validated_by, idempotency_key)
        )
        return self._records.get(validation_id) if validation_id else None

    async def add(self, record: ConnectorConfigurationValidationRecord) -> bool:
        async with self._lock:
            assignment_key = (
                record.organization_id,
                record.environment_id,
                record.source_assignment_id,
            )
            create_key = (
                record.organization_id,
                record.environment_id,
                record.validated_by,
                record.idempotency_key,
            )
            if (
                record.validation_id in self._records
                or assignment_key in self._assignment_index
                or create_key in self._create_index
            ):
                return False
            self._records[record.validation_id] = record
            self._assignment_index[assignment_key] = record.validation_id
            self._create_index[create_key] = record.validation_id
            return True

    async def close(self) -> None:
        return None


class InMemoryConnectorConfigurationEvidenceSource:
    def __init__(self, snapshots: tuple[ConnectorConfigurationEvidenceSnapshot, ...]) -> None:
        self._snapshots = {item.evidence_id: item for item in snapshots}

    async def get_by_id(self, *, evidence_id: str) -> ConnectorConfigurationEvidenceSnapshot | None:
        return self._snapshots.get(evidence_id)

    async def get_by_id_in_scope(
        self,
        *,
        evidence_id: str,
        organization_id: str,
        environment_id: str,
    ) -> ConnectorConfigurationEvidenceSnapshot | None:
        snapshot = self._snapshots.get(evidence_id)
        if (
            snapshot is None
            or snapshot.organization_id != organization_id
            or snapshot.environment_id != environment_id
        ):
            return None
        return snapshot

    async def list_scope(
        self, *, organization_id: str, environment_id: str
    ) -> tuple[ConnectorConfigurationEvidenceSnapshot, ...]:
        return tuple(
            sorted(
                (
                    item
                    for item in self._snapshots.values()
                    if item.organization_id == organization_id
                    and item.environment_id == environment_id
                ),
                key=lambda item: item.evidence_id,
            )
        )


class InMemoryConnectorConfigurationValidationPolicySource:
    def __init__(
        self, policies: tuple[ConnectorConfigurationValidationPolicySnapshot, ...]
    ) -> None:
        self._policies = {item.policy_id: item for item in policies}

    async def get_by_id(
        self, *, policy_id: str
    ) -> ConnectorConfigurationValidationPolicySnapshot | None:
        return self._policies.get(policy_id)

    async def get_by_id_in_scope(
        self,
        *,
        policy_id: str,
        organization_id: str,
        environment_id: str,
    ) -> ConnectorConfigurationValidationPolicySnapshot | None:
        policy = self._policies.get(policy_id)
        if (
            policy is None
            or policy.organization_id != organization_id
            or policy.environment_id != environment_id
        ):
            return None
        return policy

    async def list_scope(
        self, *, organization_id: str, environment_id: str
    ) -> tuple[ConnectorConfigurationValidationPolicySnapshot, ...]:
        return tuple(
            sorted(
                (
                    item
                    for item in self._policies.values()
                    if item.organization_id == organization_id
                    and item.environment_id == environment_id
                ),
                key=lambda item: item.policy_id,
            )
        )
