from __future__ import annotations

from datetime import UTC, datetime

import pytest

from atlas.core.audit import AuditRecord
from atlas.core.audit_ledger import (
    GENESIS_DIGEST,
    AuditIntegrityFinding,
    AuditIntegrityFindingKind,
    AuditIntegrityReport,
    LedgerRecord,
    administrative_deletion_or_update_interface_is_exposed,
    ai_confidence_or_approval_permits_omission_of_audit_evidence,
    audit_can_be_disabled_by_feature_flag,
    audit_proves_that_an_external_system_reported_truthfully,
    compute_record_digest,
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


def test_audit_can_never_be_disabled_by_a_feature_flag() -> None:
    assert audit_can_be_disabled_by_feature_flag() is False


def test_administrative_deletion_or_update_interface_is_never_exposed() -> None:
    assert administrative_deletion_or_update_interface_is_exposed() is False


def test_ai_confidence_or_approval_never_permits_omission_of_audit_evidence() -> None:
    assert ai_confidence_or_approval_permits_omission_of_audit_evidence() is False


def test_audit_never_proves_an_external_system_reported_truthfully() -> None:
    assert audit_proves_that_an_external_system_reported_truthfully() is False


def test_compute_record_digest_is_deterministic() -> None:
    event = _event()
    first = compute_record_digest(
        previous_record_digest=GENESIS_DIGEST, event=event, sequence=1, accepted_at=NOW
    )
    second = compute_record_digest(
        previous_record_digest=GENESIS_DIGEST, event=event, sequence=1, accepted_at=NOW
    )
    assert first == second
    assert len(first) == 64


def test_compute_record_digest_changes_with_previous_digest() -> None:
    event = _event()
    first = compute_record_digest(
        previous_record_digest=GENESIS_DIGEST, event=event, sequence=1, accepted_at=NOW
    )
    second = compute_record_digest(
        previous_record_digest="1" * 64, event=event, sequence=1, accepted_at=NOW
    )
    assert first != second


def test_compute_record_digest_changes_with_event_content() -> None:
    first = compute_record_digest(
        previous_record_digest=GENESIS_DIGEST, event=_event(), sequence=1, accepted_at=NOW
    )
    second = compute_record_digest(
        previous_record_digest=GENESIS_DIGEST,
        event=_event(outcome="denied", result_code="example.denied"),
        sequence=1,
        accepted_at=NOW,
    )
    assert first != second


def test_ledger_record_requires_positive_sequence() -> None:
    digest = compute_record_digest(
        previous_record_digest=GENESIS_DIGEST, event=_event(), sequence=1, accepted_at=NOW
    )
    with pytest.raises(ValueError, match="positive"):
        LedgerRecord(
            sequence=0,
            event=_event(),
            accepted_at=NOW,
            previous_record_digest=GENESIS_DIGEST,
            record_digest=digest,
        )


def test_ledger_record_requires_timezone_aware_acceptance_time() -> None:
    digest = compute_record_digest(
        previous_record_digest=GENESIS_DIGEST, event=_event(), sequence=1, accepted_at=NOW
    )
    with pytest.raises(ValueError, match="timezone-aware"):
        LedgerRecord(
            sequence=1,
            event=_event(),
            accepted_at=datetime(2026, 9, 7, 12, 0),
            previous_record_digest=GENESIS_DIGEST,
            record_digest=digest,
        )


def test_ledger_record_requires_valid_sha256_digests() -> None:
    with pytest.raises(ValueError, match="SHA-256 hex digest"):
        LedgerRecord(
            sequence=1,
            event=_event(),
            accepted_at=NOW,
            previous_record_digest="not-a-digest",
            record_digest=GENESIS_DIGEST,
        )


def test_ledger_record_builds_with_valid_digests() -> None:
    digest = compute_record_digest(
        previous_record_digest=GENESIS_DIGEST, event=_event(), sequence=1, accepted_at=NOW
    )
    record = LedgerRecord(
        sequence=1,
        event=_event(),
        accepted_at=NOW,
        previous_record_digest=GENESIS_DIGEST,
        record_digest=digest,
    )
    assert record.sequence == 1


def test_integrity_finding_requires_positive_sequence_and_detail() -> None:
    with pytest.raises(ValueError, match="positive"):
        AuditIntegrityFinding(kind=AuditIntegrityFindingKind.SEQUENCE_GAP, sequence=0, detail="x")
    with pytest.raises(ValueError, match="detail"):
        AuditIntegrityFinding(kind=AuditIntegrityFindingKind.SEQUENCE_GAP, sequence=1, detail="  ")


def test_integrity_report_is_intact_with_no_findings() -> None:
    report = AuditIntegrityReport(
        verified_at=NOW,
        first_sequence=1,
        last_sequence=10,
        records_checked=10,
        findings=(),
    )
    assert report.is_intact is True


def test_integrity_report_is_not_intact_with_findings() -> None:
    finding = AuditIntegrityFinding(
        kind=AuditIntegrityFindingKind.CHAIN_MISMATCH, sequence=5, detail="digest mismatch"
    )
    report = AuditIntegrityReport(
        verified_at=NOW,
        first_sequence=1,
        last_sequence=10,
        records_checked=10,
        findings=(finding,),
    )
    assert report.is_intact is False


def test_integrity_report_requires_valid_sequence_range() -> None:
    with pytest.raises(ValueError, match="valid sequence range"):
        AuditIntegrityReport(
            verified_at=NOW,
            first_sequence=10,
            last_sequence=1,
            records_checked=0,
            findings=(),
        )
