from __future__ import annotations

import asyncio

from atlas.modules.connectors.domain.authority_behavior_validation import (
    ConnectorPackageAuthorityBehaviorValidation,
)


class InMemoryPackageAuthorityBehaviorValidationRepository:
    durable = False

    def __init__(self) -> None:
        self._records: dict[str, ConnectorPackageAuthorityBehaviorValidation] = {}
        self._lock = asyncio.Lock()

    async def get_by_id(
        self, *, validation_id: str
    ) -> ConnectorPackageAuthorityBehaviorValidation | None:
        return self._records.get(validation_id)

    async def get_by_source_validation(
        self, *, source_schema_semantics_validation_id: str
    ) -> ConnectorPackageAuthorityBehaviorValidation | None:
        return next(
            (
                item
                for item in self._records.values()
                if item.source_schema_semantics_validation_id
                == source_schema_semantics_validation_id
            ),
            None,
        )

    async def get_by_create_key(
        self, *, validated_by: str, idempotency_key: str
    ) -> ConnectorPackageAuthorityBehaviorValidation | None:
        return next(
            (
                item
                for item in self._records.values()
                if item.validated_by == validated_by and item.idempotency_key == idempotency_key
            ),
            None,
        )

    async def add(self, validation: ConnectorPackageAuthorityBehaviorValidation) -> bool:
        async with self._lock:
            if validation.validation_id in self._records:
                return False
            if any(
                item.source_schema_semantics_validation_id
                == validation.source_schema_semantics_validation_id
                or (
                    item.validated_by == validation.validated_by
                    and item.idempotency_key == validation.idempotency_key
                )
                for item in self._records.values()
            ):
                return False
            self._records[validation.validation_id] = validation
            return True

    async def close(self) -> None:
        return None
