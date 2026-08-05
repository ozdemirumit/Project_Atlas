from __future__ import annotations

import asyncio

from atlas.modules.connectors.domain.final_validation import (
    ConnectorPackageFinalValidation,
    FinalValidationPolicySnapshot,
)


class InMemoryPackageFinalValidationRepository:
    def __init__(self) -> None:
        self._records: dict[str, ConnectorPackageFinalValidation] = {}
        self._source_index: dict[str, str] = {}
        self._create_index: dict[tuple[str, str], str] = {}
        self._lock = asyncio.Lock()

    @property
    def durable(self) -> bool:
        return False

    async def get_by_id(self, *, validation_id: str) -> ConnectorPackageFinalValidation | None:
        return self._records.get(validation_id)

    async def get_by_source_self_test(
        self, *, source_lab_self_test_id: str
    ) -> ConnectorPackageFinalValidation | None:
        validation_id = self._source_index.get(source_lab_self_test_id)
        return self._records.get(validation_id) if validation_id else None

    async def get_by_create_key(
        self, *, validated_by: str, idempotency_key: str
    ) -> ConnectorPackageFinalValidation | None:
        validation_id = self._create_index.get((validated_by, idempotency_key))
        return self._records.get(validation_id) if validation_id else None

    async def add(self, validation: ConnectorPackageFinalValidation) -> bool:
        async with self._lock:
            create_key = (validation.validated_by, validation.idempotency_key)
            if (
                validation.validation_id in self._records
                or validation.source_lab_self_test_id in self._source_index
                or create_key in self._create_index
            ):
                return False
            self._records[validation.validation_id] = validation
            self._source_index[validation.source_lab_self_test_id] = validation.validation_id
            self._create_index[create_key] = validation.validation_id
            return True

    async def close(self) -> None:
        return None


class InMemoryFinalValidationPolicySource:
    def __init__(self, policies: tuple[FinalValidationPolicySnapshot, ...] = ()) -> None:
        self._records = {item.policy_id: item for item in policies}

    async def get_by_id(self, *, policy_id: str) -> FinalValidationPolicySnapshot | None:
        return self._records.get(policy_id)

    async def add(self, policy: FinalValidationPolicySnapshot) -> bool:
        if policy.policy_id in self._records:
            return False
        self._records[policy.policy_id] = policy
        return True
