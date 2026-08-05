from __future__ import annotations

import asyncio
from dataclasses import replace

from atlas.modules.connectors.domain.runner_validation import ConnectorPackageRunnerValidation


class InMemoryPackageRunnerValidationRepository:
    def __init__(self) -> None:
        self._records: dict[str, ConnectorPackageRunnerValidation] = {}
        self._lock = asyncio.Lock()

    @property
    def durable(self) -> bool:
        return False

    async def get_by_id(self, *, validation_id: str) -> ConnectorPackageRunnerValidation | None:
        value = self._records.get(validation_id)
        return replace(value) if value is not None else None

    async def get_by_source_validation(
        self, *, source_contract_validation_id: str
    ) -> ConnectorPackageRunnerValidation | None:
        return next(
            (
                replace(item)
                for item in self._records.values()
                if item.source_contract_validation_id == source_contract_validation_id
            ),
            None,
        )

    async def get_by_create_key(
        self, *, validated_by: str, idempotency_key: str
    ) -> ConnectorPackageRunnerValidation | None:
        return next(
            (
                replace(item)
                for item in self._records.values()
                if item.validated_by == validated_by and item.idempotency_key == idempotency_key
            ),
            None,
        )

    async def add(self, validation: ConnectorPackageRunnerValidation) -> bool:
        async with self._lock:
            if validation.validation_id in self._records:
                return False
            if any(
                item.source_contract_validation_id == validation.source_contract_validation_id
                or (
                    item.validated_by == validation.validated_by
                    and item.idempotency_key == validation.idempotency_key
                )
                for item in self._records.values()
            ):
                return False
            self._records[validation.validation_id] = replace(validation)
            return True

    async def close(self) -> None:
        return None
