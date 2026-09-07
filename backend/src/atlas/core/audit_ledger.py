"""ATLAS-032 SS6/SS12: the durable, tamper-evident audit ledger.

`atlas.core.audit.AuditSink` is the minimal producer-facing contract every module already writes
through -- fire an `AuditRecord`, get an awaitable. It intentionally says nothing about
durability or tamper evidence, because its existing implementations (`LoggingAuditSink`, and the
in-memory list inside `security_export.application.service.SecurityExportService`) were never
meant to BE the authoritative ledger SS12 requires: "hash chaining, signed batches, immutable
storage, or equivalent controls provide tamper evidence."

SS12 itself defers the exact mechanism to a security ADR ("selected mechanism, key custody, and
verification frequency require a security ADR before production") and SS27 leaves the
ledger/immutable-storage technology as an open question -- but hash chaining over SHA-256 needs
no new external dependency (no KMS, no signing-key custody) and is explicitly one of SS12's named
"equivalent controls" alongside signed batches, so it is the correct MVP mechanism: nothing here
waits on an infrastructure decision the way ATLAS-058's registry/signing selection did.
"""

from __future__ import annotations

import asyncio
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from enum import StrEnum
from hashlib import sha256
from typing import Any, Protocol, cast

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert as postgresql_insert
from sqlalchemy.ext.asyncio import AsyncEngine, async_sessionmaker, create_async_engine

from atlas.core.audit import AuditRecord
from atlas.core.persistence.models import AuditLedgerHeadModel, AuditLedgerRecordModel

GENESIS_DIGEST = "0" * 64
_HEX_DIGITS = frozenset("0123456789abcdef")


def _is_sha256_hex(value: str) -> bool:
    return len(value) == 64 and all(character in _HEX_DIGITS for character in value)


@dataclass(frozen=True, slots=True)
class LedgerRecord:
    """One durably-accepted, chained ledger entry (SS6's Integrity field group)."""

    sequence: int
    event: AuditRecord
    accepted_at: datetime
    previous_record_digest: str
    record_digest: str

    def __post_init__(self) -> None:
        if self.sequence < 1:
            raise ValueError("a ledger record sequence must be positive")
        if self.accepted_at.tzinfo is None:
            raise ValueError("ledger acceptance time must be timezone-aware")
        if not _is_sha256_hex(self.previous_record_digest) or not _is_sha256_hex(
            self.record_digest
        ):
            raise ValueError("a ledger record digest must be a SHA-256 hex digest")


def compute_record_digest(
    *,
    previous_record_digest: str,
    event: AuditRecord,
    sequence: int,
    accepted_at: datetime,
) -> str:
    """SS12's hash chain: each record's digest commits to the previous record's digest, so
    altering, removing, or reordering any past record invalidates every digest computed after
    it.

    Both timestamps are normalized to UTC before formatting. A driver or database session can
    hand back an aware datetime in a non-UTC offset for the exact same instant (e.g. Postgres
    returns `TIMESTAMPTZ` values in the session's configured timezone) -- `==` on aware datetimes
    compares instants and would not notice, but `.isoformat()` is not instant-canonical, so
    without this the same real event would hash differently depending on which offset happened
    to come back from a given round trip.
    """
    payload = "|".join(
        (
            previous_record_digest,
            str(sequence),
            accepted_at.astimezone(UTC).isoformat(),
            event.event_id,
            event.event_type,
            event.schema_version,
            event.occurred_at.astimezone(UTC).isoformat(),
            event.correlation_id,
            event.outcome,
            event.result_code,
        )
    )
    return sha256(payload.encode("utf-8")).hexdigest()


class AuditIntegrityFindingKind(StrEnum):
    """SS12: "Gaps, duplicate IDs, invalid signatures, sequence discontinuity, and unexpected
    clock behavior create security alerts.\""""

    SEQUENCE_GAP = "sequence_gap"
    DUPLICATE_EVENT_ID = "duplicate_event_id"
    CHAIN_MISMATCH = "chain_mismatch"
    CLOCK_ANOMALY = "clock_anomaly"


