"""ATLAS-034 SS7/SS16/SS19: Syslog destination administration application service."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import replace
from datetime import UTC, datetime
from uuid import uuid4

from atlas import __version__
from atlas.core.audit import AuditRecord, AuditSink
from atlas.modules.security_export.application.destination_administration_ports import (
    SyslogDestinationAdministrationRepository,
)
from atlas.modules.security_export.domain.destination_administration import (
    DestinationDisablement,
    DestinationValidationRecord,
    DestinationValidationStep,
    SyslogDestinationProfile,
)


class SyslogDestinationAdministrationError(Exception):
    def __init__(self, code: str) -> None:
        super().__init__(code)
        self.code = code


class SyslogDestinationAdministrationService:
    def __init__(
        self,
        *,
        repository: SyslogDestinationAdministrationRepository,
        audit_sink: AuditSink,
        clock: Callable[[], datetime] | None = None,
    ) -> None:
        self._repository = repository
        self._audit_sink = audit_sink
        self._clock = clock or (lambda: datetime.now(UTC))

    async def register_profile(
        self,
        *,
        destination_id: str,
        owner: str,
        purpose: str,
        environment_id: str,
        maintenance_windows: tuple[str, ...],
        health_alert_recipients: tuple[str, ...],
        mandatory: bool,
        correlation_id: str,
    ) -> SyslogDestinationProfile:
        if await self._repository.get_profile(destination_id) is not None:
            raise SyslogDestinationAdministrationError("syslog_destination_already_registered")
        try:
            profile = SyslogDestinationProfile(
                destination_id=destination_id,
                owner=owner,
                purpose=purpose,
                environment_id=environment_id,
                maintenance_windows=maintenance_windows,
                health_alert_recipients=health_alert_recipients,
                mandatory=mandatory,
                last_validated_at=None,
                active_version=1,
            )
        except ValueError as error:
            raise SyslogDestinationAdministrationError(
                "syslog_destination_profile_invalid"
            ) from error
        await self._repository.save_profile(profile)
        await self._audit(
            correlation_id=correlation_id,
            destination_id=destination_id,
            actor=owner,
            outcome="registered",
        )
        return profile

    async def record_validation_step(
        self,
        *,
        destination_id: str,
        step: DestinationValidationStep,
        correlation_id: str,
    ) -> DestinationValidationRecord:
        if await self._repository.get_profile(destination_id) is None:
            raise SyslogDestinationAdministrationError("syslog_destination_unavailable")
        current = await self._repository.get_validation(destination_id)
        completed = current.completed_steps if current is not None else ()
        try:
            updated = DestinationValidationRecord(
                destination_id=destination_id, completed_steps=(*completed, step)
            )
        except ValueError as error:
            raise SyslogDestinationAdministrationError(
                "syslog_destination_validation_out_of_order"
            ) from error
        await self._repository.save_validation(updated)
        await self._audit(
            correlation_id=correlation_id,
            destination_id=destination_id,
            actor=None,
            outcome=f"validation_step.{step.value}",
        )
        return updated

    async def activate(
        self, *, destination_id: str, activated_by: str, correlation_id: str
    ) -> SyslogDestinationProfile:
        profile = await self._repository.get_profile(destination_id)
        if profile is None:
            raise SyslogDestinationAdministrationError("syslog_destination_unavailable")
        validation = await self._repository.get_validation(destination_id)
        if validation is None or not validation.is_fully_validated:
            raise SyslogDestinationAdministrationError("syslog_destination_validation_incomplete")
        updated = replace(
            profile,
            last_validated_at=self._clock(),
            active_version=profile.active_version + 1,
        )
        await self._repository.save_profile(updated)
        await self._audit(
            correlation_id=correlation_id,
            destination_id=destination_id,
            actor=activated_by,
            outcome="activated",
        )
        return updated

    async def disable(
        self,
        *,
        destination_id: str,
        disabled_by: str,
        reason: str,
        elevated_authorization: bool,
        warning_acknowledged: bool,
        correlation_id: str,
    ) -> DestinationDisablement:
        profile = await self._repository.get_profile(destination_id)
        if profile is None:
            raise SyslogDestinationAdministrationError("syslog_destination_unavailable")
        try:
            disablement = DestinationDisablement(
                destination_id=destination_id,
                disabled_by=disabled_by,
                reason=reason,
                mandatory_destination=profile.mandatory,
                elevated_authorization=elevated_authorization,
                warning_acknowledged=warning_acknowledged,
                disabled_at=self._clock(),
            )
        except ValueError as error:
            raise SyslogDestinationAdministrationError(
                "syslog_destination_disablement_denied"
            ) from error
        await self._repository.save_disablement(disablement)
        await self._audit(
            correlation_id=correlation_id,
            destination_id=destination_id,
            actor=disabled_by,
            outcome="disabled",
        )
        return disablement

    async def _audit(
        self, *, correlation_id: str, destination_id: str, actor: str | None, outcome: str
    ) -> None:
        await self._audit_sink.record(
            AuditRecord(
                event_id=f"evt_{uuid4().hex}",
                event_type="atlas.security_export.destination.administration",
                schema_version="1.0",
                producer="project-atlas-api",
                producer_version=__version__,
                occurred_at=self._clock(),
                correlation_id=correlation_id,
                subject_id=actor,
                actor_type=None,
                authentication_method=None,
                assurance_level=None,
                permission_id=None,
                resource_type="resource.security-export.syslog-destination",
                scope_reference=destination_id,
                decision_id=None,
                outcome="succeeded",
                result_code=f"syslog_destination.{outcome}",
            )
        )
