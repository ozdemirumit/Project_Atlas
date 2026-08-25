from __future__ import annotations

import asyncio
import re
from collections.abc import Callable, Mapping
from datetime import UTC, datetime
from time import monotonic
from uuid import uuid4

from atlas import __version__
from atlas.core.audit import AuditRecord, AuditSink
from atlas.modules.connectors.application.bundled_connection_configuration_ports import (
    BundledConnectionConfigurationRepository,
)
from atlas.modules.connectors.application.connection_test_ports import (
    ConnectorConnectionTestError,
    ConnectorConnectionTestResultRepository,
    ConnectorCredentialMaterializer,
    HitachiConnectionTestTransportFactory,
)
from atlas.modules.connectors.application.instance_creation_ports import ConnectorInstanceRepository
from atlas.modules.connectors.domain.connection_test import ConnectorConnectionTestResult
from atlas.modules.connectors.domain.instance_creation import DISABLED_UNCONFIGURED
from atlas.modules.connectors.vendors.hitachi_ops_center.manifest import PACKAGE_ID
from atlas.modules.connectors.vendors.hitachi_ops_center.ports import HitachiTransportError
from atlas.modules.identity.domain.models import AuthenticatedSubject, SubjectKind

CONNECTION_TEST_PERMISSION = "connectors.target-sessions.read"
_VERSION = re.compile(r"^[0-9]+\.[0-9]+\.[0-9]+$")