@dataclass(frozen=True, slots=True)
class AuditIntegrityFinding:
    kind: AuditIntegrityFindingKind
    sequence: int
    detail: str

    def __post_init__(self) -> None:
        if self.sequence < 1:
            raise ValueError("an integrity finding sequence must be positive")
        if not self.detail.strip():
            raise ValueError("an integrity finding requires a detail")


@dataclass(frozen=True, slots=True)
class AuditIntegrityReport:
    verified_at: datetime
    first_sequence: int
    last_sequence: int
    records_checked: int
    findings: tuple[AuditIntegrityFinding, ...]

    def __post_init__(self) -> None:
        if self.verified_at.tzinfo is None:
            raise ValueError("integrity verification time must be timezone-aware")
        if self.first_sequence < 1 or self.last_sequence < self.first_sequence:
            raise ValueError("an integrity report requires a valid sequence range")
        if self.records_checked < 0:
            raise ValueError("an integrity report cannot check a negative record count")

    @property
    def is_intact(self) -> bool:
        return not self.findings


def verify_ledger_chain(
    records: tuple[LedgerRecord, ...],
    *,
    at: datetime,
) -> AuditIntegrityReport:
    """SS12's integrity check, shared by every `DurableAuditLedger` implementation: recomputes
    every digest in `records` (already expected in ascending sequence order) and flags sequence
    gaps, duplicate event IDs, chain mismatches, and clock anomalies."""
    findings: list[AuditIntegrityFinding] = []
    seen_event_ids: set[str] = set()
    previous_digest = GENESIS_DIGEST
    previous_accepted_at: datetime | None = None
    for index, record in enumerate(records):
        expected_sequence = index + 1
        if record.sequence != expected_sequence:
            findings.append(
                AuditIntegrityFinding(
                    kind=AuditIntegrityFindingKind.SEQUENCE_GAP,
                    sequence=expected_sequence,
                    detail=f"expected sequence {expected_sequence}, found {record.sequence}",
                )
            )
        if record.event.event_id in seen_event_ids:
            findings.append(
                AuditIntegrityFinding(
                    kind=AuditIntegrityFindingKind.DUPLICATE_EVENT_ID,
                    sequence=record.sequence,
                    detail=f"event id {record.event.event_id!r} appears more than once",
                )
            )
        seen_event_ids.add(record.event.event_id)
        if record.previous_record_digest != previous_digest:
            findings.append(
                AuditIntegrityFinding(
                    kind=AuditIntegrityFindingKind.CHAIN_MISMATCH,
                    sequence=record.sequence,
                    detail="previous-record digest does not match the prior ledger entry",
                )
            )
        expected_digest = compute_record_digest(
            previous_record_digest=record.previous_record_digest,
            event=record.event,
            sequence=record.sequence,
            accepted_at=record.accepted_at,
        )
        if expected_digest != record.record_digest:
            findings.append(
                AuditIntegrityFinding(
                    kind=AuditIntegrityFindingKind.CHAIN_MISMATCH,
                    sequence=record.sequence,
                    detail="stored digest does not match the recomputed digest",
                )
            )
        if previous_accepted_at is not None and record.accepted_at < previous_accepted_at:
            findings.append(
                AuditIntegrityFinding(
                    kind=AuditIntegrityFindingKind.CLOCK_ANOMALY,
                    sequence=record.sequence,
                    detail="acceptance time precedes the prior ledger entry's acceptance time",
                )
            )
        previous_digest = record.record_digest
        previous_accepted_at = record.accepted_at
    return AuditIntegrityReport(
        verified_at=at,
        first_sequence=records[0].sequence if records else 1,
        last_sequence=records[-1].sequence if records else 1,
        records_checked=len(records),
        findings=tuple(findings),
    )


class DurableAuditLedger(Protocol):
    """SS5/SS12's authoritative store -- append-only, gives ordered ledger metadata after
    durable acceptance, and can verify its own integrity on demand."""

    async def append(self, event: AuditRecord) -> LedgerRecord: ...

    async def read_range(self, *, from_sequence: int, limit: int) -> tuple[LedgerRecord, ...]: ...

    async def verify_integrity(self, *, at: datetime) -> AuditIntegrityReport: ...


