from __future__ import annotations

from datetime import UTC, datetime

import pytest

from atlas.core.audit import AuditRecord
from atlas.modules.security_export.adapters.destination_administration_memory import (
    InMemorySyslogDestinationAdministrationRepository,
)
from atlas.modules.security_export.application.destination_administration import (
    SyslogDestinationAdministrationError,
    SyslogDestinationAdministrationService,
)
from atlas.modules.security_export.domain.destination_administration import (
    VALIDATION_STEP_ORDER,
    DestinationDisablement,
    DestinationValidationRecord,
    DestinationValidationStep,
    a_mandatory_destination_is_disabled_without_elevated_authorization_or_warning,
    a_socket_only_check_is_reported_as_full_end_to_end_destination_validation,
)

NOW = datetime(2026, 9, 7, 12, 0, tzinfo=UTC)


class CollectingAuditSink:
    def __init__(self) -> None:
        self.records: list[AuditRecord] = []

    async def record(self, event: AuditRecord) -> None:
        self.records.append(event)


def _service() -> tuple[SyslogDestinationAdministrationService, CollectingAuditSink]:
    audit_sink = CollectingAuditSink()
    service = SyslogDestinationAdministrationService(
        repository=InMemorySyslogDestinationAdministrationRepository(),
        audit_sink=audit_sink,
        clock=lambda: NOW,
    )
    return service, audit_sink


def test_absolute_rules_are_false() -> None:
    assert a_mandatory_destination_is_disabled_without_elevated_authorization_or_warning() is False
    assert a_socket_only_check_is_reported_as_full_end_to_end_destination_validation() is False


def test_validation_record_rejects_out_of_order_steps() -> None:
    with pytest.raises(ValueError, match="declared order"):
        DestinationValidationRecord(
            destination_id="destination.siem-collector.primary",
            completed_steps=(DestinationValidationStep.TEST_EVENT_SENT,),
        )


def test_validation_record_is_fully_validated_only_after_every_step() -> None:
    partial = DestinationValidationRecord(
        destination_id="destination.siem-collector.primary",
        completed_steps=VALIDATION_STEP_ORDER[:2],
    )
    assert partial.is_fully_validated is False
    full = DestinationValidationRecord(
        destination_id="destination.siem-collector.primary",
        completed_steps=VALIDATION_STEP_ORDER,
    )
    assert full.is_fully_validated is True


def test_mandatory_disablement_requires_authorization_and_warning() -> None:
    with pytest.raises(ValueError, match="elevated authorization"):
        DestinationDisablement(
            destination_id="destination.siem-collector.primary",
            disabled_by="subject.operator.primary",
            reason="Decommissioning legacy collector.",
            mandatory_destination=True,
            elevated_authorization=False,
            warning_acknowledged=True,
            disabled_at=NOW,
        )


@pytest.mark.asyncio
async def test_register_profile() -> None:
    service, audit_sink = _service()
    profile = await service.register_profile(
        destination_id="destination.siem-collector.primary",
        owner="subject.security-engineer.primary",
        purpose="Forward security audit events to the enterprise SIEM.",
        environment_id="environment.production",
        maintenance_windows=("Sundays 02:00-04:00 UTC",),
        health_alert_recipients=("team.security-operations@example.com",),
        mandatory=True,
        correlation_id="correlation.test",
    )
    assert profile.active_version == 1
    assert profile.last_validated_at is None
    assert any(item.result_code == "syslog_destination.registered" for item in audit_sink.records)


@pytest.mark.asyncio
async def test_register_profile_twice_is_refused() -> None:
    service, _audit = _service()
    kwargs = {
        "destination_id": "destination.siem-collector.primary",
        "owner": "subject.security-engineer.primary",
        "purpose": "Forward security audit events to the enterprise SIEM.",
        "environment_id": "environment.production",
        "maintenance_windows": (),
        "health_alert_recipients": ("team.security-operations@example.com",),
        "mandatory": False,
        "correlation_id": "correlation.test",
    }
    await service.register_profile(**kwargs)  # type: ignore[arg-type]
    with pytest.raises(SyslogDestinationAdministrationError) as exc_info:
        await service.register_profile(**kwargs)  # type: ignore[arg-type]
    assert exc_info.value.code == "syslog_destination_already_registered"


async def _register(service: SyslogDestinationAdministrationService, *, mandatory: bool) -> None:
    await service.register_profile(
        destination_id="destination.siem-collector.primary",
        owner="subject.security-engineer.primary",
        purpose="Forward security audit events to the enterprise SIEM.",
        environment_id="environment.production",
        maintenance_windows=(),
        health_alert_recipients=("team.security-operations@example.com",),
        mandatory=mandatory,
        correlation_id="correlation.test",
    )


@pytest.mark.asyncio
async def test_activate_requires_full_validation() -> None:
    service, _audit = _service()
    await _register(service, mandatory=False)
    with pytest.raises(SyslogDestinationAdministrationError) as exc_info:
        await service.activate(
            destination_id="destination.siem-collector.primary",
            activated_by="subject.security-engineer.primary",
            correlation_id="correlation.test",
        )
    assert exc_info.value.code == "syslog_destination_validation_incomplete"


@pytest.mark.asyncio
async def test_full_validation_then_activation() -> None:
    service, audit_sink = _service()
    await _register(service, mandatory=False)
    for step in VALIDATION_STEP_ORDER:
        await service.record_validation_step(
            destination_id="destination.siem-collector.primary",
            step=step,
            correlation_id="correlation.test",
        )
    activated = await service.activate(
        destination_id="destination.siem-collector.primary",
        activated_by="subject.security-engineer.primary",
        correlation_id="correlation.test",
    )
    assert activated.active_version == 2
    assert activated.last_validated_at == NOW
    assert any(item.result_code == "syslog_destination.activated" for item in audit_sink.records)


@pytest.mark.asyncio
async def test_disable_a_non_mandatory_destination_needs_only_a_reason() -> None:
    service, audit_sink = _service()
    await _register(service, mandatory=False)
    disablement = await service.disable(
        destination_id="destination.siem-collector.primary",
        disabled_by="subject.operator.primary",
        reason="Replacing with a new collector endpoint.",
        elevated_authorization=False,
        warning_acknowledged=False,
        correlation_id="correlation.test",
    )
    assert disablement.mandatory_destination is False
    assert any(item.result_code == "syslog_destination.disabled" for item in audit_sink.records)


@pytest.mark.asyncio
async def test_disable_a_mandatory_destination_requires_elevated_authorization() -> None:
    service, _audit = _service()
    await _register(service, mandatory=True)
    with pytest.raises(SyslogDestinationAdministrationError) as exc_info:
        await service.disable(
            destination_id="destination.siem-collector.primary",
            disabled_by="subject.operator.primary",
            reason="Attempted disablement without elevation.",
            elevated_authorization=False,
            warning_acknowledged=True,
            correlation_id="correlation.test",
        )
    assert exc_info.value.code == "syslog_destination_disablement_denied"
    disablement = await service.disable(
        destination_id="destination.siem-collector.primary",
        disabled_by="subject.security-administrator.primary",
        reason="Compliance-approved decommission.",
        elevated_authorization=True,
        warning_acknowledged=True,
        correlation_id="correlation.test",
    )
    assert disablement.mandatory_destination is True
