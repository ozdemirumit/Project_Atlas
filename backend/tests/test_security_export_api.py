from __future__ import annotations

from dataclasses import replace
from datetime import UTC, datetime, timedelta

import pytest
from fastapi.testclient import TestClient

from atlas.api.app import create_app
from atlas.core.audit import AuditRecord
from atlas.core.config import Settings
from atlas.modules.security_export.adapters.synthetic import (
    SyntheticTlsSyslogTransport,
    build_synthetic_syslog_destinations,
)
from atlas.modules.security_export.application.service import (
    SecurityExportAccessContext,
    SecurityExportOperationsError,
    SecurityExportService,
)
from atlas.modules.security_export.domain.models import DeliveryState

NOW = datetime(2026, 8, 4, 12, 0, tzinfo=UTC)


class CollectingAuditSink:
    def __init__(self) -> None:
        self.records: list[AuditRecord] = []

    async def record(self, event: AuditRecord) -> None:
        self.records.append(event)


class OverviewAuditFailingSink(CollectingAuditSink):
    async def record(self, event: AuditRecord) -> None:
        if event.event_type == "atlas.security_export.overview.read":
            raise RuntimeError("required audit unavailable")
        await super().record(event)


def settings(**overrides: object) -> Settings:
    values: dict[str, object] = {
        "environment": "test",
        "development_identity_enabled": True,
    }
    values.update(overrides)
    return Settings(**values)  # type: ignore[arg-type]


def context(**overrides: object) -> SecurityExportAccessContext:
    values: dict[str, object] = {
        "subject_id": "subject.development.operator",
        "actor_type": "human",
        "authentication_method": "development",
        "assurance_level": "development",
        "organization_id": "organization.development",
        "environment_id": "environment.test",
        "site_id": "site.local",
        "resource_id": "resource.security-export.synthetic",
        "correlation_id": "cor_security_export",
        "decision_id": "dec_security_export",
        "requested_at": NOW,
    }
    values.update(overrides)
    return SecurityExportAccessContext(**values)  # type: ignore[arg-type]


def audit_record(**overrides: object) -> AuditRecord:
    values: dict[str, object] = {
        "event_id": "evt_security_export_test",
        "event_type": "atlas.authorization.access.denied",
        "schema_version": "1.0",
        "producer": "project-atlas-api",
        "producer_version": "0.1.0",
        "occurred_at": NOW,
        "correlation_id": "cor_security_export",
        "subject_id": "subject.operator",
        "actor_type": "human",
        "authentication_method": "development",
        "assurance_level": "development",
        "permission_id": "storage.overview.read",
        "resource_type": "resource.storage",
        "scope_reference": "organization.development/environment.test/site.local",
        "decision_id": "dec_security_export",
        "outcome": "denied",
        "result_code": "no_matching_assignment",
    }
    values.update(overrides)
    return AuditRecord(**values)  # type: ignore[arg-type]


def service(
    *,
    delegate: CollectingAuditSink | None = None,
    transport: SyntheticTlsSyslogTransport | None = None,
    certificate_not_after: datetime | None = None,
    max_queue_records: int | None = None,
    max_attempts: int | None = None,
) -> tuple[SecurityExportService, CollectingAuditSink, SyntheticTlsSyslogTransport]:
    sink = delegate or CollectingAuditSink()
    resolved_transport = transport or SyntheticTlsSyslogTransport()
    destination = build_synthetic_syslog_destinations()[0]
    destination = replace(
        destination,
        certificate_not_after=certificate_not_after or destination.certificate_not_after,
        max_queue_records=max_queue_records or destination.max_queue_records,
        max_attempts=max_attempts or destination.max_attempts,
    )
    return (
        SecurityExportService(
            delegate=sink,
            destinations=(destination,),
            transport=resolved_transport,
            environment_id="environment.test",
            site_id="site.local",
        ),
        sink,
        resolved_transport,
    )


def test_security_export_overview_requires_authentication() -> None:
    with TestClient(create_app(Settings(environment="test"))) as client:
        response = client.get("/api/v1/security-export/overview")

    assert response.status_code == 401
    assert response.json()["code"] == "authentication_required"


def test_security_export_overview_requires_exact_assignment() -> None:
    with TestClient(
        create_app(settings(development_role_ids=()), audit_sink=CollectingAuditSink())
    ) as client:
        response = client.get("/api/v1/security-export/overview")

    assert response.status_code == 403
    assert response.json()["code"] == "authorization_denied"
    assert "security-export" not in response.json()["detail"].lower()


def test_overview_exposes_tls_health_preview_and_explicit_limitations() -> None:
    with TestClient(create_app(settings(), audit_sink=CollectingAuditSink())) as client:
        response = client.get(
            "/api/v1/security-export/overview",
            headers={"X-Correlation-ID": "cor_export_overview"},
        )

    assert response.status_code == 200
    payload = response.json()
    data = payload["data"]
    destination = data["destinations"][0]
    health = data["health"][0]
    preview = data["preview_message"]
    assert payload["meta"]["correlation_id"] == "cor_export_overview"
    assert destination["transport"] == "tls"
    assert destination["tls_server_authentication"] is True
    assert destination["tls_hostname_validation"] is True
    assert health["siem_ingestion_confirmed"] is False
    assert preview["payload"].startswith("<")
    assert ">1 " in preview["payload"]
    assert preview["payload_bytes"] <= 4096
    assert len(preview["content_digest"]) == 64
    assert "unconfirmed" in data["safety_notice"].lower()


