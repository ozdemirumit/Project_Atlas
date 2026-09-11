"""HTTP-level wiring tests for `POST /api/v1/platform/audit-ledger/integrity-verifications`
(docs/032_Audit.md SS12/S22's on-demand integrity-verification half -- see
`atlas.core.audit_ledger`'s module docstring for the full wiring status).

Proves: the endpoint is reachable and returns a genuine `is_intact: true` report for a clean,
real ledger with real appended events; a real, directly-corrupted stored ledger record produces a
real report with real findings and `is_intact: false`; every run emits a real `AuditRecord`
through the app's `AuditSink` (S22's "last successful check" observability); and the established
two-stage denial pattern (true 401 with dev-identity disabled, true 403 with a real login lacking
the permission) is honored from the start.
"""

from __future__ import annotations

import asyncio
from datetime import UTC, datetime

from fastapi.testclient import TestClient
from test_browser_sessions import settings

from atlas.api.app import create_app
from atlas.core.audit import AuditRecord
from atlas.core.audit_ledger import InMemoryDurableAuditLedger


class CollectingAuditSink:
    def __init__(self) -> None:
        self.records: list[AuditRecord] = []

    async def record(self, event: AuditRecord) -> None:
        self.records.append(event)


def _event(**overrides: object) -> AuditRecord:
    defaults: dict[str, object] = {
        "event_id": "evt_ledger-integrity-example-001",
        "event_type": "atlas.audit.ledger.append",
        "schema_version": "1.0",
        "producer": "test-producer",
        "producer_version": "0.0.0",
        "occurred_at": datetime(2026, 9, 11, 11, 0, tzinfo=UTC),
        "correlation_id": "correlation.ledger-integrity-example",
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


def _build_clean_ledger(count: int) -> InMemoryDurableAuditLedger:
    ledger = InMemoryDurableAuditLedger()
    for index in range(count):
        asyncio.run(ledger.append(_event(event_id=f"evt_ledger-integrity-{index:03d}")))
    return ledger


def login_dev(client: TestClient) -> str:
    response = client.post(
        "/api/v1/authentication/sessions",
        json={"username": "atlas-demo", "password": "local-demo"},
    )
    assert response.status_code == 201, response.text
    return str(response.headers["X-CSRF-Token"])


def test_audit_ledger_integrity_verification_reachable_and_intact_for_clean_ledger() -> None:
    ledger = _build_clean_ledger(4)
    sink = CollectingAuditSink()
    app = create_app(settings(), audit_ledger=ledger, audit_sink=sink)
    with TestClient(app) as client:
        csrf = login_dev(client)
        response = client.post(
            "/api/v1/platform/audit-ledger/integrity-verifications",
            headers={"X-CSRF-Token": csrf, "X-Correlation-ID": "cor_ledger_integrity_clean"},
        )

    assert response.status_code == 200, response.text
    assert response.headers["Cache-Control"] == "no-store"
    data = response.json()["data"]
    assert data["is_intact"] is True
    assert data["records_checked"] == 4
    assert data["first_sequence"] == 1
    assert data["last_sequence"] == 4
    assert data["findings"] == []

    verification_events = [
        event for event in sink.records if event.event_type == "audit.ledger-integrity-verification"
    ]
    assert len(verification_events) == 1
    emitted = verification_events[0]
    assert emitted.outcome == "succeeded"
    assert emitted.result_code == "ledger_intact"
    assert emitted.correlation_id == "cor_ledger_integrity_clean"
    assert dict(emitted.target_metadata)["records_checked"] == "4"


def test_audit_ledger_integrity_verification_detects_real_tampering() -> None:
    ledger = _build_clean_ledger(2)
    tampered = ledger._records[1]
    ledger._records[1] = type(tampered)(
        sequence=tampered.sequence,
        event=tampered.event,
        accepted_at=tampered.accepted_at,
        previous_record_digest="1" * 64,
        record_digest=tampered.record_digest,
    )
    sink = CollectingAuditSink()
    app = create_app(settings(), audit_ledger=ledger, audit_sink=sink)
    with TestClient(app) as client:
        csrf = login_dev(client)
        response = client.post(
            "/api/v1/platform/audit-ledger/integrity-verifications",
            headers={"X-CSRF-Token": csrf, "X-Correlation-ID": "cor_ledger_integrity_tampered"},
        )

    assert response.status_code == 200, response.text
    data = response.json()["data"]
    assert data["is_intact"] is False
    assert data["records_checked"] == 2
    assert any(finding["kind"] == "chain_mismatch" for finding in data["findings"])

    verification_events = [
        event for event in sink.records if event.event_type == "audit.ledger-integrity-verification"
    ]
    assert len(verification_events) == 1
    emitted = verification_events[0]
    assert emitted.outcome == "failed"
    assert emitted.result_code == "ledger_findings_detected"
    assert dict(emitted.target_metadata)["findings_count"] != "0"


def test_audit_ledger_integrity_verification_requires_authentication() -> None:
    app = create_app(settings(development_identity_enabled=False))
    with TestClient(app) as client:
        response = client.post("/api/v1/platform/audit-ledger/integrity-verifications")

    assert response.status_code == 401
    assert response.json()["code"] == "authentication_required"


def test_audit_ledger_integrity_verification_requires_permission() -> None:
    app = create_app(settings(development_role_ids=()))
    with TestClient(app) as client:
        csrf = login_dev(client)
        response = client.post(
            "/api/v1/platform/audit-ledger/integrity-verifications",
            headers={"X-CSRF-Token": csrf},
        )

    assert response.status_code == 403
    assert response.json()["code"] == "authorization_denied"
