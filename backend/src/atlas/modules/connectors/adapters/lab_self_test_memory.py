from __future__ import annotations

import asyncio
from collections.abc import Callable
from datetime import UTC, datetime, timedelta
from uuid import uuid4

from atlas.modules.connectors.domain.lab_self_test import (
    ConnectorLabPlan,
    ConnectorPackageLabSelfTest,
    LabExecutionLease,
)


class InMemoryPackageLabSelfTestRepository:
    def __init__(self) -> None:
        self._records: dict[str, ConnectorPackageLabSelfTest] = {}
        self._source_index: dict[str, str] = {}
        self._create_index: dict[tuple[str, str], str] = {}
        self._lock = asyncio.Lock()

    @property
    def durable(self) -> bool:
        return False

    async def get_by_id(self, *, self_test_id: str) -> ConnectorPackageLabSelfTest | None:
        return self._records.get(self_test_id)

    async def get_by_source_validation(
        self, *, source_runner_validation_id: str
    ) -> ConnectorPackageLabSelfTest | None:
        self_test_id = self._source_index.get(source_runner_validation_id)
        return self._records.get(self_test_id) if self_test_id else None

    async def get_by_create_key(
        self, *, validated_by: str, idempotency_key: str
    ) -> ConnectorPackageLabSelfTest | None:
        self_test_id = self._create_index.get((validated_by, idempotency_key))
        return self._records.get(self_test_id) if self_test_id else None

    async def add(self, self_test: ConnectorPackageLabSelfTest) -> bool:
        async with self._lock:
            create_key = (self_test.validated_by, self_test.idempotency_key)
            if (
                self_test.self_test_id in self._records
                or self_test.source_runner_validation_id in self._source_index
                or create_key in self._create_index
            ):
                return False
            self._records[self_test.self_test_id] = self_test
            self._source_index[self_test.source_runner_validation_id] = self_test.self_test_id
            self._create_index[create_key] = self_test.self_test_id
            return True

    async def close(self) -> None:
        return None


class InMemoryConnectorLabPlanSource:
    def __init__(self, plans: tuple[ConnectorLabPlan, ...] = ()) -> None:
        self._records = {item.plan_id: item for item in plans}

    async def get_by_id(self, *, plan_id: str) -> ConnectorLabPlan | None:
        return self._records.get(plan_id)

    async def add(self, plan: ConnectorLabPlan) -> bool:
        if plan.plan_id in self._records:
            return False
        self._records[plan.plan_id] = plan
        return True


class InMemoryLabAccessBroker:
    def __init__(
        self,
        *,
        clock: Callable[[], datetime] | None = None,
        lease_seconds: int = 60,
    ) -> None:
        if lease_seconds <= 0:
            raise ValueError("lease_seconds must be positive")
        self._active: dict[str, LabExecutionLease] = {}
        self._lock = asyncio.Lock()
        self._clock = clock or (lambda: datetime.now(UTC))
        self._lease_seconds = lease_seconds

    async def issue(self, *, plan: ConnectorLabPlan) -> LabExecutionLease:
        now = self._clock()
        expires_at = min(plan.expires_at, now + timedelta(seconds=self._lease_seconds))
        if expires_at <= now:
            raise RuntimeError("lab plan expired")
        nonce = uuid4().hex
        lease = LabExecutionLease(
            lease_id=f"lab-lease.{nonce}",
            plan_id=plan.plan_id,
            credential_handle=f"credential-handle.{nonce}",
            issued_at=now,
            expires_at=expires_at,
        )
        async with self._lock:
            self._active[lease.lease_id] = lease
        return lease

    async def release(self, *, lease: LabExecutionLease) -> bool:
        async with self._lock:
            return self._active.pop(lease.lease_id, None) is not None

    @property
    def active_count(self) -> int:
        return len(self._active)
