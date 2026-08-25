from __future__ import annotations

from collections.abc import Callable
from datetime import UTC, datetime
from uuid import uuid4

from atlas import __version__
from atlas.core.audit import AuditRecord, AuditSink
from atlas.modules.connectors.application.bundled_connection_configuration_ports import (
    BundledConnectionConfigurationError,
    BundledConnectionConfigurationRepository,
)
from atlas.modules.connectors.application.instance_creation_ports import ConnectorInstanceRepository
from atlas.modules.connectors.domain.bundled_connection_configuration import (
    BundledConnectionConfiguration,
    validate_connection_hostname,
)
from atlas.modules.connectors.domain.instance_creation import DISABLED_UNCONFIGURED
from atlas.modules.connectors.vendors.hitachi_ops_center.manifest import PACKAGE_ID
from atlas.modules.identity.domain.models import AuthenticatedSubject, SubjectKind


class BundledConnectionConfigurationService:
    def __init__(
        self,
        *,
        repository: BundledConnectionConfigurationRepository,
        instance_repository: ConnectorInstanceRepository,
        audit_sink: AuditSink,
        environment_id: str,
        deployment_environment: str,
        clock: Callable[[], datetime] | None = None,
    ) -> None:
        self._repository = repository
        self._instance_repository = instance_repository
        self._audit_sink = audit_sink
        self._environment_id = environment_id
        self._development_enabled = deployment_environment == "development"
        self._clock = clock or (lambda: datetime.now(UTC))

    @property
    def repository(self) -> BundledConnectionConfigurationRepository:
        return self._repository

    async def configure(
        self,
        *,
        actor: AuthenticatedSubject,
        instance_id: str,
        hostname: str,
        port: int,
        trust_profile_id: str,
        secret_reference_id: str,
        correlation_id: str,
    ) -> BundledConnectionConfiguration:
        self._require_development_human(actor)
        await self._require_bundled_instance(actor=actor, instance_id=instance_id)
        try:
            normalized_hostname = validate_connection_hostname(hostname)
        except ValueError as error:
            raise BundledConnectionConfigurationError(
                "bundled_connection_configuration_invalid"
            ) from error
        record = BundledConnectionConfiguration(
            configuration_id=f"connection_configuration.{uuid4().hex}",
            organization_id=actor.organization_id,
            environment_id=self._environment_id,
            connector_id=PACKAGE_ID,
            instance_id=instance_id,
            hostname=normalized_hostname,
            port=port,
            trust_profile_id=trust_profile_id,
            secret_reference_id=secret_reference_id,
            configured_by=actor.subject_id,
            configured_at=self._clock(),
        )
        await self._repository.put(record)
        await self._audit(
            actor, correlation_id, "bundled_connection_configuration_saved", instance_id
        )
        return record

    async def get(
        self, *, actor: AuthenticatedSubject, instance_id: str, correlation_id: str
    ) -> BundledConnectionConfiguration:
        self._require_development_human(actor)
        await self._require_bundled_instance(actor=actor, instance_id=instance_id)
        record = await self._repository.get(
            organization_id=actor.organization_id,
            environment_id=self._environment_id,
            instance_id=instance_id,
        )
        if record is None:
            raise BundledConnectionConfigurationError("bundled_connection_configuration_not_found")
        await self._audit(
            actor, correlation_id, "bundled_connection_configuration_read", instance_id
        )
        return record

    def _require_development_human(self, actor: AuthenticatedSubject) -> None:
        if not self._development_enabled:
            raise BundledConnectionConfigurationError(
                "bundled_connection_configuration_development_only"
            )
        if actor.kind is not SubjectKind.HUMAN:
            raise BundledConnectionConfigurationError(
                "bundled_connection_configuration_human_required"
            )

    async def _require_bundled_instance(
        self, *, actor: AuthenticatedSubject, instance_id: str
    ) -> None:
        records = await self._instance_repository.list_scope(
            organization_id=actor.organization_id,
            environment_id=self._environment_id,
        )
        matches = tuple(item for item in records if item.instance_id == instance_id)
        if len(matches) != 1:
            raise BundledConnectionConfigurationError("bundled_instance_not_found")
        record = matches[0]
        if record.connector_id != PACKAGE_ID or record.instance_state != DISABLED_UNCONFIGURED:
            raise BundledConnectionConfigurationError("bundled_instance_invalid")

    async def _audit(
        self, actor: AuthenticatedSubject, correlation_id: str, result_code: str, instance_id: str
    ) -> None:
        await self._audit_sink.record(
            AuditRecord(
                event_id=f"evt_{uuid4().hex}",
                event_type="atlas.connector.bundled-connection-configuration",
                schema_version="1.0",
                producer="project-atlas-api",
                producer_version=__version__,
                occurred_at=self._clock(),
                correlation_id=correlation_id,
                subject_id=actor.subject_id,
                actor_type=actor.kind.value,
                authentication_method=actor.authentication_method.value,
                assurance_level=actor.assurance_level.value,
                permission_id="connectors.target-sessions.create",
                resource_type="resource.connector.bundled-connection-configuration",
                scope_reference=instance_id,
                decision_id=None,
                outcome="succeeded",
                result_code=result_code,
                target_metadata=(("secret_material_stored", "false"),),
            )
        )