class ConnectorConnectionTestService:
    def __init__(
        self,
        *,
        configuration_repository: BundledConnectionConfigurationRepository,
        result_repository: ConnectorConnectionTestResultRepository,
        instance_repository: ConnectorInstanceRepository,
        credential_materializer: ConnectorCredentialMaterializer,
        transport_factory: HitachiConnectionTestTransportFactory,
        audit_sink: AuditSink,
        environment_id: str,
        deployment_environment: str,
        clock: Callable[[], datetime] | None = None,
        timeout_seconds: float = 15.0,
        maximum_response_bytes: int = 65_536,
    ) -> None:
        if not 0 < timeout_seconds <= 30 or not 1 <= maximum_response_bytes <= 1_048_576:
            raise ValueError("Connection test bounds are invalid")
        self._configuration_repository = configuration_repository
        self._result_repository = result_repository
        self._instance_repository = instance_repository
        self._credential_materializer = credential_materializer
        self._transport_factory = transport_factory
        self._audit_sink = audit_sink
        self._environment_id = environment_id
        self._development_enabled = deployment_environment == "development"
        self._clock = clock or (lambda: datetime.now(UTC))
        self._timeout_seconds = timeout_seconds
        self._maximum_response_bytes = maximum_response_bytes

    @property
    def result_repository(self) -> ConnectorConnectionTestResultRepository:
        return self._result_repository

    async def test(
        self,
        *,
        actor: AuthenticatedSubject,
        instance_id: str,
        correlation_id: str,
    ) -> ConnectorConnectionTestResult:
        self._require_development_human(actor)
        await self._require_bundled_instance(actor=actor, instance_id=instance_id)
        configuration = await self._configuration_repository.get(
            organization_id=actor.organization_id,
            environment_id=self._environment_id,
            instance_id=instance_id,
        )
        if configuration is None:
            raise ConnectorConnectionTestError("connection_test_configuration_not_found")
        if (
            configuration.connector_id != PACKAGE_ID
            or configuration.protocol != "https"
            or configuration.secret_material_stored
            or configuration.infrastructure_mutation_performed
        ):
            raise ConnectorConnectionTestError("connection_test_configuration_invalid")

        await self._audit(actor, correlation_id, "connector_connection_test_requested", instance_id)
        started = monotonic()
        outcome = "failed"
        result_code = "connection_test_failed_safely"
        retryable = False
        request_performed = False
        target_contacted = False
        try:
            async with self._credential_materializer.lease_authorization_header(
                secret_reference_id=configuration.secret_reference_id,
                maximum_lease_seconds=min(30, int(self._timeout_seconds) + 1),
            ) as lease:
                transport = self._transport_factory.create(
                    hostname=configuration.hostname,
                    port=configuration.port,
                    trust_profile_id=configuration.trust_profile_id,
                    authorization_header_provider=lease.authorization_header,
                    timeout_seconds=self._timeout_seconds,
                    maximum_response_bytes=self._maximum_response_bytes,
                )
                request_performed = True
                target_contacted = True
                async with asyncio.timeout(self._timeout_seconds + 1):
                    payload = await transport.get("/configuration/version")
                result_code = self._version_result(payload)
                outcome = "passed" if result_code == "hitachi_api_compatible" else "failed"
        except HitachiTransportError as error:
            result_code = error.code
            retryable = error.retryable
        except TimeoutError:
            result_code = "target_timeout"
            retryable = True
        except ConnectorConnectionTestError as error:
            result_code = self._minimized_failure_code(str(error))
        except Exception:
            result_code = "connection_test_failed_safely"

        result = ConnectorConnectionTestResult(
            test_id=f"test_{uuid4().hex}",
            connector_id=configuration.connector_id,
            instance_id=configuration.instance_id,
            outcome=outcome,
            result_code=result_code,
            retryable=retryable,
            checked_at=self._clock(),
            duration_ms=min(300_000, max(0, int((monotonic() - started) * 1000))),
            read_only_request_performed=request_performed,
            managed_infrastructure_contacted=target_contacted,
        )
        await self._result_repository.put(
            organization_id=actor.organization_id,
            environment_id=self._environment_id,
            result=result,
        )
        await self._audit(actor, correlation_id, result.result_code, instance_id)
        return result

    async def latest(
        self,
        *,
        actor: AuthenticatedSubject,
        instance_id: str,
        correlation_id: str,
    ) -> ConnectorConnectionTestResult:
        self._require_development_human(actor)
        await self._require_bundled_instance(actor=actor, instance_id=instance_id)
        result = await self._result_repository.get_latest(
            organization_id=actor.organization_id,
            environment_id=self._environment_id,
            instance_id=instance_id,
        )
        if result is None:
            raise ConnectorConnectionTestError("connection_test_result_not_found")
        await self._audit(
            actor,
            correlation_id,
            "connection_test_latest_read",
            instance_id,
        )
        return result

    def _require_development_human(self, actor: AuthenticatedSubject) -> None:
        if not self._development_enabled:
            raise ConnectorConnectionTestError("connection_test_development_only")
        if actor.kind is not SubjectKind.HUMAN:
            raise ConnectorConnectionTestError("connection_test_human_required")

    async def _require_bundled_instance(
        self, *, actor: AuthenticatedSubject, instance_id: str
    ) -> None:
        records = await self._instance_repository.list_scope(
            organization_id=actor.organization_id,
            environment_id=self._environment_id,
        )
        matches = tuple(item for item in records if item.instance_id == instance_id)
        if len(matches) != 1:
            raise ConnectorConnectionTestError("connection_test_instance_not_found")
        record = matches[0]
        if record.connector_id != PACKAGE_ID or record.instance_state != DISABLED_UNCONFIGURED:
            raise ConnectorConnectionTestError("connection_test_instance_invalid")

    @staticmethod
    def _version_result(payload: Mapping[str, object]) -> str:
        if payload.get("productName") != "Configuration Manager REST API":
            return "product_mismatch"
        version = payload.get("apiVersion")
        if not isinstance(version, str) or _VERSION.fullmatch(version) is None:
            return "unsupported_vendor_version"
        return "hitachi_api_compatible"

    @staticmethod
    def _minimized_failure_code(code: str) -> str:
        if code in {
            "connection_test_credentials_unavailable",
            "connection_test_credential_lease_closed",
        }:
            return code
        return "connection_test_failed_safely"

    async def _audit(
        self,
        actor: AuthenticatedSubject,
        correlation_id: str,
        result_code: str,
        instance_id: str,
    ) -> None:
        await self._audit_sink.record(
            AuditRecord(
                event_id=f"evt_{uuid4().hex}",
                event_type="atlas.connector.connection-test",
                schema_version="1.0",
                producer="project-atlas-api",
                producer_version=__version__,
                occurred_at=self._clock(),
                correlation_id=correlation_id,
                subject_id=actor.subject_id,
                actor_type=actor.kind.value,
                authentication_method=actor.authentication_method.value,
                assurance_level=actor.assurance_level.value,
                permission_id=CONNECTION_TEST_PERMISSION,
                resource_type="resource.connector.connection-test",
                scope_reference=instance_id,
                decision_id=None,
                outcome="succeeded" if result_code == "hitachi_api_compatible" else "recorded",
                result_code=result_code,
                target_metadata=(("infrastructure_mutation_performed", "false"),),
            )
        )