def test_explicit_test_event_uses_same_tls_path_without_claiming_siem_ingestion() -> None:
    audit_sink = CollectingAuditSink()
    with TestClient(create_app(settings(), audit_sink=audit_sink)) as client:
        response = client.post(
            "/api/v1/security-export/test-event",
            headers={"X-Correlation-ID": "cor_export_test"},
        )

    delivery = response.json()["data"]
    assert response.status_code == 200
    assert delivery["state"] == "transport_delivered"
    assert delivery["attempts"] == 1
    assert delivery["event_id"].startswith("evt_")
    assert delivery["receipt"]["event_id"] == delivery["event_id"]
    assert delivery["receipt"]["collector_acknowledged"] is True
    assert delivery["receipt"]["siem_ingestion_confirmed"] is False
    assert any(item.event_type == "atlas.security_export.test_event" for item in audit_sink.records)


@pytest.mark.asyncio
async def test_normalization_redacts_secret_tokens_and_frames_one_rfc5424_record() -> None:
    export_service, _, transport = service()
    await export_service.record(
        audit_record(
            event_id="evt_secret_token_value",
            scope_reference='password=do-not-export\nline-two"]',
        )
    )

    message = transport.messages[0]
    assert message.event_id == "redacted"
    assert "do-not-export" not in message.payload
    assert "\n" not in message.payload
    assert "\r" not in message.payload
    assert message.payload_bytes == len(message.payload.encode("utf-8"))


@pytest.mark.asyncio
async def test_transient_failure_retries_with_stable_event_identity() -> None:
    export_service, _, transport = service(transport=SyntheticTlsSyslogTransport(fail_attempts=1))
    await export_service.record(audit_record())
    initial = (await export_service.get_overview(context=context())).recent_deliveries
    failed = next(item for item in initial if item.event_id == "evt_security_export_test")
    assert failed.state is DeliveryState.RETRYING
    assert failed.next_attempt_at == NOW + timedelta(seconds=1)

    await export_service.retry_all(at=NOW + timedelta(seconds=1))
    final = (await export_service.get_overview(context=context())).recent_deliveries
    delivered = next(item for item in final if item.event_id == "evt_security_export_test")
    assert delivered.state is DeliveryState.TRANSPORT_DELIVERED
    assert delivered.attempts == 2
    assert any(message.event_id == failed.event_id for message in transport.messages)


@pytest.mark.asyncio
async def test_delivery_moves_to_dead_letter_after_bounded_attempts() -> None:
    export_service, _, _ = service(
        transport=SyntheticTlsSyslogTransport(fail_attempts=2),
        max_attempts=2,
    )
    await export_service.record(audit_record())
    await export_service.retry_all(at=NOW + timedelta(seconds=1))

    overview = await export_service.get_overview(context=context())
    delivery = next(
        item for item in overview.recent_deliveries if item.event_id == "evt_security_export_test"
    )
    assert delivery.state is DeliveryState.DEAD_LETTER
    assert delivery.attempts == 2
    assert overview.health[0].queue_depth == 0
    assert overview.health[0].dead_letter_count == 1


@pytest.mark.asyncio
async def test_expired_certificate_fails_closed_without_transport_downgrade() -> None:
    export_service, _, transport = service(
        certificate_not_after=datetime(2020, 1, 1, tzinfo=UTC),
        max_attempts=1,
    )
    await export_service.record(audit_record())

    overview = await export_service.get_overview(context=context())
    delivery = next(
        item for item in overview.recent_deliveries if item.event_id == "evt_security_export_test"
    )
    assert delivery.state is DeliveryState.DEAD_LETTER
    assert delivery.last_error_code == "tls_destination_validation_failed"
    assert transport.messages == []
    assert overview.destinations[0].transport.value == "tls"


@pytest.mark.asyncio
async def test_bounded_queue_rejects_new_events_when_transport_is_unavailable() -> None:
    export_service, sink, _ = service(
        transport=SyntheticTlsSyslogTransport(fail_attempts=5),
        max_queue_records=1,
    )
    await export_service.record(audit_record())

    with pytest.raises(RuntimeError, match="queue_capacity"):
        await export_service.record(audit_record(event_id="evt_second"))

    assert [item.event_id for item in sink.records] == [
        "evt_security_export_test",
        "evt_second",
    ]


def test_required_overview_audit_failure_blocks_response() -> None:
    sink = OverviewAuditFailingSink()
    export_service, _, _ = service(delegate=sink)
    with TestClient(
        create_app(
            settings(),
            audit_sink=sink,
            security_export_service=export_service,
        ),
        raise_server_exceptions=False,
    ) as client:
        response = client.get("/api/v1/security-export/overview")

    assert response.status_code == 500
    assert response.json()["code"] == "internal_error"
    assert "audit" not in response.text.lower()


@pytest.mark.asyncio
async def test_scope_mismatch_is_rejected_before_audit_or_transport() -> None:
    export_service, sink, transport = service()

    with pytest.raises(SecurityExportOperationsError, match="outside the authorized scope"):
        await export_service.emit_test_event(
            context=context(resource_id="resource.security-export.other")
        )

    assert sink.records == []
    assert transport.messages == []