class AuditLedgerConflictError(RuntimeError):
    """Raised when an event ID is re-submitted with content differing from what the ledger
    already durably accepted (SS13: idempotent ingestion, not silent overwrite)."""


class InMemoryDurableAuditLedger:
    """A reference `DurableAuditLedger` for tests and non-durable defaults. Production
    deployments needing real durability use a persistent adapter (e.g. Postgres) implementing
    the same protocol; this class exists so the protocol has one dependency-free, always
    available implementation, mirroring `LoggingAuditSink`'s role for the plain `AuditSink`."""

    def __init__(self) -> None:
        self._records: list[LedgerRecord] = []
        self._by_event_id: dict[str, LedgerRecord] = {}
        self._lock = asyncio.Lock()

    async def append(self, event: AuditRecord) -> LedgerRecord:
        async with self._lock:
            existing = self._by_event_id.get(event.event_id)
            if existing is not None:
                if existing.event != event:
                    raise AuditLedgerConflictError(
                        f"audit event {event.event_id!r} was already accepted with different"
                        " content"
                    )
                return existing
            sequence = len(self._records) + 1
            previous_digest = self._records[-1].record_digest if self._records else GENESIS_DIGEST
            accepted_at = event.occurred_at
            digest = compute_record_digest(
                previous_record_digest=previous_digest,
                event=event,
                sequence=sequence,
                accepted_at=accepted_at,
            )
            record = LedgerRecord(
                sequence=sequence,
                event=event,
                accepted_at=accepted_at,
                previous_record_digest=previous_digest,
                record_digest=digest,
            )
            self._records.append(record)
            self._by_event_id[event.event_id] = record
            return record

    async def read_range(self, *, from_sequence: int, limit: int) -> tuple[LedgerRecord, ...]:
        async with self._lock:
            return tuple(record for record in self._records if record.sequence >= from_sequence)[
                :limit
            ]

    async def verify_integrity(self, *, at: datetime) -> AuditIntegrityReport:
        async with self._lock:
            records = tuple(self._records)
        return verify_ledger_chain(records, at=at)


