from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest

from atlas.core.audit import AuditRecord
from atlas.core.audit_ledger import (
    GENESIS_DIGEST,
    AuditIntegrityFindingKind,
    AuditLedgerConflictError,
    InMemoryDurableAuditLedger,
)

NOW = datetime(2026, 9, 7, 12, 0, tzinfo=UTC)


def _event(**overrides: object) -> AuditRecord:
    defaults: dict[str, object] = {
        "event_id": "evt_example-001",
        "event_type": "atlas.audit.ledger.append",
        "schema_version": "1.0",
        "producer": "test-producer",
        "producer_version": "0.0.0",
        "occurred_at": NOW,
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
async def test_first_append_chains_from_the_genesis_digest() -> None:
    ledger = InMemoryDurableAuditLedger()
    record = await ledger.append(_event())
    assert record.sequence == 1
    assert record.previous_record_digest == GENESIS_DIGEST


@pytest.mark.asyncio
async def test_successive_appends_chain_sequence_and_digest() -> None:
    ledger = InMemoryDurableAuditLedger()
    first = await ledger.append(_event(event_id="evt_001"))
    second = await ledger.append(_event(event_id="evt_002"))
    assert second.sequence == 2
    assert second.previous_record_digest == first.record_digest


@pytest.mark.asyncio
async def test_re_appending_identical_event_is_idempotent() -> None:
    ledger = InMemoryDurableAuditLedger()
    first = await ledger.append(_event())
    second = await ledger.append(_event())
    assert first == second
    report = await ledger.verify_integrity(at=NOW)
    assert report.records_checked == 1


@pytest.mark.asyncio
async def test_re_appending_conflicting_event_raises() -> None:
    ledger = InMemoryDurableAuditLedger()
    await ledger.append(_event())
    with pytest.raises(AuditLedgerConflictError):
        await ledger.append(_event(outcome="denied", result_code="example.denied"))


@pytest.mark.asyncio
async def test_read_range_returns_records_from_the_requested_sequence() -> None:
    ledger = InMemoryDurableAuditLedger()
    for index in range(5):
        await ledger.append(_event(event_id=f"evt_{index:03d}"))
    page = await ledger.read_range(from_sequence=3, limit=10)
    assert [record.sequence for record in page] == [3, 4, 5]


@pytest.mark.asyncio
async def test_read_range_respects_limit() -> None:
    ledger = InMemoryDurableAuditLedger()
    for index in range(5):
        await ledger.append(_event(event_id=f"evt_{index:03d}"))
    page = await ledger.read_range(from_sequence=1, limit=2)
    assert [record.sequence for record in page] == [1, 2]


@pytest.mark.asyncio
async def test_verify_integrity_on_empty_ledger_is_intact() -> None:
    ledger = InMemoryDurableAuditLedger()
    report = await ledger.verify_integrity(at=NOW)
    assert report.is_intact is True
    assert report.records_checked == 0


@pytest.mark.asyncio
async def test_verify_integrity_on_untampered_chain_is_intact() -> None:
    ledger = InMemoryDurableAuditLedger()
    for index in range(4):
        await ledger.append(_event(event_id=f"evt_{index:03d}"))
    report = await ledger.verify_integrity(at=NOW)
    assert report.is_intact is True
    assert report.records_checked == 4
    assert report.first_sequence == 1
    assert report.last_sequence == 4


@pytest.mark.asyncio
async def test_verify_integrity_detects_a_forged_chain_link() -> None:
    ledger = InMemoryDurableAuditLedger()
    await ledger.append(_event(event_id="evt_001"))
    await ledger.append(_event(event_id="evt_002"))
    # Simulate tampering: splice in a record whose previous-digest no longer matches.
    tampered = ledger._records[1]
    ledger._records[1] = type(tampered)(
        sequence=tampered.sequence,
        event=tampered.event,
        accepted_at=tampered.accepted_at,
        previous_record_digest="1" * 64,
        record_digest=tampered.record_digest,
    )
    report = await ledger.verify_integrity(at=NOW)
    assert report.is_intact is False
    assert any(
        finding.kind is AuditIntegrityFindingKind.CHAIN_MISMATCH for finding in report.findings
    )


@pytest.mark.asyncio
async def test_verify_integrity_detects_a_clock_anomaly() -> None:
    ledger = InMemoryDurableAuditLedger()
    await ledger.append(_event(event_id="evt_001", occurred_at=NOW))
    earlier = NOW - timedelta(hours=1)
    await ledger.append(_event(event_id="evt_002", occurred_at=earlier))
    report = await ledger.verify_integrity(at=NOW)
    assert report.is_intact is False
    assert any(
        finding.kind is AuditIntegrityFindingKind.CLOCK_ANOMALY for finding in report.findings
    )
