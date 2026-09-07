from __future__ import annotations

import os
from datetime import UTC, datetime
from uuid import uuid4

import pytest
from sqlalchemy import delete
from sqlalchemy.ext.asyncio import create_async_engine

from atlas.core.audit import AuditRecord
from atlas.core.audit_ledger import AuditLedgerConflictError, PostgresDurableAuditLedger
from atlas.core.persistence.models import AuditLedgerHeadModel, AuditLedgerRecordModel


def _event(event_id: str, **overrides: object) -> AuditRecord:
    defaults: dict[str, object] = {
        "event_id": event_id,
        "event_type": "atlas.audit.ledger.append",
        "schema_version": "1.0",
        "producer": "test-producer",
        "producer_version": "0.0.0",
        "occurred_at": datetime.now(UTC),
        "correlation_id": "correlation.example",
        "subject_id": "subject.example",
        "actor_type": "human",
        "authentication_method": None,
        "assurance_level": None,
        "permission_id": None,
        "resource_type": None,
        "scope_reference": None,
        "decision_id": None,
        "outcome": "succeeded",
        "result_code": "example.succeeded",
    }
    defaults.update(overrides)
    return AuditRecord(**defaults)  # type: ignore[arg-type]


@pytest.mark.asyncio
async def test_live_postgres_audit_ledger_chains_appends_and_verifies_intact() -> None:
    database_url = os.getenv("ATLAS_TEST_POSTGRES_DSN")
    if not database_url:
        pytest.skip("ATLAS_TEST_POSTGRES_DSN is not configured")

    ledger_name = f"test.{uuid4().hex}"
    engine = create_async_engine(database_url, pool_pre_ping=True)
    ledger = PostgresDurableAuditLedger(engine=engine, ledger_name=ledger_name)
    try:
        first = await ledger.append(_event("evt_001"))
        second = await ledger.append(_event("evt_002"))
        assert first.sequence == 1
        assert second.sequence == 2
        assert second.previous_record_digest == first.record_digest

        # idempotent re-append of the identical event
        assert await ledger.append(_event("evt_001", occurred_at=first.event.occurred_at)) == first

        # conflicting re-append of the same event id is rejected
        with pytest.raises(AuditLedgerConflictError):
            await ledger.append(_event("evt_001", outcome="denied", result_code="example.denied"))

        page = await ledger.read_range(from_sequence=1, limit=10)
        assert [record.sequence for record in page] == [1, 2]

        report = await ledger.verify_integrity(at=datetime.now(UTC))
        assert report.is_intact
        assert report.records_checked == 2

        await ledger.record(_event("evt_via_record"))
        report_after_record = await ledger.verify_integrity(at=datetime.now(UTC))
        assert report_after_record.is_intact
        assert report_after_record.records_checked == 3
    finally:
        async with engine.begin() as connection:
            await connection.execute(
                delete(AuditLedgerRecordModel).where(
                    AuditLedgerRecordModel.ledger_name == ledger_name
                )
            )
            await connection.execute(
                delete(AuditLedgerHeadModel).where(AuditLedgerHeadModel.ledger_name == ledger_name)
            )
        await ledger.close()


@pytest.mark.asyncio
async def test_live_postgres_audit_ledger_serializes_concurrent_appends() -> None:
    import asyncio

    database_url = os.getenv("ATLAS_TEST_POSTGRES_DSN")
    if not database_url:
        pytest.skip("ATLAS_TEST_POSTGRES_DSN is not configured")

    ledger_name = f"test.{uuid4().hex}"
    engine = create_async_engine(database_url, pool_pre_ping=True)
    ledger = PostgresDurableAuditLedger(engine=engine, ledger_name=ledger_name)
    try:

        async def append_many(prefix: str, count: int) -> None:
            for index in range(count):
                await ledger.append(_event(f"evt_{prefix}_{index:04d}"))

        await asyncio.gather(
            append_many("a", 15),
            append_many("b", 15),
            append_many("c", 15),
        )
        report = await ledger.verify_integrity(at=datetime.now(UTC))
        assert report.is_intact
        assert report.records_checked == 45
    finally:
        async with engine.begin() as connection:
            await connection.execute(
                delete(AuditLedgerRecordModel).where(
                    AuditLedgerRecordModel.ledger_name == ledger_name
                )
            )
            await connection.execute(
                delete(AuditLedgerHeadModel).where(AuditLedgerHeadModel.ledger_name == ledger_name)
            )
        await ledger.close()