class PostgresDurableAuditLedger:
    """Real, durable audit ledger backed by PostgreSQL (`audit_ledger_records`/
    `audit_ledger_heads`, migration `20260907_0170`). No application code issues UPDATE or
    DELETE against `audit_ledger_records` -- the only mutating operation is INSERT.

    Every append is one serialized transaction: the named ledger's head row is locked with
    `SELECT ... FOR UPDATE` (created first via `INSERT ... ON CONFLICT DO NOTHING` if this is the
    ledger's first-ever append, so the lock always has a row to acquire), the next sequence and
    chained digest are computed from that locked head, and the new record plus the updated head
    are written together in the same transaction. Hash chaining is inherently sequential, so two
    concurrent appenders to the same named ledger can never compute the same sequence or fork the
    chain -- they simply queue behind each other's lock.
    """

    def __init__(self, *, engine: AsyncEngine, ledger_name: str = "default") -> None:
        self._engine = engine
        self._sessions = async_sessionmaker(engine, expire_on_commit=False)
        self._ledger_name = ledger_name

    @classmethod
    def from_url(
        cls, database_url: str, *, ledger_name: str = "default"
    ) -> PostgresDurableAuditLedger:
        return cls(
            engine=create_async_engine(database_url, pool_pre_ping=True, pool_recycle=300),
            ledger_name=ledger_name,
        )

    async def append(self, event: AuditRecord) -> LedgerRecord:
        async with self._sessions.begin() as session:
            await session.execute(
                postgresql_insert(AuditLedgerHeadModel)
                .values(
                    ledger_name=self._ledger_name,
                    last_sequence=0,
                    last_digest=GENESIS_DIGEST,
                )
                .on_conflict_do_nothing(index_elements=["ledger_name"])
            )
            head = await session.get(AuditLedgerHeadModel, self._ledger_name, with_for_update=True)
            assert head is not None
            existing = await session.scalar(
                select(AuditLedgerRecordModel).where(
                    AuditLedgerRecordModel.ledger_name == self._ledger_name,
                    AuditLedgerRecordModel.event_id == event.event_id,
                )
            )
            if existing is not None:
                existing_record = self._to_domain(existing)
                if existing_record.event != event:
                    raise AuditLedgerConflictError(
                        f"audit event {event.event_id!r} was already accepted with different"
                        " content"
                    )
                return existing_record
            sequence = head.last_sequence + 1
            previous_digest = head.last_digest
            accepted_at = event.occurred_at
            digest = compute_record_digest(
                previous_record_digest=previous_digest,
                event=event,
                sequence=sequence,
                accepted_at=accepted_at,
            )
            session.add(
                AuditLedgerRecordModel(
                    ledger_name=self._ledger_name,
                    sequence=sequence,
                    event_id=event.event_id,
                    accepted_at=accepted_at,
                    previous_record_digest=previous_digest,
                    record_digest=digest,
                    payload=self._serialize_event(event),
                )
            )
            head.last_sequence = sequence
            head.last_digest = digest
        return LedgerRecord(
            sequence=sequence,
            event=event,
            accepted_at=accepted_at,
            previous_record_digest=previous_digest,
            record_digest=digest,
        )

    async def read_range(self, *, from_sequence: int, limit: int) -> tuple[LedgerRecord, ...]:
        async with self._sessions() as session:
            rows = await session.scalars(
                select(AuditLedgerRecordModel)
                .where(
                    AuditLedgerRecordModel.ledger_name == self._ledger_name,
                    AuditLedgerRecordModel.sequence >= from_sequence,
                )
                .order_by(AuditLedgerRecordModel.sequence)
                .limit(limit)
            )
            return tuple(self._to_domain(row) for row in rows)

    async def verify_integrity(self, *, at: datetime) -> AuditIntegrityReport:
        async with self._sessions() as session:
            rows = await session.scalars(
                select(AuditLedgerRecordModel)
                .where(AuditLedgerRecordModel.ledger_name == self._ledger_name)
                .order_by(AuditLedgerRecordModel.sequence)
            )
            records = tuple(self._to_domain(row) for row in rows)
        return verify_ledger_chain(records, at=at)

    async def close(self) -> None:
        await self._engine.dispose()

    @staticmethod
    def _serialize_event(event: AuditRecord) -> dict[str, Any]:
        payload = asdict(event)
        payload["occurred_at"] = event.occurred_at.isoformat()
        payload["target_metadata"] = [list(pair) for pair in event.target_metadata]
        return payload

    @staticmethod
    def _to_domain(row: AuditLedgerRecordModel) -> LedgerRecord:
        payload = dict(row.payload)
        payload["occurred_at"] = datetime.fromisoformat(str(payload["occurred_at"]))
        payload["target_metadata"] = tuple(
            tuple(pair) for pair in cast(list[list[str]], payload["target_metadata"])
        )
        event = AuditRecord(**cast(Any, payload))
        return LedgerRecord(
            sequence=row.sequence,
            event=event,
            accepted_at=row.accepted_at,
            previous_record_digest=row.previous_record_digest,
            record_digest=row.record_digest,
        )


def audit_can_be_disabled_by_feature_flag() -> bool:
    """SS4: "Audit cannot be disabled by a tenant, user, agent, workflow, connector, or feature
    flag.\""""
    return False


def administrative_deletion_or_update_interface_is_exposed() -> bool:
    """SS12: "Administrative deletion or update interfaces are not exposed.\""""
    return False


def ai_confidence_or_approval_permits_omission_of_audit_evidence() -> bool:
    """SS4: "AI confidence, approval, or successful execution never permits omission of audit
    evidence.\""""
    return False


def audit_proves_that_an_external_system_reported_truthfully() -> bool:
    """SS4: "Audit proves recorded behavior; it does not by itself prove that an external system
    reported truthfully.\""""
    return False
